"""
NBA Finalize Games DAG (Cold Path)

Fetches final scores + player box scores from BallDontLie.
Games and box scores run in parallel branches, each with stage → DQ → MERGE.
Postponed detection marks events with no matching game after merge.
After both branches complete, triggers nba_dbt_finalize for transformations.

Supports two trigger modes:
  - Scheduled (3am ET): uses ds - 1 as game_date (yesterday's completed games)
  - Event-triggered: accepts game_date via dag_run.conf (from live scoreboard DAG)

Pattern: fetch → S3 → stage → DQ → MERGE → mark_postponed → ops log → trigger dbt
Idempotency: MERGE (atomic upsert), staging cleared per-date. Safe to re-trigger.

Schedule: Daily at 3am ET (08:00 UTC) + event-triggered by live scoreboard
Source: BallDontLie API (games + box_scores endpoints)
Tables: hist_nba_games, hist_nba_player_box_scores
"""
import logging
from datetime import datetime, timedelta

from airflow.sdk import dag
from airflow.providers.standard.operators.python import PythonOperator, ShortCircuitOperator
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator

from include.capstone.config import is_nba_season
from include.capstone.balldontlie_client import (
    fetch_games_for_date,
    fetch_box_scores_for_date,
)
from include.capstone.storage import (
    upload_archive,
    upload_bulk,
    build_games_archive_payload,
    build_box_scores_archive_payload,
)
from include.capstone.database import (
    get_snowflake_connection,
    stage_games,
    stage_box_scores,
    validate_games,
    validate_box_scores,
    merge_games,
    merge_box_scores,
    mark_postponed_events,
    classify_empty,
    log_ingestion_run,
)
from include.capstone.config import (
    HIST_EVENTS_TABLE,
    OPS_TABLE,
)
from include.capstone.callbacks import alert_on_failure

logger = logging.getLogger(__name__)

DAG_ID = "nba_finalize_games_v3"


def _game_date(context) -> str:
    """Get game date: from dag_run.conf (event-triggered) or ds-1 (scheduled).

    Event-triggered runs pass game_date explicitly via conf when the live
    scoreboard DAG detects a game going Final.  Scheduled runs at 3am ET
    use ds - 1 (yesterday's completed games).
    """
    dag_run = context.get("dag_run")
    if dag_run and getattr(dag_run, "conf", None) and dag_run.conf.get("game_date"):
        return dag_run.conf["game_date"]
    ds = context["ds"]
    return (datetime.strptime(ds, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")


def run_check_season(**context):
    return is_nba_season(_game_date(context))


def run_wait_for_events(**context):
    """Ensure events data is loaded before proceeding.

    Events DAG loads events via data_interval_end. Reconcile processes
    ds - 1 (yesterday). Events for yesterday were loaded ~20 hours ago,
    so this should pass immediately. Safety net in case events DAG failed.
    """
    game_date = _game_date(context)
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {HIST_EVENTS_TABLE} WHERE ds = '{game_date}'")
        event_count = cursor.fetchone()[0]
        if event_count > 0:
            logger.info(f"wait_for_events | game_date={game_date} | events={event_count} | ready")
            return event_count

        # Off-day: events DAG ran but found 0 events (EMPTY_EXPECTED)
        cursor.execute(f"""
            SELECT COUNT(*) FROM {OPS_TABLE}
            WHERE ds = '{game_date}' AND dataset = 'events'
            AND status IN ('SUCCESS', 'EMPTY_EXPECTED')
        """)
        if cursor.fetchone()[0] > 0:
            logger.info(f"wait_for_events | game_date={game_date} | events=0 (off-day) | ready")
            return 0

        raise ValueError(
            f"Events data not loaded for game_date={game_date}. "
            f"Waiting for nba_ingest_events DAG to complete."
        )
    finally:
        cursor.close()
        conn.close()


# ===========================================
# Games branch
# ===========================================

def run_fetch_games(**context):
    game_date = _game_date(context)
    records, raw_response = fetch_games_for_date(game_date)
    context["ti"].xcom_push(key="raw_response", value=raw_response)
    print(f"Fetched {len(records)} games for {game_date}")
    return records


def run_upload_games_archive(**context):
    ti = context["ti"]
    game_date = _game_date(context)
    records = ti.xcom_pull(task_ids="fetch_games")
    raw_response = ti.xcom_pull(task_ids="fetch_games", key="raw_response")
    if not records:
        return None
    payload = build_games_archive_payload(game_date, records, raw_response)
    return upload_archive("games", payload, date_str=game_date)


def run_upload_games_bulk(**context):
    ti = context["ti"]
    game_date = _game_date(context)
    records = ti.xcom_pull(task_ids="fetch_games")
    return upload_bulk("games", records, date_str=game_date)


def run_stage_games(**context):
    ti = context["ti"]
    game_date = _game_date(context)
    bulk_path = ti.xcom_pull(task_ids="upload_games_bulk")
    records = ti.xcom_pull(task_ids="fetch_games")

    if not records:
        status = classify_empty(game_date, "games")
        log_ingestion_run(game_date, "games", DAG_ID, status, rows_merged=0)
        print(f"Empty games for {game_date}: {status}")
        if status == "EMPTY_UNEXPECTED":
            raise ValueError(f"EMPTY_UNEXPECTED: events exist for {game_date} but 0 games returned")
        return {"ds": game_date, "staged": 0, "status": status}

    result = stage_games(game_date, bulk_path)
    print(f"Stage games result: {result}")
    return result


def run_dq_games(**context):
    ti = context["ti"]
    game_date = _game_date(context)
    stage_result = ti.xcom_pull(task_ids="stage_games")
    if stage_result.get("staged", 0) == 0:
        print(f"Skipping games DQ — no staged data for {game_date}")
        return
    validate_games(game_date)


def run_merge_games(**context):
    ti = context["ti"]
    game_date = _game_date(context)
    stage_result = ti.xcom_pull(task_ids="stage_games")
    if stage_result.get("staged", 0) == 0:
        print(f"Skipping games merge — no staged data for {game_date}")
        return {"ds": game_date, "merged": 0}
    result = merge_games(game_date)
    print(f"Merge games result: {result}")
    return result


def run_mark_postponed(**context):
    """Mark events with no matching game as postponed (retroactive detection).

    Always runs after merge_games regardless of staged count — ensures
    previously postponed events get reset to FALSE if games are found on re-run.
    """
    game_date = _game_date(context)
    result = mark_postponed_events(game_date)
    print(f"Mark postponed result: {result}")
    return result


def run_log_games(**context):
    ti = context["ti"]
    game_date = _game_date(context)
    stage_result = ti.xcom_pull(task_ids="stage_games")

    if stage_result.get("status"):
        return

    merge_result = ti.xcom_pull(task_ids="merge_games") or {}
    archive_path = ti.xcom_pull(task_ids="upload_games_archive")
    bulk_path = ti.xcom_pull(task_ids="upload_games_bulk")

    log_ingestion_run(
        date_str=game_date,
        dataset="games",
        dag_id=DAG_ID,
        status="SUCCESS",
        rows_merged=merge_result.get("merged", 0),
        s3_archive_path=archive_path,
        s3_bulk_path=bulk_path,
    )


# ===========================================
# Box scores branch
# ===========================================

def run_fetch_box_scores(**context):
    game_date = _game_date(context)
    records, raw_response = fetch_box_scores_for_date(game_date)
    context["ti"].xcom_push(key="raw_response", value=raw_response)
    print(f"Fetched {len(records)} player box scores for {game_date}")
    return records


def run_upload_box_archive(**context):
    ti = context["ti"]
    game_date = _game_date(context)
    records = ti.xcom_pull(task_ids="fetch_box_scores")
    raw_response = ti.xcom_pull(task_ids="fetch_box_scores", key="raw_response")
    if not records:
        return None
    payload = build_box_scores_archive_payload(game_date, records, raw_response)
    return upload_archive("box_scores", payload, date_str=game_date)


def run_upload_box_bulk(**context):
    ti = context["ti"]
    game_date = _game_date(context)
    records = ti.xcom_pull(task_ids="fetch_box_scores")
    return upload_bulk("box_scores", records, date_str=game_date)


def run_stage_box(**context):
    ti = context["ti"]
    game_date = _game_date(context)
    bulk_path = ti.xcom_pull(task_ids="upload_box_bulk")
    records = ti.xcom_pull(task_ids="fetch_box_scores")

    if not records:
        status = classify_empty(game_date, "box_scores")
        log_ingestion_run(game_date, "box_scores", DAG_ID, status, rows_merged=0)
        print(f"Empty box scores for {game_date}: {status}")
        if status == "EMPTY_UNEXPECTED":
            raise ValueError(f"EMPTY_UNEXPECTED: events exist for {game_date} but 0 box scores returned")
        return {"ds": game_date, "staged": 0, "status": status}

    result = stage_box_scores(game_date, bulk_path)
    print(f"Stage box scores result: {result}")
    return result


def run_dq_box(**context):
    ti = context["ti"]
    game_date = _game_date(context)
    stage_result = ti.xcom_pull(task_ids="stage_box")
    if stage_result.get("staged", 0) == 0:
        print(f"Skipping box scores DQ — no staged data for {game_date}")
        return
    validate_box_scores(game_date)


def run_merge_box(**context):
    ti = context["ti"]
    game_date = _game_date(context)
    stage_result = ti.xcom_pull(task_ids="stage_box")
    if stage_result.get("staged", 0) == 0:
        print(f"Skipping box scores merge — no staged data for {game_date}")
        return {"ds": game_date, "merged": 0}
    result = merge_box_scores(game_date)
    print(f"Merge box scores result: {result}")
    return result


def run_log_box(**context):
    ti = context["ti"]
    game_date = _game_date(context)
    stage_result = ti.xcom_pull(task_ids="stage_box")

    if stage_result.get("status"):
        return

    merge_result = ti.xcom_pull(task_ids="merge_box") or {}
    archive_path = ti.xcom_pull(task_ids="upload_box_archive")
    bulk_path = ti.xcom_pull(task_ids="upload_box_bulk")

    log_ingestion_run(
        date_str=game_date,
        dataset="box_scores",
        dag_id=DAG_ID,
        status="SUCCESS",
        rows_merged=merge_result.get("merged", 0),
        s3_archive_path=archive_path,
        s3_bulk_path=bulk_path,
    )


@dag(
    dag_id=DAG_ID,
    description="Finalize games: final scores + box scores + postponed detection (cold path)",
    default_args={
        "owner": "capstone",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=30),
        "on_failure_callback": alert_on_failure,
    },
    start_date=datetime(2023, 10, 24),
    schedule="0 8 * * *",
    catchup=False,
    max_active_runs=2,
    is_paused_upon_creation=False,
    tags=["capstone", "nba", "finalize", "cold-path"],
)
def nba_finalize_games():
    check = ShortCircuitOperator(
        task_id="check_nba_season",
        python_callable=run_check_season,
    )

    wait = PythonOperator(
        task_id="wait_for_events",
        python_callable=run_wait_for_events,
        retries=6,
        retry_delay=timedelta(minutes=10),
        execution_timeout=timedelta(minutes=2),
    )

    # Games branch
    fetch_games_task = PythonOperator(task_id="fetch_games", python_callable=run_fetch_games)
    games_archive = PythonOperator(task_id="upload_games_archive", python_callable=run_upload_games_archive)
    games_bulk = PythonOperator(task_id="upload_games_bulk", python_callable=run_upload_games_bulk)
    stage_games_task = PythonOperator(task_id="stage_games", python_callable=run_stage_games)
    dq_games = PythonOperator(task_id="dq_games", python_callable=run_dq_games)
    merge_games_task = PythonOperator(task_id="merge_games", python_callable=run_merge_games)
    log_games = PythonOperator(task_id="log_games", python_callable=run_log_games)

    # Box scores branch
    fetch_box = PythonOperator(task_id="fetch_box_scores", python_callable=run_fetch_box_scores)
    box_archive = PythonOperator(task_id="upload_box_archive", python_callable=run_upload_box_archive)
    box_bulk = PythonOperator(task_id="upload_box_bulk", python_callable=run_upload_box_bulk)
    stage_box_task = PythonOperator(task_id="stage_box", python_callable=run_stage_box)
    dq_box = PythonOperator(task_id="dq_box", python_callable=run_dq_box)
    merge_box_task = PythonOperator(task_id="merge_box", python_callable=run_merge_box)
    log_box = PythonOperator(task_id="log_box", python_callable=run_log_box)

    # Postponed detection (after games merge)
    mark_postponed = PythonOperator(task_id="mark_postponed", python_callable=run_mark_postponed)

    # Trigger dbt finalize after both branches complete
    trigger_dbt = TriggerDagRunOperator(
        task_id="trigger_dbt_finalize",
        trigger_dag_id="nba_dbt_finalize_v3",
        conf={"game_date": "{{ dag_run.conf.get('game_date', '') }}"},
        wait_for_completion=False,
        reset_dag_run=True,
        retries=1,
        retry_delay=timedelta(minutes=1),
    )

    # Task dependencies
    check >> wait >> [fetch_games_task, fetch_box]

    (fetch_games_task >> [games_archive, games_bulk]
     >> stage_games_task >> dq_games >> merge_games_task
     >> mark_postponed >> log_games)
    fetch_box >> [box_archive, box_bulk] >> stage_box_task >> dq_box >> merge_box_task >> log_box

    # Chain dbt after both branches finish
    [log_games, log_box] >> trigger_dbt


nba_finalize_games()
