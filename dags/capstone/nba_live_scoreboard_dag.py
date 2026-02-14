"""
NBA Live Scoreboard DAG (Hot Path)

Real-time scoreboard, box scores, and play-by-play updates during game hours.
Single task for speed — no S3, no staging, no DQ. Direct API → MERGE.

Event-driven trigger: detects games transitioning to Final status and triggers
nba_finalize_games → nba_dbt_finalize chain for authoritative data processing.

Pattern: fetch → Python validation → MERGE FROM VALUES → detect Final → trigger finalize
Trigger: Uses TriggerDagRunOperator to trigger nba_finalize_games when games go Final.
Safety: MERGE from empty = 0 changes. Table always has data.
        Finalize trigger is non-fatal — 3am safety net catches misses.

Schedule: Every 1 minute during game hours (11am-2am ET)
Source: BallDontLie API (games, box_scores, plays)
Tables: live_nba_scoreboard, live_nba_player_box_scores, live_nba_plays
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from airflow.sdk import dag
from airflow.providers.standard.operators.python import PythonOperator, ShortCircuitOperator
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator

from include.capstone.config import (
    is_nba_season,
    is_game_window,
    get_live_game_dates,
    LIVE_PLAYS_TABLE,
    LIVE_SCOREBOARD_TABLE,
)
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
    cleanup_live_tables,
)
from include.capstone.callbacks import alert_on_failure

logger = logging.getLogger(__name__)

DAG_ID = "nba_live_scoreboard_v3"


def run_check_game_window(**context):
    """Short-circuit if outside game hours or off-season."""
    now_et = datetime.now()
    today = now_et.strftime("%Y-%m-%d")
    in_season = is_nba_season(today)
    in_window = is_game_window()
    logger.info(f"check_game_window | in_season={in_season} | in_window={in_window}")
    return in_season and in_window


def run_ingest_scores(**context):
    """
    Fetch and MERGE scoreboard, box scores, and plays.

    Single task with single Snowflake connection for speed.
    All API fetches run concurrently via ThreadPoolExecutor.
    """
    dates = get_live_game_dates()
    logger.info(f"ingest_scores | dates={dates}")

    # Phase 1: Fetch games + box scores concurrently across all dates
    all_games = []
    all_box_scores = []

    with ThreadPoolExecutor(max_workers=8) as pool:
        game_futures = {pool.submit(fetch_live_games, d): d for d in dates}
        box_futures = {pool.submit(fetch_live_box_scores, d): d for d in dates}

        for f in as_completed(game_futures):
            all_games.extend(f.result())
        for f in as_completed(box_futures):
            all_box_scores.extend(f.result())

    # Single connection for plays check + all MERGEs
    conn = get_snowflake_connection()
    try:
        # Snapshot current game statuses BEFORE merge (for Final detection)
        pre_status = {}
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT game_id, status FROM {LIVE_SCOREBOARD_TABLE}")
            pre_status = {row[0]: row[1] for row in cursor.fetchall()}
            cursor.close()
        except Exception:
            pass  # First run or empty table — all games will be "new"

        # Query which game_ids already have plays (one cheap query)
        # so we can skip re-fetching Final games we already captured.
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT DISTINCT game_id FROM {LIVE_PLAYS_TABLE}")
            games_with_plays = {row[0] for row in cursor.fetchall()}
            cursor.close()
        except Exception:
            games_with_plays = set()

        # Determine which games need play-by-play
        active_game_ids = []
        for game in all_games:
            status = game.get("status", "")
            game_id = game.get("game_id")
            if not game_id:
                continue
            # Skip scheduled games (status is a time string like "7:00 pm ET")
            if "pm" in status.lower() or "am" in status.lower():
                continue
            # Final: only fetch if we don't already have plays for this game
            if status == "Final" and game_id in games_with_plays:
                continue
            active_game_ids.append(game_id)

        # Phase 2: Fetch plays concurrently across all active games
        all_plays = []
        if active_game_ids:
            with ThreadPoolExecutor(max_workers=8) as pool:
                play_futures = {
                    pool.submit(fetch_live_plays, gid): gid
                    for gid in active_game_ids
                }
                for f in as_completed(play_futures):
                    try:
                        all_plays.extend(f.result())
                    except Exception as e:
                        gid = play_futures[f]
                        logger.warning(f"Failed to fetch plays for game {gid}: {e}")

        # Phase 3: MERGE all data (sequential, same connection)
        scoreboard_result = merge_live_scoreboard(all_games, conn=conn)
        box_result = merge_live_box_scores(all_box_scores, conn=conn)
        plays_result = merge_live_plays(all_plays, conn=conn) if all_plays else {"merged": 0}

        # Phase 4: Detect newly-Final games and trigger nba_finalize_games
        post_status = {
            r["game_id"]: r["status"]
            for r in all_games
            if r.get("game_id")
        }
        newly_final = [
            gid for gid, status in post_status.items()
            if status == "Final" and pre_status.get(gid) != "Final"
        ]

        if newly_final:
            now_et = datetime.now(ZoneInfo("America/New_York"))
            today_et = now_et.strftime("%Y-%m-%d")
            context["ti"].xcom_push(key="trigger_game_date", value=today_et)
            logger.info(
                f"newly_final_detected | game_ids={newly_final}"
                f" | game_date={today_et}"
            )

        print(
            f"Scoreboard: {scoreboard_result.get('merged', 0)} merged | "
            f"Box scores: {box_result.get('merged', 0)} merged | "
            f"Plays: {plays_result.get('merged', 0)} merged"
            f"{f' | newly_final={newly_final}' if newly_final else ''}"
        )
        return {
            "scoreboard": scoreboard_result,
            "box_scores": box_result,
            "plays": plays_result,
            "newly_final": newly_final,
        }
    finally:
        conn.close()


def run_check_newly_final(**context):
    """Short-circuit if no games transitioned to Final in this run."""
    trigger_game_date = context["ti"].xcom_pull(
        task_ids="ingest_scores", key="trigger_game_date"
    )
    if trigger_game_date:
        logger.info(f"check_newly_final | game_date={trigger_game_date} | triggering finalize")
        return True
    return False


def run_cleanup(**context):
    """
    Clean up old data from live tables.

    Only executes at the top of the hour (minute == 0).
    Otherwise returns immediately.
    """
    now = datetime.now()
    if now.minute != 0:
        print(f"Skipping cleanup (minute={now.minute}, only runs at :00)")
        return {"skipped": True}

    result = cleanup_live_tables(max_age_days=2)
    print(f"Cleanup result: {result}")
    return result


@dag(
    dag_id=DAG_ID,
    description="Live scoreboard + box scores + plays (hot path, every 1 min)",
    default_args={
        "owner": "capstone",
        "retries": 0,
        "execution_timeout": timedelta(seconds=55),
        "on_failure_callback": alert_on_failure,
    },
    start_date=datetime(2025, 10, 21),
    schedule="* * * * *",
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["capstone", "nba", "live", "hot-path"],
)
def nba_live_scoreboard():
    check = ShortCircuitOperator(
        task_id="check_game_window",
        python_callable=run_check_game_window,
    )
    ingest = PythonOperator(
        task_id="ingest_scores",
        python_callable=run_ingest_scores,
    )
    cleanup = PythonOperator(
        task_id="cleanup_old_data",
        python_callable=run_cleanup,
    )
    check_final = ShortCircuitOperator(
        task_id="check_newly_final",
        python_callable=run_check_newly_final,
    )
    trigger_finalize = TriggerDagRunOperator(
        task_id="trigger_finalize",
        trigger_dag_id="nba_finalize_games_v3",
        conf={
            "game_date": "{{ ti.xcom_pull(task_ids='ingest_scores', key='trigger_game_date') }}",
            "triggered_by": "live_scoreboard",
        },
        wait_for_completion=False,
        reset_dag_run=True,
        retries=1,
        retry_delay=timedelta(minutes=1),
    )

    check >> ingest >> [cleanup, check_final]
    check_final >> trigger_finalize


nba_live_scoreboard()
