"""
Ops metadata: ingestion run logging and empty classification.
"""
import logging
from typing import Optional

from include.capstone.config import (
    OPS_TABLE,
    HIST_EVENTS_TABLE,
)
from include.capstone.database.connection import get_snowflake_connection

logger = logging.getLogger(__name__)


def log_ingestion_run(
    date_str: str,
    dataset: str,
    dag_id: str,
    status: str,
    rows_merged: int = 0,
    s3_archive_path: Optional[str] = None,
    s3_bulk_path: Optional[str] = None,
    elapsed_sec: Optional[float] = None,
    error_message: Optional[str] = None,
) -> dict:
    """Write audit record to ops.ingestion_runs."""
    conn = get_snowflake_connection()
    cursor = conn.cursor()

    try:
        archive_val = f"'{s3_archive_path}'" if s3_archive_path else "NULL"
        bulk_val = f"'{s3_bulk_path}'" if s3_bulk_path else "NULL"
        elapsed_val = str(elapsed_sec) if elapsed_sec is not None else "NULL"
        error_val = f"'{(error_message or '')[:2000].replace(chr(39), chr(39)+chr(39))}'" if error_message else "NULL"

        cursor.execute(f"""
            INSERT INTO {OPS_TABLE} (
                ds, dataset, dag_id, status, rows_merged,
                s3_archive_path, s3_bulk_path, elapsed_sec, error_message
            ) VALUES (
                '{date_str}', '{dataset}', '{dag_id}', '{status}', {rows_merged},
                {archive_val}, {bulk_val}, {elapsed_val}, {error_val}
            )
        """)

        result = {
            "ds": date_str,
            "dataset": dataset,
            "status": status,
            "rows_merged": rows_merged,
        }
        logger.info(f"ops_log | {result}")
        return result

    finally:
        cursor.close()
        conn.close()


def classify_empty(date_str: str, dataset: str) -> str:
    """
    Classify whether 0 records is expected or unexpected.

    Events/Odds: 0 during season = EMPTY_EXPECTED (off-day).
    Games/Box Scores: cross-reference events table.
      - 0 events on that date = EMPTY_EXPECTED (off-day)
      - events exist but 0 games = EMPTY_UNEXPECTED (should fail)
    """
    if dataset in ("events", "odds_open"):
        return "EMPTY_EXPECTED"

    conn = get_snowflake_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"""
            SELECT COUNT(*) FROM {HIST_EVENTS_TABLE} WHERE ds = '{date_str}'
        """)
        event_count = cursor.fetchone()[0]
        if event_count == 0:
            return "EMPTY_EXPECTED"
        else:
            return "EMPTY_UNEXPECTED"
    finally:
        cursor.close()
        conn.close()
