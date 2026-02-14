"""
NBA Upcoming Events & Odds DAG (Cold Path)

Fetches game schedule and odds for the next 7 days into hist_nba_events
and hist_nba_odds_open. Runs daily after the regular ingestion DAGs,
followed by a dbt rebuild to update mart_nba__game_predictions.

This enables the Streamlit dashboard to show predictions for upcoming
games during All-Star break, off-days, and multi-day lookahead.

Each future date is processed through the full cold-path pipeline
(fetch → S3 → stage → DQ → MERGE → ops log) individually, preserving
the single-date-per-staging-load constraint. Lines update daily as
bookmakers adjust; the regular odds DAG captures the authoritative
morning line on game day.

Pattern: For each date in [ds+1 .. ds+7] → fetch → S3 → stage → DQ → MERGE → log
Idempotency: MERGE (atomic upsert), staging cleared per-date.
Backfillable: Uses ds as base date, processes ds+1 through ds+7.

Schedule: Daily at 8am ET (13:00 UTC)
Source: The Odds API (events + odds endpoints)
Tables: hist_nba_events, hist_nba_odds_open
"""
import os
import time
import logging
from datetime import datetime, timedelta

from airflow.sdk import dag
from airflow.operators.empty import EmptyOperator
from airflow.providers.standard.operators.python import PythonOperator, ShortCircuitOperator
from cosmos import DbtTaskGroup, ProjectConfig, ProfileConfig, RenderConfig, ExecutionConfig
from cosmos.constants import TestBehavior
from dotenv import load_dotenv

from include.capstone.config import is_nba_season, HIST_EVENTS_TABLE
from include.capstone.api_client import fetch_events_for_date, fetch_odds_for_date
from include.capstone.storage import (
    upload_archive,
    upload_bulk,
    build_events_archive_payload,
    build_odds_archive_payload,
)
from include.capstone.database import (
    get_snowflake_connection,
    stage_events,
    validate_events,
    merge_events,
    stage_odds,
    validate_odds,
    merge_odds,
    log_ingestion_run,
)
from include.capstone.callbacks import alert_on_failure

logger = logging.getLogger(__name__)

DAG_ID = "nba_ingest_upcoming_v3"
DAYS_AHEAD = 7

# ===========================================
# Cosmos / dbt configuration (same as nba_dbt_daily)
# ===========================================
airflow_home = os.environ.get("AIRFLOW_HOME", "")

load_dotenv(os.path.join(airflow_home, "dbt_project", ".env"), override=False)
load_dotenv(os.path.join(airflow_home, "dbt_project", "dbt.env"), override=False)

os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"] = os.path.join(airflow_home, "rsa_key.p8")
os.environ["STUDENT_SCHEMA"] = "ipgross"

PATH_TO_DBT_PROJECT = os.path.join(airflow_home, "dbt_project")
PATH_TO_DBT_PROFILES = os.path.join(airflow_home, "dbt_project", "profiles.yml")

profile_config = ProfileConfig(
    profile_name="nba_betting_analytics",
    target_name="dev",
    profiles_yml_filepath=PATH_TO_DBT_PROFILES,
)

execution_config = ExecutionConfig(
    dbt_executable_path=os.path.join(airflow_home, "dbt_venv", "bin", "dbt"),
)


# ===========================================
# Task functions
# ===========================================


def run_check_season(**context):
    """Short-circuit if today (ds) is outside NBA season."""
    return is_nba_season(context["ds"])


def _has_events_for_date(target_date: str) -> bool:
    """Quick check if hist_nba_events has rows for a date (saves odds API credits)."""
    conn = get_snowflake_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT COUNT(*) FROM {HIST_EVENTS_TABLE} WHERE ds = '{target_date}'"
        )
        count = cursor.fetchone()[0]
        cursor.close()
        return count > 0
    finally:
        conn.close()


def run_ingest_upcoming_events(**context):
    """Fetch, upload, stage, validate, and merge events for next 7 days."""
    today = context["ds"]
    base_date = datetime.strptime(today, "%Y-%m-%d")

    results = []
    for offset in range(1, DAYS_AHEAD + 1):
        target_date = (base_date + timedelta(days=offset)).strftime("%Y-%m-%d")

        if not is_nba_season(target_date):
            logger.info(f"upcoming_events | ds={target_date} | skipped=outside_season")
            continue

        try:
            t0 = time.monotonic()

            # 1. Fetch events (FREE for future dates via regular endpoint)
            events = fetch_events_for_date(target_date)
            logger.info(
                f"upcoming_events | ds={target_date} | events={len(events)}"
            )

            if not events:
                log_ingestion_run(
                    target_date, "events", DAG_ID, "EMPTY_EXPECTED", rows_merged=0
                )
                results.append(
                    {"ds": target_date, "events": 0, "status": "EMPTY_EXPECTED"}
                )
                continue

            # 2. Upload archive (JSON.gz)
            today_et = datetime.now().strftime("%Y-%m-%d")
            endpoint = "historical" if target_date < today_et else "current"
            payload = build_events_archive_payload(target_date, events, endpoint)
            archive_path = upload_archive("events", payload, date_str=target_date)

            # 3. Upload bulk (Parquet)
            bulk_path = upload_bulk("events", events, date_str=target_date)

            # 4. Stage → DQ → Merge
            stage_events(target_date, bulk_path)
            validate_events(target_date)
            merge_result = merge_events(target_date)

            elapsed = time.monotonic() - t0

            # 5. Log ops
            log_ingestion_run(
                date_str=target_date,
                dataset="events",
                dag_id=DAG_ID,
                status="SUCCESS",
                rows_merged=merge_result.get("merged", 0),
                s3_archive_path=archive_path,
                s3_bulk_path=bulk_path,
                elapsed_sec=elapsed,
            )

            results.append(
                {
                    "ds": target_date,
                    "events": len(events),
                    "merged": merge_result.get("merged", 0),
                    "status": "SUCCESS",
                }
            )

        except Exception as e:
            logger.error(f"upcoming_events | ds={target_date} | error={e}")
            try:
                log_ingestion_run(
                    date_str=target_date,
                    dataset="events",
                    dag_id=DAG_ID,
                    status="FAILED",
                    rows_merged=0,
                    error_message=str(e),
                )
            except Exception:
                pass
            results.append(
                {"ds": target_date, "events": 0, "status": "FAILED", "error": str(e)}
            )

    logger.info(f"upcoming_events_summary | dates_processed={len(results)} | results={results}")
    return results


def run_ingest_upcoming_odds(**context):
    """Fetch, upload, stage, validate, and merge odds for next 7 days."""
    today = context["ds"]
    base_date = datetime.strptime(today, "%Y-%m-%d")

    results = []
    for offset in range(1, DAYS_AHEAD + 1):
        target_date = (base_date + timedelta(days=offset)).strftime("%Y-%m-%d")

        if not is_nba_season(target_date):
            logger.info(f"upcoming_odds | ds={target_date} | skipped=outside_season")
            continue

        # Cost optimization: skip odds API call if no events for this date
        if not _has_events_for_date(target_date):
            logger.info(
                f"upcoming_odds | ds={target_date} | skipped=no_events"
            )
            results.append(
                {"ds": target_date, "records": 0, "status": "SKIPPED_NO_EVENTS"}
            )
            continue

        try:
            t0 = time.monotonic()

            # 1. Fetch odds (3 credits per call via regular endpoint)
            records, raw_response = fetch_odds_for_date(target_date)
            logger.info(
                f"upcoming_odds | ds={target_date} | records={len(records)}"
            )

            if not records:
                log_ingestion_run(
                    target_date, "odds_open", DAG_ID, "EMPTY_EXPECTED", rows_merged=0
                )
                results.append(
                    {"ds": target_date, "records": 0, "status": "EMPTY_EXPECTED"}
                )
                continue

            # 2. Upload archive (JSON.gz)
            payload = build_odds_archive_payload(target_date, records, raw_response)
            archive_path = upload_archive("odds_open", payload, date_str=target_date)

            # 3. Upload bulk (Parquet)
            bulk_path = upload_bulk("odds_open", records, date_str=target_date)

            # 4. Stage → DQ → Merge
            stage_odds(target_date, bulk_path)
            validate_odds(target_date)
            merge_result = merge_odds(target_date)

            elapsed = time.monotonic() - t0

            # 5. Log ops
            log_ingestion_run(
                date_str=target_date,
                dataset="odds_open",
                dag_id=DAG_ID,
                status="SUCCESS",
                rows_merged=merge_result.get("merged", 0),
                s3_archive_path=archive_path,
                s3_bulk_path=bulk_path,
                elapsed_sec=elapsed,
            )

            results.append(
                {
                    "ds": target_date,
                    "records": len(records),
                    "merged": merge_result.get("merged", 0),
                    "status": "SUCCESS",
                }
            )

        except Exception as e:
            logger.error(f"upcoming_odds | ds={target_date} | error={e}")
            try:
                log_ingestion_run(
                    date_str=target_date,
                    dataset="odds_open",
                    dag_id=DAG_ID,
                    status="FAILED",
                    rows_merged=0,
                    error_message=str(e),
                )
            except Exception:
                pass
            results.append(
                {"ds": target_date, "records": 0, "status": "FAILED", "error": str(e)}
            )

    logger.info(f"upcoming_odds_summary | dates_processed={len(results)} | results={results}")
    return results


# ===========================================
# DAG definition
# ===========================================


@dag(
    dag_id=DAG_ID,
    description="Ingest events + odds for next 7 days, then rebuild dbt predictions",
    default_args={
        "owner": "capstone",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=45),
        "on_failure_callback": alert_on_failure,
    },
    start_date=datetime(2023, 10, 24),
    schedule="0 13 * * *",  # 8am ET = 13:00 UTC
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["capstone", "nba", "upcoming", "cold-path"],
)
def nba_ingest_upcoming():
    check = ShortCircuitOperator(
        task_id="check_nba_season",
        python_callable=run_check_season,
    )

    ingest_events = PythonOperator(
        task_id="ingest_upcoming_events",
        python_callable=run_ingest_upcoming_events,
    )

    ingest_odds = PythonOperator(
        task_id="ingest_upcoming_odds",
        python_callable=run_ingest_upcoming_odds,
    )

    dbt_tasks = DbtTaskGroup(
        group_id="dbt_nba_upcoming",
        project_config=ProjectConfig(PATH_TO_DBT_PROJECT),
        profile_config=profile_config,
        execution_config=execution_config,
        render_config=RenderConfig(
            select=["stg_nba__events+", "stg_nba__odds_open+"],
            exclude=["path:models/nba/live"],
            test_behavior=TestBehavior.AFTER_EACH,
            emit_datasets=False,
        ),
    )

    post = EmptyOperator(task_id="post_dbt", trigger_rule="all_done")

    check >> ingest_events >> ingest_odds >> dbt_tasks >> post


nba_ingest_upcoming()
