"""
NBA Games Daily DAG
Fetches game results from BallDontLie API and stores to S3 + Snowflake.

Data Source: BallDontLie API (https://api.balldontlie.io/v1/games)

Purpose:
- Fetch final game scores for completed games
- Used to calculate if teams covered the spread (join with odds data)
- Catches any games missed by the live DAG

Schedule: 10am EST (15:00 UTC) daily
- Games end by ~2-3am EST at latest
- By 10am EST, all games from yesterday are Final

Idempotent: Re-running same date produces identical results (DELETE + INSERT).
"""
from airflow.sdk import dag
from airflow.providers.standard.operators.python import PythonOperator, ShortCircuitOperator
from datetime import datetime, timedelta

from include.capstone.config import is_nba_season
from include.capstone.balldontlie_client import fetch_games_for_date
from include.capstone.storage import upload_games_to_s3, upload_games_ndjson_to_s3
from include.capstone.database import load_games_to_snowflake


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


def run_fetch_games(**context):
    """Fetch games from BallDontLie API."""
    ds = context["ds"]
    records, raw_response = fetch_games_for_date(ds)
    print(f"Fetched {len(records)} completed game records for {ds}")

    context["ti"].xcom_push(key="raw_response", value=raw_response)
    return records


def run_upload_to_s3(**context):
    """Upload games to S3 (JSON for archive + NDJSON for COPY INTO)."""
    ti = context["ti"]
    ds = context["ds"]
    records = ti.xcom_pull(task_ids="fetch_games")
    raw_response = ti.xcom_pull(task_ids="fetch_games", key="raw_response")

    if not records:
        print(f"No game records for {ds} - skipping S3 upload")
        return None

    # Upload JSON with metadata (for archiving)
    json_path = upload_games_to_s3(ds, records, raw_response)
    print(f"Uploaded JSON archive to {json_path}")

    # Upload NDJSON (for fast COPY INTO)
    ndjson_path = upload_games_ndjson_to_s3(ds, records)
    print(f"Uploaded NDJSON for COPY INTO to {ndjson_path}")

    return ndjson_path


def run_load_to_snowflake(**context):
    """Load games to Snowflake using COPY INTO from S3."""
    ti = context["ti"]
    ds = context["ds"]
    ndjson_path = ti.xcom_pull(task_ids="upload_to_s3")

    if not ndjson_path:
        print(f"No NDJSON path for {ds} - skipping Snowflake load")
        return {"ds": ds, "deleted": 0, "inserted": 0}

    result = load_games_to_snowflake(ds, ndjson_path)
    print(f"Load result: {result}")
    return result


# ===========================================
# DAG Definition
# ===========================================
@dag(
    dag_id="nba_games_daily_v1",
    description="Daily: Fetch NBA game results to S3 + Snowflake (backfill + catchup)",
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
    tags=["capstone", "nba-games", "balldontlie", "daily"],
)
def nba_games_daily_dag():
    """
    Daily DAG to ingest NBA game results.

    Flow:
    1. Check if date is within NBA season (skip if off-season)
    2. Fetch games from BallDontLie API (completed games only)
    3. Upload to S3 (JSON archive + NDJSON for fast loading)
    4. Load to Snowflake with COPY INTO from S3
    """
    check_season = ShortCircuitOperator(
        task_id="check_nba_season",
        python_callable=run_check_season,
    )

    fetch_games = PythonOperator(
        task_id="fetch_games",
        python_callable=run_fetch_games,
    )

    upload_to_s3 = PythonOperator(
        task_id="upload_to_s3",
        python_callable=run_upload_to_s3,
    )

    load_to_snowflake = PythonOperator(
        task_id="load_to_snowflake",
        python_callable=run_load_to_snowflake,
    )

    check_season >> fetch_games >> upload_to_s3 >> load_to_snowflake


nba_games_daily_dag()
