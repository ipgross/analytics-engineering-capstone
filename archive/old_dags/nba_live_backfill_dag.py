"""
NBA Live Backfill DAG (Hot Path Recovery)

Manual-trigger DAG to repair live tables after an Astronomer outage.
Fetches final game data from BallDontLie API and MERGEs into live tables.

Does NOT backfill odds — completed games disappear from the Odds API.
Existing odds in live_nba_odds represent the last captured line and
persist until the 2-day cleanup cycle.

Pattern: validate params → fetch API (concurrent) → MERGE FROM VALUES (single conn)
Schedule: None (manual trigger)
Source: BallDontLie API (games, box_scores, plays)
Tables: live_nba_scoreboard, live_nba_player_box_scores, live_nba_plays
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from airflow.models.param import Param
from airflow.sdk import dag
from airflow.providers.standard.operators.python import PythonOperator, ShortCircuitOperator

from include.capstone.config import is_nba_season
from include.capstone.balldontlie_client import (
    fetch_live_games,
    fetch_live_box_scores,
    fetch_live_plays,
)
from include.capstone.database import (
    get_snowflake_connection,
    merge_live_scoreboard,
    merge_live_box_scores,
    merge_live_plays,
    log_ingestion_run,
)
from include.capstone.callbacks import alert_on_failure

logger = logging.getLogger(__name__)

DAG_ID = "nba_live_backfill_v1"


def run_validate_params(**context):
    """Validate game_date parameter. Short-circuit if invalid or off-season."""
    game_date = context["params"]["game_date"]

    try:
        datetime.strptime(game_date, "%Y-%m-%d")
    except ValueError:
        logger.error(f"Invalid date format: {game_date}. Expected YYYY-MM-DD")
        return False

    if not is_nba_season(game_date):
        logger.warning(f"Date {game_date} is outside NBA season. Skipping.")
        return False

    today = datetime.now().strftime("%Y-%m-%d")
    if game_date > today:
        logger.error(f"Date {game_date} is in the future. Cannot backfill.")
        return False

    logger.info(f"validate_params | game_date={game_date} | valid=True")
    return True


def run_backfill_live_data(**context):
    """
    Backfill live tables for a single game date.

    Single task with single Snowflake connection for speed.
    Follows the same pattern as nba_live_scoreboard_v2:run_ingest_scores.
    """
    game_date = context["params"]["game_date"]
    t0 = time.monotonic()

    logger.info(f"backfill_live_data | game_date={game_date} | starting")

    # Phase 1: Fetch games + box scores concurrently
    all_games = []
    all_box_scores = []

    with ThreadPoolExecutor(max_workers=4) as pool:
        game_future = pool.submit(fetch_live_games, game_date)
        box_future = pool.submit(fetch_live_box_scores, game_date)

        all_games = game_future.result()
        all_box_scores = box_future.result()

    logger.info(
        f"backfill_live_data | game_date={game_date}"
        f" | games={len(all_games)} | box_scores={len(all_box_scores)}"
    )

    if not all_games:
        logger.warning(f"No games found for {game_date}. Nothing to backfill.")
        log_ingestion_run(game_date, "live_backfill", DAG_ID, "EMPTY_EXPECTED", rows_merged=0)
        return {"game_date": game_date, "status": "no_games"}

    # Extract all game_ids for plays (fetch all — outage may have left partial data)
    game_ids = [g["game_id"] for g in all_games if g.get("game_id")]

    # Phase 2: Fetch plays concurrently for all games
    all_plays = []
    if game_ids:
        with ThreadPoolExecutor(max_workers=8) as pool:
            play_futures = {
                pool.submit(fetch_live_plays, gid): gid
                for gid in game_ids
            }
            for f in as_completed(play_futures):
                try:
                    all_plays.extend(f.result())
                except Exception as e:
                    gid = play_futures[f]
                    logger.warning(f"Failed to fetch plays for game {gid}: {e}")

    logger.info(
        f"backfill_live_data | game_date={game_date}"
        f" | plays={len(all_plays)} | game_ids={len(game_ids)}"
    )

    # Phase 3: MERGE all data (single connection, sequential)
    conn = get_snowflake_connection()
    try:
        scoreboard_result = merge_live_scoreboard(all_games, conn=conn)
        box_result = merge_live_box_scores(all_box_scores, conn=conn)
        plays_result = merge_live_plays(all_plays, conn=conn) if all_plays else {"merged": 0}
    finally:
        conn.close()

    elapsed = time.monotonic() - t0
    total_merged = (
        scoreboard_result.get("merged", 0)
        + box_result.get("merged", 0)
        + plays_result.get("merged", 0)
    )

    log_ingestion_run(
        game_date, "live_backfill", DAG_ID, "SUCCESS",
        rows_merged=total_merged, elapsed_sec=round(elapsed, 2),
    )

    summary = {
        "game_date": game_date,
        "scoreboard": scoreboard_result,
        "box_scores": box_result,
        "plays": plays_result,
        "elapsed_sec": round(elapsed, 2),
    }
    print(
        f"Scoreboard: {scoreboard_result.get('merged', 0)} merged | "
        f"Box scores: {box_result.get('merged', 0)} merged | "
        f"Plays: {plays_result.get('merged', 0)} merged | "
        f"Elapsed: {elapsed:.1f}s"
    )
    return summary


@dag(
    dag_id=DAG_ID,
    description="Manual backfill for live tables after outage (hot path recovery)",
    default_args={
        "owner": "capstone",
        "retries": 2,
        "retry_delay": timedelta(minutes=2),
        "execution_timeout": timedelta(minutes=30),
        "on_failure_callback": alert_on_failure,
    },
    start_date=datetime(2025, 10, 21),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["capstone", "nba", "live", "backfill", "hot-path"],
    params={
        "game_date": Param(
            "2026-02-10",
            type="string",
            description="Game date to backfill (YYYY-MM-DD)",
        ),
    },
)
def nba_live_backfill():
    validate = ShortCircuitOperator(
        task_id="validate_params",
        python_callable=run_validate_params,
    )
    backfill = PythonOperator(
        task_id="backfill_live_data",
        python_callable=run_backfill_live_data,
    )

    validate >> backfill


nba_live_backfill()
