"""
S3 storage operations for NBA Analytics pipeline.
Two generic functions: upload_archive (raw JSON.gz) and upload_bulk (Parquet).
Uses Airflow Variables for AWS credentials (shared infrastructure).
"""
import gzip
import io
import json
import logging
from datetime import datetime
from typing import Optional

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
from airflow.sdk import Variable

from include.capstone.config import (
    S3_ARCHIVE_PREFIX,
    S3_BULK_PREFIX,
    ODDS_MARKETS,
    ODDS_REGIONS,
)

logger = logging.getLogger(__name__)


# ===========================================
# PyArrow schemas for each dataset
# ===========================================

EVENTS_SCHEMA = pa.schema([
    ("event_id", pa.string()),
    ("season", pa.string()),
    ("sport_key", pa.string()),
    ("sport_title", pa.string()),
    ("commence_time_utc", pa.string()),
    ("commence_time_et", pa.string()),
    ("home_team", pa.string()),
    ("away_team", pa.string()),
])

ODDS_SCHEMA = pa.schema([
    ("event_id", pa.string()),
    ("season", pa.string()),
    ("home_team", pa.string()),
    ("away_team", pa.string()),
    ("commence_time_utc", pa.string()),
    ("commence_time_et", pa.string()),
    ("bookmaker_key", pa.string()),
    ("bookmaker_title", pa.string()),
    ("bookmaker_last_update", pa.string()),
    ("market_key", pa.string()),
    ("outcome_name", pa.string()),
    ("outcome_price", pa.int32()),
    ("outcome_point", pa.float64()),
])

GAMES_SCHEMA = pa.schema([
    ("game_id", pa.int32()),
    ("season", pa.string()),
    ("game_date", pa.string()),
    ("status", pa.string()),
    ("home_team_id", pa.int32()),
    ("home_team_name", pa.string()),
    ("home_team_score", pa.int32()),
    ("visitor_team_id", pa.int32()),
    ("visitor_team_name", pa.string()),
    ("visitor_team_score", pa.int32()),
    ("postseason", pa.bool_()),
])

BOX_SCORES_SCHEMA = pa.schema([
    ("game_id", pa.int32()),
    ("player_id", pa.int32()),
    ("player_name", pa.string()),
    ("team_id", pa.int32()),
    ("team_name", pa.string()),
    ("season", pa.int32()),
    ("game_date", pa.string()),
    ("is_home", pa.bool_()),
    ("min", pa.string()),
    ("pts", pa.int32()),
    ("reb", pa.int32()),
    ("oreb", pa.int32()),
    ("dreb", pa.int32()),
    ("ast", pa.int32()),
    ("stl", pa.int32()),
    ("blk", pa.int32()),
    ("turnover", pa.int32()),
    ("pf", pa.int32()),
    ("fgm", pa.int32()),
    ("fga", pa.int32()),
    ("fg_pct", pa.float64()),
    ("fg3m", pa.int32()),
    ("fg3a", pa.int32()),
    ("fg3_pct", pa.float64()),
    ("ftm", pa.int32()),
    ("fta", pa.int32()),
    ("ft_pct", pa.float64()),
])

TEAMS_SCHEMA = pa.schema([
    ("team_id", pa.int32()),
    ("full_name", pa.string()),
    ("name", pa.string()),
    ("city", pa.string()),
    ("abbreviation", pa.string()),
    ("conference", pa.string()),
    ("division", pa.string()),
])

# Map dataset name to schema
DATASET_SCHEMAS = {
    "events": EVENTS_SCHEMA,
    "odds_open": ODDS_SCHEMA,
    "games": GAMES_SCHEMA,
    "box_scores": BOX_SCORES_SCHEMA,
    "teams": TEAMS_SCHEMA,
}


# ===========================================
# S3 client helpers
# ===========================================

def get_s3_client():
    """Create S3 client using Airflow Variables."""
    return boto3.client(
        "s3",
        aws_access_key_id=Variable.get("DATAEXPERT_AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=Variable.get("DATAEXPERT_AWS_SECRET_ACCESS_KEY"),
        region_name="us-west-2",
    )


def get_s3_bucket() -> str:
    """Get S3 bucket name from Airflow Variables."""
    return Variable.get("AWS_S3_BUCKET_TABULAR")


# ===========================================
# Generic upload functions
# ===========================================

def upload_archive(
    dataset: str,
    payload: dict,
    date_str: Optional[str] = None,
) -> Optional[str]:
    """
    Upload gzipped raw JSON archive to S3 for replay capability.

    Args:
        dataset: Dataset name (events, odds_open, games, box_scores, teams)
        payload: Dict with metadata + raw API data to archive
        date_str: Date in YYYY-MM-DD format (None for non-date datasets like teams)

    Returns:
        S3 URI or None if payload is empty
    """
    if not payload:
        logger.info(f"No data for {dataset}/{date_str} - skipping archive upload")
        return None

    if date_str:
        s3_key = f"{S3_ARCHIVE_PREFIX}/{dataset}/ds={date_str}/{dataset}.json.gz"
    else:
        s3_key = f"{S3_ARCHIVE_PREFIX}/{dataset}/{dataset}.json.gz"

    bucket = get_s3_bucket()
    json_bytes = json.dumps(payload, default=str).encode("utf-8")
    compressed = gzip.compress(json_bytes)

    s3_client = get_s3_client()
    s3_client.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=compressed,
        ContentType="application/gzip",
    )

    s3_uri = f"s3://{bucket}/{s3_key}"
    logger.info(
        f"upload_archive | dataset={dataset} | ds={date_str}"
        f" | size_bytes={len(compressed)} | path={s3_uri}"
    )
    return s3_uri


def upload_bulk(
    dataset: str,
    records: list[dict],
    date_str: Optional[str] = None,
) -> Optional[str]:
    """
    Upload records as Parquet to S3 for Snowflake COPY INTO.

    Converts list of dicts to a typed Parquet file using the dataset's
    PyArrow schema, then uploads to S3.

    Args:
        dataset: Dataset name (events, odds_open, games, box_scores, teams)
        records: List of typed dicts to upload
        date_str: Date in YYYY-MM-DD format (None for non-date datasets)

    Returns:
        S3 URI or None if records is empty
    """
    if not records:
        logger.info(f"No records for {dataset}/{date_str} - skipping bulk upload")
        return None

    schema = DATASET_SCHEMAS.get(dataset)
    if schema is None:
        raise ValueError(f"Unknown dataset: {dataset}. Expected one of {list(DATASET_SCHEMAS.keys())}")

    if date_str:
        s3_key = f"{S3_BULK_PREFIX}/{dataset}/ds={date_str}/records.parquet"
    else:
        s3_key = f"{S3_BULK_PREFIX}/{dataset}/records.parquet"

    bucket = get_s3_bucket()

    # Convert records to PyArrow Table
    # Build column arrays from records using the schema field order
    columns = {}
    for field in schema:
        values = [r.get(field.name) for r in records]
        columns[field.name] = values

    table = pa.table(columns, schema=schema)

    # Write Parquet to in-memory buffer
    buf = io.BytesIO()
    pq.write_table(table, buf)
    buf.seek(0)

    s3_client = get_s3_client()
    s3_client.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=buf.getvalue(),
        ContentType="application/octet-stream",
    )

    s3_uri = f"s3://{bucket}/{s3_key}"
    logger.info(
        f"upload_bulk | dataset={dataset} | ds={date_str}"
        f" | records={len(records)} | path={s3_uri}"
    )
    return s3_uri


# ===========================================
# Archive payload builders
# ===========================================

def build_events_archive_payload(
    date_str: str, events: list[dict], endpoint_used: str
) -> dict:
    """Build archive payload for events data."""
    return {
        "metadata": {
            "ds": date_str,
            "event_count": len(events),
            "endpoint_used": endpoint_used,
            "ingested_at": datetime.utcnow().isoformat() + "Z",
        },
        "events": events,
    }


def build_odds_archive_payload(
    date_str: str, records: list[dict], raw_response: dict
) -> dict:
    """Build archive payload for odds data."""
    unique_events = len(set(r["event_id"] for r in records)) if records else 0
    unique_bookmakers = len(set(r["bookmaker_key"] for r in records)) if records else 0

    return {
        "metadata": {
            "ds": date_str,
            "event_count": unique_events,
            "bookmaker_count": unique_bookmakers,
            "record_count": len(records),
            "markets": ODDS_MARKETS,
            "regions": ODDS_REGIONS,
            "ingested_at": datetime.utcnow().isoformat() + "Z",
        },
        "raw_response": raw_response,
        "records": records,
    }


def build_games_archive_payload(
    date_str: str, records: list[dict], raw_response: dict
) -> dict:
    """Build archive payload for games data."""
    return {
        "metadata": {
            "ds": date_str,
            "game_count": len(records),
            "source": "balldontlie",
            "ingested_at": datetime.utcnow().isoformat() + "Z",
        },
        "raw_response": raw_response,
        "records": records,
    }


def build_box_scores_archive_payload(
    date_str: str, records: list[dict], raw_response: dict
) -> dict:
    """Build archive payload for box scores data."""
    unique_games = len(set(r["game_id"] for r in records)) if records else 0

    return {
        "metadata": {
            "ds": date_str,
            "game_count": unique_games,
            "player_record_count": len(records),
            "source": "balldontlie",
            "ingested_at": datetime.utcnow().isoformat() + "Z",
        },
        "raw_response": raw_response,
        "records": records,
    }


def build_teams_archive_payload(
    records: list[dict], raw_response: dict
) -> dict:
    """Build archive payload for teams data."""
    return {
        "metadata": {
            "team_count": len(records),
            "source": "balldontlie",
            "ingested_at": datetime.utcnow().isoformat() + "Z",
        },
        "raw_response": raw_response,
        "records": records,
    }
