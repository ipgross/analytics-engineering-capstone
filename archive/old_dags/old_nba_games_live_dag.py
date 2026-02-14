"""
NBA Games Live DAG
Near-realtime ingestion of game results as they complete.

Data Source: BallDontLie API (https://api.balldontlie.io/v1/games)

Purpose:
- Fetch completed games during game hours (7pm-2am EST)
- Enables near-realtime spread cover analysis
- Works alongside daily DAG which catches any stragglers

Schedule: Every 30 minutes from 7pm-2am EST (midnight-7am UTC)
- Games typically run 7pm-1am EST
- 30-min intervals balance freshness vs API calls

Key Differences from Daily DAG:
- Uses current Eastern date (not Airflow's ds)
- Runs multiple times per day
- Only during game hours
- Daily DAG catches anything missed

Idempotent: Re-running produces identical results (DELETE + INSERT by date).
"""
from airflow.sdk import dag
from airflow.providers.standard.operators.python import PythonOperator, ShortCircuitOperator
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from include.capstone.config import is_nba_season
from include.capstone.balldontlie_client import fetch_games_for_date
from include.capstone.storage import upload_games_to_s3, upload_games_ndjson_to_s3
from include.capstone.database import load_games_to_snowflake

EASTERN = ZoneInfo("America/New_York")


# ===========================================
# Task Functions
# ===========================================
def get_current_game_date() -> str:
    """
    Get the current game date in Eastern time.

    NBA games that start in the evening are attributed to that calendar date,
    even if they end after midnight. So a game starting at 10:30pm EST on Jan 15
    that ends at 1am EST on Jan 16 is still a "Jan 15" game.

    We use the current Eastern date, but if it's before 5am EST, we assume
    we're still processing yesterday's games.
    """
    now_et = datetime.now(EASTERN)

    # If it's before 5am EST, we're still in "yesterday's" game window
    if now_et.hour < 5:
        game_date = (now_et - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        game_date = now_et.strftime("%Y-%m-%d")

    return game_date


def run_check_season(**context):
    """
    Check if current game date is within NBA season.
    Returns True to continue, False to skip downstream tasks.
    """
    game_date = get_current_game_date()
    in_season = is_nba_season(game_date)

    if not in_season:
        print(f"{game_date} is off-season - skipping DAG execution")
    else:
        print(f"{game_date} is within NBA season - proceeding")

    # Store game_date for downstream tasks
    context["ti"].xcom_push(key="game_date", value=game_date)
    return in_season


def run_fetch_games(**context):
    """Fetch completed games from BallDontLie API."""
    ti = context["ti"]
    game_date = ti.xcom_pull(task_ids="check_nba_season", key="game_date")

    records, raw_response = fetch_games_for_date(game_date)
    print(f"Fetched {len(records)} completed game records for {game_date}")

    if not records:
        print(f"No Final games yet for {game_date} - will retry next run")

    ti.xcom_push(key="raw_response", value=raw_response)
    ti.xcom_push(key="game_date", value=game_date)
    return records


def run_upload_to_s3(**context):
    """Upload games to S3 (JSON for archive + NDJSON for COPY INTO)."""
    ti = context["ti"]
    records = ti.xcom_pull(task_ids="fetch_games")
    raw_response = ti.xcom_pull(task_ids="fetch_games", key="raw_response")
    game_date = ti.xcom_pull(task_ids="fetch_games", key="game_date")

    if not records:
        print(f"No game records for {game_date} - skipping S3 upload")
        ti.xcom_push(key="game_date", value=game_date)
        return None

    # Upload JSON with metadata (for archiving)
    json_path = upload_games_to_s3(game_date, records, raw_response)
    print(f"Uploaded JSON archive to {json_path}")

    # Upload NDJSON (for fast COPY INTO)
    ndjson_path = upload_games_ndjson_to_s3(game_date, records)
    print(f"Uploaded NDJSON for COPY INTO to {ndjson_path}")

    ti.xcom_push(key="game_date", value=game_date)
    return ndjson_path


def run_load_to_snowflake(**context):
    """Load games to Snowflake using COPY INTO from S3."""
    ti = context["ti"]
    ndjson_path = ti.xcom_pull(task_ids="upload_to_s3")
    game_date = ti.xcom_pull(task_ids="upload_to_s3", key="game_date")

    if not ndjson_path:
        print(f"No NDJSON path for {game_date} - skipping Snowflake load")
        return {"ds": game_date, "deleted": 0, "inserted": 0}

    result = load_games_to_snowflake(game_date, ndjson_path)
    print(f"Load result: {result}")
    return result


# ===========================================
# DAG Definition
# ===========================================
@dag(
    dag_id="nba_games_live_v1",
    description="Live: Fetch completed NBA games every 30 min during game hours",
    default_args={
        "owner": "capstone",
        "retries": 1,
        "retry_delay": timedelta(minutes=2),
        "execution_timeout": timedelta(minutes=10),
    },
    start_date=datetime(2025, 1, 1),  # Start from current season
    schedule="*/30 0-7 * * *",  # Every 30 min, midnight-7am UTC (7pm-2am EST)
    catchup=False,  # Don't backfill - daily DAG handles that
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["capstone", "nba-games", "balldontlie", "live"],
)
def nba_games_live_dag():
    """
    Live DAG to ingest NBA game results as they complete.

    Flow:
    1. Check if current game date is within NBA season
    2. Fetch completed games from BallDontLie API (status="Final" only)
    3. Upload to S3 (JSON archive + NDJSON for fast loading)
    4. Load to Snowflake with COPY INTO from S3

    Key behavior:
    - Uses current Eastern date (not Airflow's ds)
    - Only processes games with status="Final"
    - Safe to run multiple times (idempotent DELETE + INSERT)
    - If no Final games yet, gracefully skips and retries next run
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


nba_games_live_dag()
