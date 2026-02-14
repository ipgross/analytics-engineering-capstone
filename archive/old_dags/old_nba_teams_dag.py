"""
NBA Teams DAG
Fetches team reference data from BallDontLie API and stores to S3 + Snowflake.

This is a one-time/manual refresh DAG for reference data.
Teams don't change often, so this can be run once at project start
and periodically refreshed if needed.

Data Source: BallDontLie API (https://api.balldontlie.io/v1/teams)
"""
from airflow.sdk import dag
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

from include.capstone.balldontlie_client import fetch_all_teams
from include.capstone.storage import upload_teams_to_s3, upload_teams_ndjson_to_s3
from include.capstone.database import load_teams_to_snowflake


# ===========================================
# Task Functions
# ===========================================
def run_fetch_teams(**context):
    """Fetch all NBA teams from BallDontLie API."""
    records, raw_response = fetch_all_teams()
    print(f"Fetched {len(records)} team records")

    context["ti"].xcom_push(key="raw_response", value=raw_response)
    return records


def run_upload_to_s3(**context):
    """Upload teams to S3 (JSON for archive + NDJSON for COPY INTO)."""
    ti = context["ti"]
    records = ti.xcom_pull(task_ids="fetch_teams")
    raw_response = ti.xcom_pull(task_ids="fetch_teams", key="raw_response")

    if not records:
        print("No team records - skipping S3 upload")
        return None

    # Upload JSON with metadata (for archiving)
    json_path = upload_teams_to_s3(records, raw_response)
    print(f"Uploaded JSON archive to {json_path}")

    # Upload NDJSON (for fast COPY INTO)
    ndjson_path = upload_teams_ndjson_to_s3(records)
    print(f"Uploaded NDJSON for COPY INTO to {ndjson_path}")

    return ndjson_path


def run_load_to_snowflake(**context):
    """Load teams to Snowflake using COPY INTO from S3."""
    ti = context["ti"]
    ndjson_path = ti.xcom_pull(task_ids="upload_to_s3")

    if not ndjson_path:
        print("No NDJSON path - skipping Snowflake load")
        return {"inserted": 0}

    result = load_teams_to_snowflake(ndjson_path)
    print(f"Load result: {result}")
    return result


# ===========================================
# DAG Definition
# ===========================================
@dag(
    dag_id="nba_teams_v1",
    description="One-time: Load NBA team reference data to S3 + Snowflake",
    default_args={
        "owner": "capstone",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=10),
    },
    start_date=datetime(2023, 10, 24),
    schedule=None,  # Manual trigger only
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["capstone", "nba-teams", "balldontlie"],
)
def nba_teams_dag():
    """
    One-time DAG to load NBA team reference data.

    Flow:
    1. Fetch teams from BallDontLie API
    2. Upload to S3 (JSON archive + NDJSON for fast loading)
    3. Load to Snowflake (TRUNCATE + INSERT)
    """
    fetch_teams = PythonOperator(
        task_id="fetch_teams",
        python_callable=run_fetch_teams,
    )

    upload_to_s3 = PythonOperator(
        task_id="upload_to_s3",
        python_callable=run_upload_to_s3,
    )

    load_to_snowflake = PythonOperator(
        task_id="load_to_snowflake",
        python_callable=run_load_to_snowflake,
    )

    fetch_teams >> upload_to_s3 >> load_to_snowflake


nba_teams_dag()
