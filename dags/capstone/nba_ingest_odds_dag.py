"""
NBA Daily Odds Snapshot DAG (Cold Path)

Captures morning-line odds from The Odds API — one snapshot per game day.
This is the "opening line" used as a training feature for spread modeling.

Uses data_interval_end (today) as the game date so the morning run captures
today's opening odds via the regular endpoint (3 credits) before games start.
For manual triggers on past dates, fetch_odds_for_date auto-selects the
historical endpoint (30 credits).

Pattern: fetch → S3 → stage → DQ → MERGE → ops log
Idempotency: MERGE (atomic upsert), staging cleared per-date.

Schedule: Daily at 7am ET (12:00 UTC)
Source: The Odds API (odds endpoint)
Table: hist_nba_odds_open
"""
from datetime import datetime, timedelta

from airflow.sdk import dag
from airflow.providers.standard.operators.python import PythonOperator, ShortCircuitOperator

from include.capstone.config import is_nba_season
from include.capstone.api_client import fetch_odds_for_date
from include.capstone.storage import (
    upload_archive,
    upload_bulk,
    build_odds_archive_payload,
)
from include.capstone.database import stage_odds, validate_odds, merge_odds
from include.capstone.dag_tasks import build_cold_path_tasks
from include.capstone.callbacks import alert_on_failure

DAG_ID = "nba_ingest_odds_v3"


def _game_date(context) -> str:
    """Get today's date (ds) as the game date for odds capture."""
    return context["ds"]


def run_check_season(**context):
    return is_nba_season(_game_date(context))


def run_fetch_odds(**context):
    game_date = _game_date(context)
    records, raw_response = fetch_odds_for_date(game_date)
    context["ti"].xcom_push(key="raw_response", value=raw_response)
    print(f"Fetched {len(records)} odds records for {game_date}")
    return records


def run_upload_archive(**context):
    ti = context["ti"]
    game_date = _game_date(context)
    records = ti.xcom_pull(task_ids="fetch_odds")
    raw_response = ti.xcom_pull(task_ids="fetch_odds", key="raw_response")
    if not records:
        return None
    payload = build_odds_archive_payload(game_date, records, raw_response)
    return upload_archive("odds_open", payload, date_str=game_date)


def run_upload_bulk(**context):
    ti = context["ti"]
    game_date = _game_date(context)
    records = ti.xcom_pull(task_ids="fetch_odds")
    return upload_bulk("odds_open", records, date_str=game_date)


@dag(
    dag_id=DAG_ID,
    description="Daily morning-line odds snapshot from The Odds API (cold path)",
    default_args={
        "owner": "capstone",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=30),
        "on_failure_callback": alert_on_failure,
    },
    start_date=datetime(2023, 10, 24),
    schedule="0 12 * * *",
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["capstone", "nba", "odds", "cold-path"],
)
def nba_ingest_odds():
    check = ShortCircuitOperator(
        task_id="check_nba_season",
        python_callable=run_check_season,
    )
    fetch = PythonOperator(task_id="fetch_odds", python_callable=run_fetch_odds)
    archive = PythonOperator(task_id="upload_archive", python_callable=run_upload_archive)
    bulk = PythonOperator(task_id="upload_bulk", python_callable=run_upload_bulk)

    tasks = build_cold_path_tasks(
        dataset="odds_open",
        dag_id=DAG_ID,
        game_date_fn=_game_date,
        fetch_task_id="fetch_odds",
        stage_fn=stage_odds,
        validate_fn=validate_odds,
        merge_fn=merge_odds,
    )

    check >> fetch >> [archive, bulk] >> tasks.stage


nba_ingest_odds()
