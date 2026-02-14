"""
Data quality (DQ) runner and validation functions for cold-path datasets.
"""
import logging

from include.capstone.config import (
    STG_EVENTS_TABLE,
    STG_ODDS_TABLE,
    STG_GAMES_TABLE,
    STG_BOX_SCORES_TABLE,
    HIST_EVENTS_TABLE,
)
from include.capstone.database.connection import get_snowflake_connection

logger = logging.getLogger(__name__)


def _run_dq_check(cursor, query: str, dataset: str, date_str: str):
    """
    Execute DQ query. Raise ValueError if any boolean check is False.

    DQ queries should return a single row of boolean columns.
    Each column name describes the check (e.g., 'event_id_not_null').
    """
    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description]
    row = cursor.fetchone()

    if row is None:
        raise ValueError(f"DQ: no results for {dataset} ds={date_str}")

    failures = [col for col, val in zip(columns, row) if val is False]
    if failures:
        raise ValueError(
            f"DQ FAILED {dataset} ds={date_str}: {failures}"
        )

    logger.info(f"DQ passed {dataset} ds={date_str}: all {len(columns)} checks OK")


def validate_events(date_str: str) -> None:
    """Run DQ checks on staged events. Raises ValueError on failure."""
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    try:
        _run_dq_check(cursor, f"""
            SELECT
                COUNT(*) > 0                                         AS has_data,
                COUNT_IF(event_id IS NULL) = 0                       AS event_id_not_null,
                COUNT_IF(home_team IS NULL OR away_team IS NULL) = 0 AS teams_not_null,
                COUNT_IF(commence_time_utc IS NULL) = 0              AS time_not_null,
                COUNT(*) = COUNT(DISTINCT event_id)                  AS no_duplicate_events,
                COUNT(DISTINCT ds) = 1                               AS single_date_only
            FROM {STG_EVENTS_TABLE}
            WHERE ds = '{date_str}'
        """, "events", date_str)
    finally:
        cursor.close()
        conn.close()


def validate_odds(date_str: str) -> None:
    """Run DQ checks on staged odds. Raises ValueError on failure."""
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    try:
        _run_dq_check(cursor, f"""
            SELECT
                COUNT(*) > 0                           AS has_data,
                COUNT_IF(event_id IS NULL) = 0         AS event_id_not_null,
                COUNT_IF(outcome_price IS NULL) = 0    AS price_not_null,
                COUNT(*) = COUNT(DISTINCT
                    CONCAT(event_id,'|',bookmaker_key,'|',market_key,'|',outcome_name))
                                                       AS no_duplicates,
                COUNT(DISTINCT ds) = 1                 AS single_date_only
            FROM {STG_ODDS_TABLE}
            WHERE ds = '{date_str}'
        """, "odds", date_str)
    finally:
        cursor.close()
        conn.close()


def validate_games(date_str: str) -> None:
    """Run DQ checks on staged games. Cross-references events for expected count."""
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    try:
        # Hard-fail checks: data integrity + cross-reference events
        # Uses <= for game count because postponed games won't appear in BDL.
        # The reconcile DAG marks postponed events retroactively after merge.
        _run_dq_check(cursor, f"""
            SELECT
                COUNT(*) >= 1                                                       AS has_games,
                COUNT_IF(game_id IS NULL) = 0                                       AS game_id_not_null,
                COUNT_IF(status != 'Final') = 0                                     AS all_games_final,
                COUNT_IF(home_team_score IS NULL OR visitor_team_score IS NULL) = 0  AS scores_not_null,
                COUNT_IF(home_team_score < 50 OR visitor_team_score < 50) = 0       AS scores_not_too_low,
                COUNT_IF(home_team_score > 200 OR visitor_team_score > 200) = 0     AS scores_not_too_high,
                COUNT(*) = COUNT(DISTINCT game_id)                                  AS no_duplicate_games,
                COUNT(DISTINCT ds) = 1                                              AS single_date_only,
                COUNT(DISTINCT game_id) <= (
                    SELECT COUNT(DISTINCT event_id)
                    FROM {HIST_EVENTS_TABLE}
                    WHERE ds = '{date_str}'
                )                                                                   AS game_count_within_events
            FROM {STG_GAMES_TABLE}
            WHERE ds = '{date_str}'
        """, "games", date_str)
    finally:
        cursor.close()
        conn.close()


def validate_box_scores(date_str: str) -> None:
    """Run DQ checks on staged box scores. Cross-references games staging."""
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    try:
        _run_dq_check(cursor, f"""
            SELECT
                COUNT_IF(game_id IS NULL OR player_id IS NULL) = 0        AS ids_not_null,
                COUNT_IF(pts < 0 OR reb < 0 OR ast < 0) = 0              AS no_negative_stats,
                COUNT_IF(fgm > fga OR fg3m > fg3a OR ftm > fta) = 0      AS makes_lte_attempts,
                COUNT(*) = COUNT(DISTINCT CONCAT(game_id,'|',player_id))  AS no_duplicates,
                COUNT(DISTINCT ds) = 1                                    AS single_date_only,
                (SELECT COUNT(DISTINCT game_id) FROM {STG_BOX_SCORES_TABLE} WHERE ds = '{date_str}')
                >= (SELECT COUNT(DISTINCT game_id) FROM {STG_GAMES_TABLE} WHERE ds = '{date_str}')
                                                                          AS all_games_have_box_scores
            FROM {STG_BOX_SCORES_TABLE}
            WHERE ds = '{date_str}'
        """, "box_scores", date_str)
    finally:
        cursor.close()
        conn.close()
