"""
NBA Player Box Scores Daily DAG
Fetches player-level box scores from BallDontLie API and stores to S3 + Snowflake.

Data Source: BallDontLie API (https://api.balldontlie.io/v1/box_scores)

Purpose:
- Fetch raw player stats for all games on a date
- Stores player-level data (NOT aggregated)
- dbt aggregates to team level for analysis
- Catches any games missed by the live DAG

Why player-level?
- Faster ingestion (no Python aggregation)
- Flexibility (can analyze player data later if needed)
- dbt optimization (SQL aggregation is fast and testable)

Schedule: 10am EST (15:00 UTC) daily
- Games end by ~2-3am EST at latest
- By 10am EST, all games from yesterday are Final

Idempotent: Re-running same date produces identical results (DELETE + INSERT).
"""
from airflow.sdk import dag
from airflow.providers.standard.operators.python import PythonOperator, ShortCircuitOperator
from datetime import datetime, timedelta

from include.capstone.config import is_nba_season
from include.capstone.balldontlie_client import fetch_box_scores_for_date
from include.capstone.storage import upload_box_scores_to_s3, upload_box_scores_ndjson_to_s3
from include.capstone.database import load_box_scores_to_snowflake


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


def run_fetch_box_scores(**context):
    """Fetch player box scores from BallDontLie API."""
    ds = context["ds"]
    records, raw_response = fetch_box_scores_for_date(ds)
    print(f"Fetched {len(records)} player box score records for {ds}")

    context["ti"].xcom_push(key="raw_response", value=raw_response)
    return records


def run_upload_to_s3(**context):
    """Upload box scores to S3 (JSON for archive + NDJSON for COPY INTO)."""
    ti = context["ti"]
    ds = context["ds"]
    records = ti.xcom_pull(task_ids="fetch_box_scores")
    raw_response = ti.xcom_pull(task_ids="fetch_box_scores", key="raw_response")

    if not records:
        print(f"No box score records for {ds} - skipping S3 upload")
        return None

    # Upload JSON with metadata (for archiving)
    json_path = upload_box_scores_to_s3(ds, records, raw_response)
    print(f"Uploaded JSON archive to {json_path}")

    # Upload NDJSON (for fast COPY INTO)
    ndjson_path = upload_box_scores_ndjson_to_s3(ds, records)
    print(f"Uploaded NDJSON for COPY INTO to {ndjson_path}")

    return ndjson_path


def run_load_to_snowflake(**context):
    """Load box scores to Snowflake using COPY INTO from S3."""
    ti = context["ti"]
    ds = context["ds"]
    ndjson_path = ti.xcom_pull(task_ids="upload_to_s3")

    if not ndjson_path:
        print(f"No NDJSON path for {ds} - skipping Snowflake load")
        return {"ds": ds, "deleted": 0, "inserted": 0}

    result = load_box_scores_to_snowflake(ds, ndjson_path)
    print(f"Load result: {result}")
    return result


# ===========================================
# DAG Definition
# ===========================================
@dag(
    dag_id="nba_player_box_scores_daily_v1",
    description="Daily: Fetch NBA player box scores to S3 + Snowflake (backfill + catchup)",
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
    tags=["capstone", "nba-box-scores", "balldontlie", "daily"],
)
def nba_player_box_scores_daily_dag():
    """
    Daily DAG to ingest NBA player box scores.

    Flow:
    1. Check if date is within NBA season (skip if off-season)
    2. Fetch box scores from BallDontLie API (player-level, not aggregated)
    3. Upload to S3 (JSON archive + NDJSON for fast loading)
    4. Load to Snowflake with COPY INTO from S3

    Note: dbt will aggregate player stats to team level for analysis.
    """
    check_season = ShortCircuitOperator(
        task_id="check_nba_season",
        python_callable=run_check_season,
    )

    fetch_box_scores = PythonOperator(
        task_id="fetch_box_scores",
        python_callable=run_fetch_box_scores,
    )

    upload_to_s3 = PythonOperator(
        task_id="upload_to_s3",
        python_callable=run_upload_to_s3,
    )

    load_to_snowflake = PythonOperator(
        task_id="load_to_snowflake",
        python_callable=run_load_to_snowflake,
    )

    check_season >> fetch_box_scores >> upload_to_s3 >> load_to_snowflake


nba_player_box_scores_daily_dag()
