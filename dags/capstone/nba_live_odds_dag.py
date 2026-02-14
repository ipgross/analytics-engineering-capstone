"""
NBA Live Odds DAG (Hot Path)

Fetches current odds from The Odds API every 5 minutes during game hours.
Archives each snapshot to track line movement over time.

Pattern: fetch → Python validation → MERGE FROM VALUES → snapshot archive
Safety: MERGE from empty = 0 changes. Completed games disappear from API
        but rows persist (MERGE never deletes).

Schedule: Every 5 minutes during game hours (11am-2am ET)
Source: The Odds API (odds endpoint)
Tables: live_nba_odds, archive_nba_odds_snapshots
Cost: 3 credits/call × 12 calls/hour × ~5 hours = ~180 credits/game day
"""
import logging
from datetime import datetime, timedelta

from airflow.sdk import dag
from airflow.providers.standard.operators.python import PythonOperator, ShortCircuitOperator

from include.capstone.config import is_nba_season, is_game_window
from include.capstone.api_client import fetch_live_odds
from include.capstone.database import (
    merge_live_odds,
    snapshot_live_odds,
)
from include.capstone.callbacks import alert_on_failure

logger = logging.getLogger(__name__)

DAG_ID = "nba_live_odds_v3"


def run_check_game_window(**context):
    """Short-circuit if outside game hours or off-season."""
    now_et = datetime.now()
    today = now_et.strftime("%Y-%m-%d")
    in_season = is_nba_season(today)
    in_window = is_game_window()
    logger.info(f"check_game_window | in_season={in_season} | in_window={in_window}")
    return in_season and in_window


def run_ingest_odds(**context):
    """
    Fetch current odds, MERGE into live table, snapshot to archive.

    Single task for speed. Archive is non-fatal (failure doesn't crash run).
    """
    # Fetch all current odds
    records = fetch_live_odds()
    print(f"Fetched {len(records)} odds records")

    # MERGE into live table
    merge_result = merge_live_odds(records)
    print(f"Merge result: {merge_result}")

    # Snapshot to archive (non-fatal)
    snapshot_result = snapshot_live_odds()
    print(f"Snapshot result: {snapshot_result}")

    return {
        "merge": merge_result,
        "snapshot": snapshot_result,
    }


@dag(
    dag_id=DAG_ID,
    description="Live odds from The Odds API + line movement archive (hot path, every 5 min)",
    default_args={
        "owner": "capstone",
        "retries": 0,
        "execution_timeout": timedelta(minutes=4),
        "on_failure_callback": alert_on_failure,
    },
    start_date=datetime(2025, 10, 21),
    schedule="*/5 * * * *",
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["capstone", "nba", "live", "odds", "hot-path"],
)
def nba_live_odds():
    check = ShortCircuitOperator(
        task_id="check_game_window",
        python_callable=run_check_game_window,
    )
    ingest = PythonOperator(
        task_id="ingest_odds",
        python_callable=run_ingest_odds,
    )

    check >> ingest


nba_live_odds()
