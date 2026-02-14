"""
NBA Teams Load DAG (Cold Path)

Manual-trigger DAG for loading team reference data from BallDontLie API.
Truncates and replaces the entire hist_nba_teams table.

Schedule: None (manual trigger)
Source: BallDontLie API (teams endpoint)
Table: hist_nba_teams
"""
from datetime import datetime, timedelta

from airflow.sdk import dag
from airflow.providers.standard.operators.python import PythonOperator

from include.capstone.balldontlie_client import fetch_all_teams
from include.capstone.storage import (
    upload_archive,
    upload_bulk,
    build_teams_archive_payload,
)
from include.capstone.database import load_teams_to_snowflake
from include.capstone.callbacks import alert_on_failure


def run_fetch_teams(**context):
    records, raw_response = fetch_all_teams()
    context["ti"].xcom_push(key="raw_response", value=raw_response)
    print(f"Fetched {len(records)} teams")
    return records


def run_upload_archive(**context):
    ti = context["ti"]
    records = ti.xcom_pull(task_ids="fetch_teams")
    raw_response = ti.xcom_pull(task_ids="fetch_teams", key="raw_response")
    if not records:
        return None
    payload = build_teams_archive_payload(records, raw_response)
    return upload_archive("teams", payload)


def run_upload_bulk(**context):
    ti = context["ti"]
    records = ti.xcom_pull(task_ids="fetch_teams")
    return upload_bulk("teams", records)


def run_load_to_snowflake(**context):
    ti = context["ti"]
    bulk_path = ti.xcom_pull(task_ids="upload_bulk")
    result = load_teams_to_snowflake(bulk_path)
    print(f"Load result: {result}")
    return result


@dag(
    dag_id="nba_teams_load_v1",
    description="Load NBA team reference data from BallDontLie (manual)",
    default_args={
        "owner": "capstone",
        "retries": 1,
        "retry_delay": timedelta(minutes=2),
        "execution_timeout": timedelta(minutes=10),
        "on_failure_callback": alert_on_failure,
    },
    start_date=datetime(2023, 10, 24),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["capstone", "nba", "teams", "reference"],
)
def nba_teams_load():
    fetch = PythonOperator(
        task_id="fetch_teams",
        python_callable=run_fetch_teams,
    )
    archive = PythonOperator(
        task_id="upload_archive",
        python_callable=run_upload_archive,
    )
    bulk = PythonOperator(
        task_id="upload_bulk",
        python_callable=run_upload_bulk,
    )
    load = PythonOperator(
        task_id="load_to_snowflake",
        python_callable=run_load_to_snowflake,
    )

    fetch >> [archive, bulk] >> load


nba_teams_load()
