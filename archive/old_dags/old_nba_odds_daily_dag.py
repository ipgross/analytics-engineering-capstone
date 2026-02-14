"""
NBA Odds Daily DAG
Fetches betting odds from The Odds API and stores to S3 + Snowflake.

Markets: h2h (moneyline), spreads, totals
Regions: us

API Cost:
- Past dates (backfill): 30 credits per day (10 base × 3 markets × 1 region)
- Today/future: 3 credits per call (1 base × 3 markets × 1 region)

Idempotent: Re-running same date produces identical results.
"""
from airflow.sdk import dag
from airflow.providers.standard.operators.python import PythonOperator, ShortCircuitOperator
from datetime import datetime, timedelta

from include.capstone.config import is_nba_season
from include.capstone.api_client import fetch_odds_for_date
from include.capstone.storage import upload_odds_to_s3, upload_odds_ndjson_to_s3
from include.capstone.database import load_odds_to_snowflake


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


def run_fetch_odds(**context):
    """Fetch odds from The Odds API."""
    ds = context["ds"]
    records, raw_response = fetch_odds_for_date(ds)
    print(f"Fetched {len(records)} odds records for {ds}")

    # Store raw_response in XCom for S3 upload
    context["ti"].xcom_push(key="raw_response", value=raw_response)

    return records


def run_upload_to_s3(**context):
    """Upload odds to S3 (JSON for archive + NDJSON for COPY INTO)."""
    ti = context["ti"]
    ds = context["ds"]
    records = ti.xcom_pull(task_ids="fetch_odds")
    raw_response = ti.xcom_pull(task_ids="fetch_odds", key="raw_response")

    if not records:
        print(f"No odds records for {ds} - skipping S3 upload")
        return None

    # Upload JSON with metadata (for archiving)
    json_path = upload_odds_to_s3(ds, records, raw_response)
    print(f"Uploaded JSON archive to {json_path}")

    # Upload NDJSON (for fast COPY INTO)
    ndjson_path = upload_odds_ndjson_to_s3(ds, records)
    print(f"Uploaded NDJSON for COPY INTO to {ndjson_path}")

    # Return NDJSON path for Snowflake load
    return ndjson_path


def run_load_to_snowflake(**context):
    """Load odds to Snowflake using COPY INTO from S3."""
    ti = context["ti"]
    ds = context["ds"]
    ndjson_path = ti.xcom_pull(task_ids="upload_to_s3")

    if not ndjson_path:
        print(f"No NDJSON path for {ds} - skipping Snowflake load")
        return {"ds": ds, "deleted": 0, "inserted": 0}

    result = load_odds_to_snowflake(ds, ndjson_path)
    print(f"Load result: {result}")
    return result


# ===========================================
# DAG Definition
# ===========================================
@dag(
    dag_id="nba_odds_daily_v9",
    description="Daily: Fetch NBA betting odds to S3 + Snowflake (INSERT...SELECT)",
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
    tags=["capstone", "nba-odds"],
)
def nba_odds_daily_dag():
    """
    Daily DAG to ingest NBA betting odds.

    Flow:
    1. Check if date is within NBA season (skip if off-season)
    2. Fetch odds from The Odds API (h2h, spreads, totals)
    3. Upload to S3 (JSON archive + NDJSON for fast loading)
    4. Load to Snowflake with COPY INTO from S3 (10-50x faster)
    """
    check_season = ShortCircuitOperator(
        task_id="check_nba_season",
        python_callable=run_check_season,
    )

    fetch_odds = PythonOperator(
        task_id="fetch_odds",
        python_callable=run_fetch_odds,
    )

    upload_to_s3 = PythonOperator(
        task_id="upload_to_s3",
        python_callable=run_upload_to_s3,
    )

    load_to_snowflake = PythonOperator(
        task_id="load_to_snowflake",
        python_callable=run_load_to_snowflake,
    )

    check_season >> fetch_odds >> upload_to_s3 >> load_to_snowflake


nba_odds_daily_dag()
