"""
NBA Events Daily DAG
Fetches game events from The Odds API and stores to S3 + Snowflake.

API Cost:
- Past dates (backfill): 1 credit per day (FREE if no games)
- Today/future: FREE (0 credits)

Idempotent: Re-running same date produces identical results.
"""
from airflow.sdk import dag
from airflow.providers.standard.operators.python import PythonOperator, ShortCircuitOperator
from datetime import datetime, timedelta

from include.capstone.config import is_nba_season
from include.capstone.api_client import fetch_events_for_date
from include.capstone.storage import upload_events_to_s3
from include.capstone.database import load_events_to_snowflake


# ===========================================
# Task Functions
# ===========================================
def run_check_season(**context):
    """
    Check if execution date is within NBA season.
    Returns True to continue, False to skip downstream tasks.
    """
    ds = context["ds"]
    in_season = is_nba_season(ds)
    if not in_season:
        print(f"{ds} is off-season - skipping DAG execution")
    else:
        print(f"{ds} is within NBA season - proceeding")
    return in_season


def run_fetch_events(**context):
    """Fetch events from The Odds API."""
    ds = context["ds"]
    events = fetch_events_for_date(ds)
    print(f"Fetched {len(events)} events for {ds}")
    return events


def run_upload_to_s3(**context):
    """Upload events JSON to S3."""
    ti = context["ti"]
    ds = context["ds"]
    events = ti.xcom_pull(task_ids="fetch_events")

    if not events:
        print(f"No events for {ds} - skipping S3 upload")
        return None

    s3_path = upload_events_to_s3(ds, events)
    print(f"Uploaded to {s3_path}")
    return s3_path


def run_load_to_snowflake(**context):
    """Load events to Snowflake (DELETE + INSERT)."""
    ti = context["ti"]
    ds = context["ds"]
    events = ti.xcom_pull(task_ids="fetch_events")
    s3_path = ti.xcom_pull(task_ids="upload_to_s3")

    if not events:
        print(f"No events for {ds} - skipping Snowflake load")
        return {"ds": ds, "deleted": 0, "inserted": 0}

    result = load_events_to_snowflake(ds, events, s3_path)
    print(f"Load result: {result}")
    return result


# ===========================================
# DAG Definition
# ===========================================
@dag(
    dag_id="nba_events_daily_v3",
    description="Daily: Fetch NBA game events to S3 + Snowflake",
    default_args={
        "owner": "capstone",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=30),
    },
    start_date=datetime(2023, 10, 24),  # First game of 2023-24 season
    schedule="0 15 * * *",  # 10am EST = 15:00 UTC daily
    catchup=True,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["capstone", "nba-events"],
)
def nba_events_daily_dag():
    """
    Daily DAG to ingest NBA game events.

    Flow:
    1. Check if date is within NBA season (skip if off-season)
    2. Fetch events from The Odds API
    3. Upload to S3 with metadata wrapper
    4. Load to Snowflake with idempotent DELETE+INSERT
    """
    check_season = ShortCircuitOperator(
        task_id="check_nba_season",
        python_callable=run_check_season,
    )

    fetch_events = PythonOperator(
        task_id="fetch_events",
        python_callable=run_fetch_events,
    )

    upload_to_s3 = PythonOperator(
        task_id="upload_to_s3",
        python_callable=run_upload_to_s3,
    )

    load_to_snowflake = PythonOperator(
        task_id="load_to_snowflake",
        python_callable=run_load_to_snowflake,
    )

    check_season >> fetch_events >> upload_to_s3 >> load_to_snowflake


nba_events_daily_dag()
