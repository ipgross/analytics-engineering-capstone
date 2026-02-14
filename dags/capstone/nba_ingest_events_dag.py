"""
NBA Daily Events DAG (Cold Path)

Fetches today's game schedule/events from The Odds API.
Archives raw JSON.gz to S3, loads typed Parquet to Snowflake.

Uses data_interval_end (today) as the game date so the morning run
captures today's scheduled games before they start.

Pattern: fetch → S3 → stage → DQ → MERGE → ops log
Idempotency: MERGE (atomic upsert), staging cleared per-date.

Schedule: Daily at 7am ET (12:00 UTC)
Source: The Odds API (events endpoint)
Table: hist_nba_events
"""
from datetime import datetime, timedelta

from airflow.sdk import dag
from airflow.providers.standard.operators.python import PythonOperator, ShortCircuitOperator

from include.capstone.config import is_nba_season
from include.capstone.api_client import fetch_events_for_date
from include.capstone.storage import (
    upload_archive,
    upload_bulk,
    build_events_archive_payload,
)
from include.capstone.database import stage_events, validate_events, merge_events
from include.capstone.dag_tasks import build_cold_path_tasks
from include.capstone.callbacks import alert_on_failure

DAG_ID = "nba_ingest_events_v3"


def _game_date(context) -> str:
    """Get today's date (ds) as the game date for events capture."""
    return context["ds"]


def run_check_season(**context):
    return is_nba_season(_game_date(context))


def run_fetch_events(**context):
    game_date = _game_date(context)
    events = fetch_events_for_date(game_date)
    print(f"Fetched {len(events)} events for {game_date}")
    return events


def run_upload_archive(**context):
    ti = context["ti"]
    game_date = _game_date(context)
    events = ti.xcom_pull(task_ids="fetch_events")
    if not events:
        return None
    today_et = datetime.now().strftime("%Y-%m-%d")
    endpoint = "historical" if game_date < today_et else "current"
    payload = build_events_archive_payload(game_date, events, endpoint)
    return upload_archive("events", payload, date_str=game_date)


def run_upload_bulk(**context):
    ti = context["ti"]
    game_date = _game_date(context)
    events = ti.xcom_pull(task_ids="fetch_events")
    return upload_bulk("events", events, date_str=game_date)


@dag(
    dag_id=DAG_ID,
    description="Daily NBA events/schedule from The Odds API (cold path)",
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
    max_active_runs=3,
    is_paused_upon_creation=False,
    tags=["capstone", "nba", "events", "cold-path"],
)
def nba_ingest_events():
    check = ShortCircuitOperator(
        task_id="check_nba_season",
        python_callable=run_check_season,
    )
    fetch = PythonOperator(task_id="fetch_events", python_callable=run_fetch_events)
    archive = PythonOperator(task_id="upload_archive", python_callable=run_upload_archive)
    bulk = PythonOperator(task_id="upload_bulk", python_callable=run_upload_bulk)

    tasks = build_cold_path_tasks(
        dataset="events",
        dag_id=DAG_ID,
        game_date_fn=_game_date,
        fetch_task_id="fetch_events",
        stage_fn=stage_events,
        validate_fn=validate_events,
        merge_fn=merge_events,
    )

    check >> fetch >> [archive, bulk] >> tasks.stage


nba_ingest_events()
