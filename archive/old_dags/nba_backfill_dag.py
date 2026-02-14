"""
NBA Backfill DAG (Cold Path)

Manual-trigger DAG for bulk-loading historical data across date ranges.
Accepts start_date, end_date, and datasets as parameters.

Pattern: stage → DQ → MERGE → ops log (per date, per dataset)
Idempotency: MERGE (atomic upsert), staging cleared per-date.

Schedule: None (manual trigger)
Source: The Odds API + BallDontLie API
Tables: hist_nba_events, hist_nba_odds_open, hist_nba_games, hist_nba_player_box_scores
"""
import logging
from datetime import datetime, timedelta

from airflow.models.param import Param
from airflow.sdk import dag
from airflow.providers.standard.operators.python import PythonOperator

from include.capstone.config import is_nba_season
from include.capstone.api_client import fetch_events_for_date, fetch_odds_for_date
from include.capstone.balldontlie_client import (
    fetch_games_for_date,
    fetch_box_scores_for_date,
)
from include.capstone.storage import (
    upload_archive,
    upload_bulk,
    build_events_archive_payload,
    build_odds_archive_payload,
    build_games_archive_payload,
    build_box_scores_archive_payload,
)
from include.capstone.database import (
    stage_events,
    stage_odds,
    stage_games,
    stage_box_scores,
    validate_events,
    validate_odds,
    validate_games,
    validate_box_scores,
    merge_events,
    merge_odds,
    merge_games,
    merge_box_scores,
    classify_empty,
    log_ingestion_run,
)
from include.capstone.callbacks import alert_on_failure

logger = logging.getLogger(__name__)

DAG_ID = "nba_backfill_v2"


def run_generate_date_list(**context):
    """Generate list of dates within NBA season for the given range."""
    params = context["params"]
    start = params["start_date"]
    end = params["end_date"]

    current = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")

    dates = []
    while current <= end_dt:
        date_str = current.strftime("%Y-%m-%d")
        if is_nba_season(date_str):
            dates.append(date_str)
        current += timedelta(days=1)

    print(f"Generated {len(dates)} dates for backfill ({start} to {end})")
    return dates


def _backfill_events(date_str: str):
    """Backfill events for a single date: fetch → S3 → stage → DQ → MERGE."""
    events = fetch_events_for_date(date_str)
    if not events:
        status = classify_empty(date_str, "events")
        log_ingestion_run(date_str, "events", DAG_ID, status, rows_merged=0)
        return 0

    today_et = datetime.now().strftime("%Y-%m-%d")
    endpoint = "historical" if date_str < today_et else "current"
    payload = build_events_archive_payload(date_str, events, endpoint)
    upload_archive("events", payload, date_str=date_str)
    bulk_path = upload_bulk("events", events, date_str=date_str)

    if bulk_path:
        stage_events(date_str, bulk_path)
        validate_events(date_str)
        result = merge_events(date_str)
        log_ingestion_run(
            date_str, "events", DAG_ID, "SUCCESS",
            rows_merged=result.get("merged", 0), s3_bulk_path=bulk_path,
        )
        return result.get("merged", 0)
    return 0


def _backfill_odds(date_str: str):
    """Backfill odds for a single date: fetch → S3 → stage → DQ → MERGE."""
    records, raw_response = fetch_odds_for_date(date_str)
    if not records:
        status = classify_empty(date_str, "odds_open")
        log_ingestion_run(date_str, "odds_open", DAG_ID, status, rows_merged=0)
        return 0

    payload = build_odds_archive_payload(date_str, records, raw_response)
    upload_archive("odds_open", payload, date_str=date_str)
    bulk_path = upload_bulk("odds_open", records, date_str=date_str)

    if bulk_path:
        stage_odds(date_str, bulk_path)
        validate_odds(date_str)
        result = merge_odds(date_str)
        log_ingestion_run(
            date_str, "odds_open", DAG_ID, "SUCCESS",
            rows_merged=result.get("merged", 0), s3_bulk_path=bulk_path,
        )
        return result.get("merged", 0)
    return 0


def _backfill_games(date_str: str):
    """Backfill games for a single date: fetch → S3 → stage → DQ → MERGE."""
    records, raw_response = fetch_games_for_date(date_str)
    if not records:
        status = classify_empty(date_str, "games")
        log_ingestion_run(date_str, "games", DAG_ID, status, rows_merged=0)
        return 0

    payload = build_games_archive_payload(date_str, records, raw_response)
    upload_archive("games", payload, date_str=date_str)
    bulk_path = upload_bulk("games", records, date_str=date_str)

    if bulk_path:
        stage_games(date_str, bulk_path)
        validate_games(date_str)
        result = merge_games(date_str)
        log_ingestion_run(
            date_str, "games", DAG_ID, "SUCCESS",
            rows_merged=result.get("merged", 0), s3_bulk_path=bulk_path,
        )
        return result.get("merged", 0)
    return 0


def _backfill_box_scores(date_str: str):
    """Backfill box scores for a single date: fetch → S3 → stage → DQ → MERGE."""
    records, raw_response = fetch_box_scores_for_date(date_str)
    if not records:
        status = classify_empty(date_str, "box_scores")
        log_ingestion_run(date_str, "box_scores", DAG_ID, status, rows_merged=0)
        return 0

    payload = build_box_scores_archive_payload(date_str, records, raw_response)
    upload_archive("box_scores", payload, date_str=date_str)
    bulk_path = upload_bulk("box_scores", records, date_str=date_str)

    if bulk_path:
        stage_box_scores(date_str, bulk_path)
        validate_box_scores(date_str)
        result = merge_box_scores(date_str)
        log_ingestion_run(
            date_str, "box_scores", DAG_ID, "SUCCESS",
            rows_merged=result.get("merged", 0), s3_bulk_path=bulk_path,
        )
        return result.get("merged", 0)
    return 0


DATASET_HANDLERS = {
    "events": _backfill_events,
    "odds": _backfill_odds,
    "games": _backfill_games,
    "box_scores": _backfill_box_scores,
}


def run_backfill_date_range(**context):
    """Iterate over dates and backfill selected datasets."""
    ti = context["ti"]
    params = context["params"]
    dates = ti.xcom_pull(task_ids="generate_date_list")
    datasets = params.get("datasets", ["events", "odds", "games", "box_scores"])

    total_dates = len(dates)
    summary = {ds: 0 for ds in datasets}

    for i, date_str in enumerate(dates, 1):
        print(f"\n--- Backfill {i}/{total_dates}: {date_str} ---")

        for dataset in datasets:
            handler = DATASET_HANDLERS.get(dataset)
            if handler is None:
                print(f"Unknown dataset: {dataset}, skipping")
                continue

            count = handler(date_str)
            summary[dataset] += count
            print(f"  {dataset}: {count} records")

    print(f"\nBackfill complete: {summary}")
    return summary


@dag(
    dag_id=DAG_ID,
    description="Manual backfill for historical NBA data (cold path)",
    default_args={
        "owner": "capstone",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(hours=6),
        "on_failure_callback": alert_on_failure,
    },
    start_date=datetime(2023, 10, 24),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    #is_paused_upon_creation=False,
    tags=["capstone", "nba", "backfill"],
    params={
        "start_date": Param("2023-10-24", type="string", description="Start date (YYYY-MM-DD)"),
        "end_date": Param("2023-10-31", type="string", description="End date (YYYY-MM-DD)"),
        "datasets": Param(
            ["events", "odds", "games", "box_scores"],
            type="array",
            description="Datasets to backfill: events, odds, games, box_scores",
        ),
    },
)
def nba_backfill():
    generate = PythonOperator(
        task_id="generate_date_list",
        python_callable=run_generate_date_list,
    )
    backfill = PythonOperator(
        task_id="backfill_date_range",
        python_callable=run_backfill_date_range,
    )

    generate >> backfill


nba_backfill()
