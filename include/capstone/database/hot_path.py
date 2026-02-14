"""
Hot-path database operations: live MERGE FROM VALUES, snapshots, cleanup.

Direct API → Python validation → MERGE FROM VALUES. No S3, no staging, no DQ.
Speed is the priority. Cold path is the safety net.
"""
import logging

from include.capstone.config import (
    LIVE_SCOREBOARD_TABLE,
    LIVE_BOX_SCORES_TABLE,
    LIVE_ODDS_TABLE,
    LIVE_PLAYS_TABLE,
    ARCHIVE_ODDS_TABLE,
)
from include.capstone.database.connection import get_snowflake_connection

logger = logging.getLogger(__name__)


# ===========================================
# SQL escape utility
# ===========================================

def _escape_sql(value) -> str:
    """Escape a Python value for safe inclusion in a SQL VALUES clause."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    # String — escape single quotes
    return f"'{str(value).replace(chr(39), chr(39)+chr(39))}'"


# ===========================================
# Python-side validation (lightweight, no SQL round-trips)
# ===========================================

def _validate_scoreboard_record(record: dict) -> bool:
    """Validate a single scoreboard record. Returns True if valid."""
    game_id = record.get("game_id")
    if not isinstance(game_id, int) or game_id <= 0:
        logger.warning(f"Invalid game_id: {game_id}")
        return False
    if not record.get("home_team_id") or not record.get("visitor_team_id"):
        logger.warning(f"Missing team IDs for game {game_id}")
        return False
    if not record.get("home_team_name") or not record.get("visitor_team_name"):
        logger.warning(f"Missing team names for game {game_id}")
        return False
    home_score = record.get("home_team_score", 0)
    visitor_score = record.get("visitor_team_score", 0)
    if not (0 <= home_score <= 300) or not (0 <= visitor_score <= 300):
        logger.warning(f"Score out of range for game {game_id}: {home_score}-{visitor_score}")
        return False
    if not record.get("status"):
        logger.warning(f"Empty status for game {game_id}")
        return False
    return True


def _validate_box_score_record(record: dict) -> bool:
    """Validate a single box score record. Returns True if valid."""
    game_id = record.get("game_id")
    player_id = record.get("player_id")
    if not isinstance(game_id, int) or game_id <= 0:
        logger.warning(f"Invalid game_id: {game_id}")
        return False
    if not isinstance(player_id, int) or player_id <= 0:
        logger.warning(f"Invalid player_id: {player_id}")
        return False
    if not record.get("player_name"):
        logger.warning(f"Empty player_name for game {game_id} player {player_id}")
        return False
    # Check non-negative stats
    for stat in ("pts", "reb", "ast", "stl", "blk", "turnover", "pf", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta"):
        val = record.get(stat, 0)
        if isinstance(val, (int, float)) and val < 0:
            logger.warning(f"Negative stat {stat}={val} for player {player_id}")
            return False
    # Makes <= attempts
    if (record.get("fgm", 0) or 0) > (record.get("fga", 0) or 0):
        logger.warning(f"fgm > fga for player {player_id}")
        return False
    if (record.get("fg3m", 0) or 0) > (record.get("fg3a", 0) or 0):
        logger.warning(f"fg3m > fg3a for player {player_id}")
        return False
    if (record.get("ftm", 0) or 0) > (record.get("fta", 0) or 0):
        logger.warning(f"ftm > fta for player {player_id}")
        return False
    pts = record.get("pts", 0) or 0
    if pts > 100:
        logger.warning(f"pts={pts} exceeds single-game cap for player {player_id}")
        return False
    return True


def _validate_odds_record(record: dict) -> bool:
    """Validate a single odds record. Returns True if valid."""
    if not record.get("event_id"):
        logger.warning("Empty event_id in odds record")
        return False
    if not record.get("bookmaker_key"):
        logger.warning("Empty bookmaker_key in odds record")
        return False
    if not record.get("market_key"):
        logger.warning("Empty market_key in odds record")
        return False
    if not record.get("outcome_name"):
        logger.warning("Empty outcome_name in odds record")
        return False
    price = record.get("outcome_price")
    if price is None or not isinstance(price, (int, float)):
        logger.warning(f"Invalid outcome_price: {price}")
        return False
    point = record.get("outcome_point")
    if point is not None and isinstance(point, (int, float)) and abs(point) > 300:
        logger.warning(f"outcome_point out of range: {point}")
        return False
    return True


def _validate_play_record(record: dict) -> bool:
    """Validate a single play record. Returns True if valid."""
    if not isinstance(record.get("game_id"), int) or record["game_id"] <= 0:
        logger.warning(f"Invalid game_id in play record: {record.get('game_id')}")
        return False
    # play_id comes from BDL "order" field — 0-indexed sequence number
    if not isinstance(record.get("play_id"), int) or record["play_id"] < 0:
        logger.warning(f"Invalid play_id in play record: {record.get('play_id')}")
        return False
    return True


# ===========================================
# MERGE functions
# ===========================================

def merge_live_scoreboard(records: list[dict], conn=None) -> dict:
    """
    MERGE FROM VALUES into live_nba_scoreboard.

    Validates records Python-side, builds VALUES clause, executes MERGE.
    Empty records = no-op.

    Args:
        records: List of game dicts from fetch_live_games()
        conn: Optional existing Snowflake connection (for single-connection pattern)

    Returns:
        Dict with merge stats
    """
    valid = [r for r in records if _validate_scoreboard_record(r)]
    skipped = len(records) - len(valid)
    if skipped:
        logger.warning(f"merge_live_scoreboard | skipped={skipped} invalid records")

    if not valid:
        return {"merged": 0, "skipped": skipped}

    own_conn = conn is None
    if own_conn:
        conn = get_snowflake_connection()
    cursor = conn.cursor()

    try:
        values_rows = []
        for r in valid:
            values_rows.append(
                f"({_escape_sql(r['game_id'])}, {_escape_sql(r.get('game_date'))}, "
                f"{_escape_sql(r.get('season'))}, {_escape_sql(r['status'])}, "
                f"{_escape_sql(r.get('period'))}, {_escape_sql(r.get('clock'))}, "
                f"{_escape_sql(r.get('game_datetime'))}, "
                f"{_escape_sql(r['home_team_id'])}, {_escape_sql(r['home_team_name'])}, "
                f"{_escape_sql(r.get('home_team_score', 0))}, "
                f"{_escape_sql(r.get('home_q1'))}, {_escape_sql(r.get('home_q2'))}, "
                f"{_escape_sql(r.get('home_q3'))}, {_escape_sql(r.get('home_q4'))}, "
                f"{_escape_sql(r.get('home_ot1'))}, {_escape_sql(r.get('home_ot2'))}, "
                f"{_escape_sql(r.get('home_ot3'))}, "
                f"{_escape_sql(r.get('home_timeouts_remaining'))}, "
                f"{_escape_sql(r.get('home_in_bonus'))}, "
                f"{_escape_sql(r['visitor_team_id'])}, {_escape_sql(r['visitor_team_name'])}, "
                f"{_escape_sql(r.get('visitor_team_score', 0))}, "
                f"{_escape_sql(r.get('visitor_q1'))}, {_escape_sql(r.get('visitor_q2'))}, "
                f"{_escape_sql(r.get('visitor_q3'))}, {_escape_sql(r.get('visitor_q4'))}, "
                f"{_escape_sql(r.get('visitor_ot1'))}, {_escape_sql(r.get('visitor_ot2'))}, "
                f"{_escape_sql(r.get('visitor_ot3'))}, "
                f"{_escape_sql(r.get('visitor_timeouts_remaining'))}, "
                f"{_escape_sql(r.get('visitor_in_bonus'))}, "
                f"{_escape_sql(r.get('postseason', False))}, "
                f"{_escape_sql(r.get('postponed', False))})"
            )

        values_clause = ",\n".join(values_rows)

        cursor.execute(f"""
            MERGE INTO {LIVE_SCOREBOARD_TABLE} AS tgt
            USING (
                SELECT
                    column1 AS game_id, column2 AS game_date, column3 AS season,
                    column4 AS status, column5 AS period, column6 AS clock,
                    column7 AS game_datetime,
                    column8 AS home_team_id, column9 AS home_team_name,
                    column10 AS home_team_score,
                    column11 AS home_q1, column12 AS home_q2,
                    column13 AS home_q3, column14 AS home_q4,
                    column15 AS home_ot1, column16 AS home_ot2, column17 AS home_ot3,
                    column18 AS home_timeouts_remaining, column19 AS home_in_bonus,
                    column20 AS visitor_team_id, column21 AS visitor_team_name,
                    column22 AS visitor_team_score,
                    column23 AS visitor_q1, column24 AS visitor_q2,
                    column25 AS visitor_q3, column26 AS visitor_q4,
                    column27 AS visitor_ot1, column28 AS visitor_ot2, column29 AS visitor_ot3,
                    column30 AS visitor_timeouts_remaining, column31 AS visitor_in_bonus,
                    column32 AS postseason,
                    column33 AS postponed
                FROM VALUES {values_clause}
            ) AS src
            ON tgt.game_id = src.game_id
            WHEN MATCHED THEN UPDATE SET
                tgt.game_date = src.game_date,
                tgt.season = src.season,
                tgt.status = src.status,
                tgt.period = src.period,
                tgt.clock = src.clock,
                tgt.game_datetime = src.game_datetime,
                tgt.home_team_id = src.home_team_id,
                tgt.home_team_name = src.home_team_name,
                tgt.home_team_score = src.home_team_score,
                tgt.home_q1 = src.home_q1,
                tgt.home_q2 = src.home_q2,
                tgt.home_q3 = src.home_q3,
                tgt.home_q4 = src.home_q4,
                tgt.home_ot1 = src.home_ot1,
                tgt.home_ot2 = src.home_ot2,
                tgt.home_ot3 = src.home_ot3,
                tgt.home_timeouts_remaining = src.home_timeouts_remaining,
                tgt.home_in_bonus = src.home_in_bonus,
                tgt.visitor_team_id = src.visitor_team_id,
                tgt.visitor_team_name = src.visitor_team_name,
                tgt.visitor_team_score = src.visitor_team_score,
                tgt.visitor_q1 = src.visitor_q1,
                tgt.visitor_q2 = src.visitor_q2,
                tgt.visitor_q3 = src.visitor_q3,
                tgt.visitor_q4 = src.visitor_q4,
                tgt.visitor_ot1 = src.visitor_ot1,
                tgt.visitor_ot2 = src.visitor_ot2,
                tgt.visitor_ot3 = src.visitor_ot3,
                tgt.visitor_timeouts_remaining = src.visitor_timeouts_remaining,
                tgt.visitor_in_bonus = src.visitor_in_bonus,
                tgt.postseason = src.postseason,
                tgt.postponed = src.postponed,
                tgt.updated_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT (
                game_id, game_date, season, status, period, clock, game_datetime,
                home_team_id, home_team_name, home_team_score,
                home_q1, home_q2, home_q3, home_q4,
                home_ot1, home_ot2, home_ot3,
                home_timeouts_remaining, home_in_bonus,
                visitor_team_id, visitor_team_name, visitor_team_score,
                visitor_q1, visitor_q2, visitor_q3, visitor_q4,
                visitor_ot1, visitor_ot2, visitor_ot3,
                visitor_timeouts_remaining, visitor_in_bonus,
                postseason, postponed
            ) VALUES (
                src.game_id, src.game_date, src.season, src.status, src.period, src.clock,
                src.game_datetime,
                src.home_team_id, src.home_team_name, src.home_team_score,
                src.home_q1, src.home_q2, src.home_q3, src.home_q4,
                src.home_ot1, src.home_ot2, src.home_ot3,
                src.home_timeouts_remaining, src.home_in_bonus,
                src.visitor_team_id, src.visitor_team_name, src.visitor_team_score,
                src.visitor_q1, src.visitor_q2, src.visitor_q3, src.visitor_q4,
                src.visitor_ot1, src.visitor_ot2, src.visitor_ot3,
                src.visitor_timeouts_remaining, src.visitor_in_bonus,
                src.postseason, src.postponed
            )
        """)
        merged = cursor.rowcount

        result = {"merged": merged, "skipped": skipped}
        logger.info(f"merge_live_scoreboard | merged={merged} | skipped={skipped}")
        return result

    finally:
        cursor.close()
        if own_conn:
            conn.close()


def merge_live_box_scores(records: list[dict], conn=None) -> dict:
    """
    MERGE FROM VALUES into live_nba_player_box_scores.

    Args:
        records: List of player box score dicts from fetch_live_box_scores()
        conn: Optional existing Snowflake connection

    Returns:
        Dict with merge stats
    """
    valid = [r for r in records if _validate_box_score_record(r)]
    skipped = len(records) - len(valid)
    if skipped:
        logger.warning(f"merge_live_box_scores | skipped={skipped} invalid records")

    if not valid:
        return {"merged": 0, "skipped": skipped}

    own_conn = conn is None
    if own_conn:
        conn = get_snowflake_connection()
    cursor = conn.cursor()

    try:
        values_rows = []
        for r in valid:
            values_rows.append(
                f"({_escape_sql(r['game_id'])}, {_escape_sql(r['player_id'])}, "
                f"{_escape_sql(r['player_name'])}, {_escape_sql(r['team_id'])}, "
                f"{_escape_sql(r['team_name'])}, {_escape_sql(r['is_home'])}, "
                f"{_escape_sql(r.get('game_date'))}, {_escape_sql(r.get('season'))}, "
                f"{_escape_sql(r.get('status'))}, {_escape_sql(r.get('min'))}, "
                f"{_escape_sql(r.get('pts', 0))}, {_escape_sql(r.get('reb', 0))}, "
                f"{_escape_sql(r.get('oreb', 0))}, {_escape_sql(r.get('dreb', 0))}, "
                f"{_escape_sql(r.get('ast', 0))}, {_escape_sql(r.get('stl', 0))}, "
                f"{_escape_sql(r.get('blk', 0))}, {_escape_sql(r.get('turnover', 0))}, "
                f"{_escape_sql(r.get('pf', 0))}, "
                f"{_escape_sql(r.get('fgm', 0))}, {_escape_sql(r.get('fga', 0))}, "
                f"{_escape_sql(r.get('fg_pct'))}, "
                f"{_escape_sql(r.get('fg3m', 0))}, {_escape_sql(r.get('fg3a', 0))}, "
                f"{_escape_sql(r.get('fg3_pct'))}, "
                f"{_escape_sql(r.get('ftm', 0))}, {_escape_sql(r.get('fta', 0))}, "
                f"{_escape_sql(r.get('ft_pct'))})"
            )

        values_clause = ",\n".join(values_rows)

        cursor.execute(f"""
            MERGE INTO {LIVE_BOX_SCORES_TABLE} AS tgt
            USING (
                SELECT
                    column1 AS game_id, column2 AS player_id, column3 AS player_name,
                    column4 AS team_id, column5 AS team_name, column6 AS is_home,
                    column7 AS game_date, column8 AS season, column9 AS status,
                    column10 AS min,
                    column11 AS pts, column12 AS reb, column13 AS oreb, column14 AS dreb,
                    column15 AS ast, column16 AS stl, column17 AS blk,
                    column18 AS turnover, column19 AS pf,
                    column20 AS fgm, column21 AS fga, column22 AS fg_pct,
                    column23 AS fg3m, column24 AS fg3a, column25 AS fg3_pct,
                    column26 AS ftm, column27 AS fta, column28 AS ft_pct
                FROM VALUES {values_clause}
            ) AS src
            ON tgt.game_id = src.game_id AND tgt.player_id = src.player_id
            WHEN MATCHED THEN UPDATE SET
                tgt.player_name = src.player_name,
                tgt.team_id = src.team_id,
                tgt.team_name = src.team_name,
                tgt.is_home = src.is_home,
                tgt.game_date = src.game_date,
                tgt.season = src.season,
                tgt.status = src.status,
                tgt.min = src.min,
                tgt.pts = src.pts, tgt.reb = src.reb,
                tgt.oreb = src.oreb, tgt.dreb = src.dreb,
                tgt.ast = src.ast, tgt.stl = src.stl,
                tgt.blk = src.blk, tgt.turnover = src.turnover, tgt.pf = src.pf,
                tgt.fgm = src.fgm, tgt.fga = src.fga, tgt.fg_pct = src.fg_pct,
                tgt.fg3m = src.fg3m, tgt.fg3a = src.fg3a, tgt.fg3_pct = src.fg3_pct,
                tgt.ftm = src.ftm, tgt.fta = src.fta, tgt.ft_pct = src.ft_pct,
                tgt.updated_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT (
                game_id, player_id, player_name, team_id, team_name, is_home,
                game_date, season, status, min,
                pts, reb, oreb, dreb, ast, stl, blk, turnover, pf,
                fgm, fga, fg_pct, fg3m, fg3a, fg3_pct, ftm, fta, ft_pct
            ) VALUES (
                src.game_id, src.player_id, src.player_name,
                src.team_id, src.team_name, src.is_home,
                src.game_date, src.season, src.status, src.min,
                src.pts, src.reb, src.oreb, src.dreb,
                src.ast, src.stl, src.blk, src.turnover, src.pf,
                src.fgm, src.fga, src.fg_pct,
                src.fg3m, src.fg3a, src.fg3_pct,
                src.ftm, src.fta, src.ft_pct
            )
        """)
        merged = cursor.rowcount

        result = {"merged": merged, "skipped": skipped}
        logger.info(f"merge_live_box_scores | merged={merged} | skipped={skipped}")
        return result

    finally:
        cursor.close()
        if own_conn:
            conn.close()


def merge_live_odds(records: list[dict], conn=None) -> dict:
    """
    MERGE FROM VALUES into live_nba_odds.

    Completed games disappear from the API — MERGE never deletes,
    so the closing line persists until cleanup.

    Args:
        records: List of odds dicts from fetch_live_odds()
        conn: Optional existing Snowflake connection

    Returns:
        Dict with merge stats
    """
    valid = [r for r in records if _validate_odds_record(r)]
    skipped = len(records) - len(valid)
    if skipped:
        logger.warning(f"merge_live_odds | skipped={skipped} invalid records")

    if not valid:
        return {"merged": 0, "skipped": skipped}

    own_conn = conn is None
    if own_conn:
        conn = get_snowflake_connection()
    cursor = conn.cursor()

    try:
        values_rows = []
        for r in valid:
            values_rows.append(
                f"({_escape_sql(r['event_id'])}, {_escape_sql(r.get('game_date'))}, "
                f"{_escape_sql(r['home_team'])}, {_escape_sql(r['away_team'])}, "
                f"{_escape_sql(r['commence_time_utc'])}, "
                f"{_escape_sql(r['bookmaker_key'])}, {_escape_sql(r.get('bookmaker_title'))}, "
                f"{_escape_sql(r.get('bookmaker_last_update'))}, "
                f"{_escape_sql(r['market_key'])}, {_escape_sql(r['outcome_name'])}, "
                f"{_escape_sql(r['outcome_price'])}, {_escape_sql(r.get('outcome_point'))})"
            )

        values_clause = ",\n".join(values_rows)

        cursor.execute(f"""
            MERGE INTO {LIVE_ODDS_TABLE} AS tgt
            USING (
                SELECT
                    column1 AS event_id, column2 AS game_date,
                    column3 AS home_team, column4 AS away_team,
                    column5 AS commence_time_utc,
                    column6 AS bookmaker_key, column7 AS bookmaker_title,
                    column8 AS bookmaker_last_update,
                    column9 AS market_key, column10 AS outcome_name,
                    column11 AS outcome_price, column12 AS outcome_point
                FROM VALUES {values_clause}
            ) AS src
            ON tgt.event_id = src.event_id
                AND tgt.bookmaker_key = src.bookmaker_key
                AND tgt.market_key = src.market_key
                AND tgt.outcome_name = src.outcome_name
            WHEN MATCHED THEN UPDATE SET
                tgt.game_date = src.game_date,
                tgt.home_team = src.home_team,
                tgt.away_team = src.away_team,
                tgt.commence_time_utc = src.commence_time_utc,
                tgt.bookmaker_title = src.bookmaker_title,
                tgt.bookmaker_last_update = src.bookmaker_last_update,
                tgt.outcome_price = src.outcome_price,
                tgt.outcome_point = src.outcome_point,
                tgt.updated_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT (
                event_id, game_date, home_team, away_team, commence_time_utc,
                bookmaker_key, bookmaker_title, bookmaker_last_update,
                market_key, outcome_name, outcome_price, outcome_point
            ) VALUES (
                src.event_id, src.game_date, src.home_team, src.away_team,
                src.commence_time_utc,
                src.bookmaker_key, src.bookmaker_title, src.bookmaker_last_update,
                src.market_key, src.outcome_name, src.outcome_price, src.outcome_point
            )
        """)
        merged = cursor.rowcount

        result = {"merged": merged, "skipped": skipped}
        logger.info(f"merge_live_odds | merged={merged} | skipped={skipped}")
        return result

    finally:
        cursor.close()
        if own_conn:
            conn.close()


def merge_live_plays(records: list[dict], conn=None) -> dict:
    """
    MERGE FROM VALUES into live_nba_plays.

    Plays are insert-once — they don't change after creation.
    WHEN MATCHED is effectively a no-op.

    Args:
        records: List of play dicts from fetch_live_plays()
        conn: Optional existing Snowflake connection

    Returns:
        Dict with merge stats
    """
    valid = [r for r in records if _validate_play_record(r)]
    skipped = len(records) - len(valid)
    if skipped:
        logger.warning(f"merge_live_plays | skipped={skipped} invalid records")

    if not valid:
        return {"merged": 0, "skipped": skipped}

    own_conn = conn is None
    if own_conn:
        conn = get_snowflake_connection()
    cursor = conn.cursor()

    try:
        values_rows = []
        for r in valid:
            values_rows.append(
                f"({_escape_sql(r['game_id'])}, {_escape_sql(r['play_id'])}, "
                f"{_escape_sql(r.get('period'))}, {_escape_sql(r.get('period_display'))}, "
                f"{_escape_sql(r.get('clock'))}, "
                f"{_escape_sql(r.get('action_type'))}, {_escape_sql(r.get('description'))}, "
                f"{_escape_sql(r.get('team_id'))}, {_escape_sql(r.get('team_name'))}, "
                f"{_escape_sql(r.get('scoring_play', False))}, "
                f"{_escape_sql(r.get('shooting_play', False))}, "
                f"{_escape_sql(r.get('score_value'))}, "
                f"{_escape_sql(r.get('home_score', 0))}, {_escape_sql(r.get('away_score', 0))}, "
                f"{_escape_sql(r.get('coordinate_x'))}, {_escape_sql(r.get('coordinate_y'))})"
            )

        values_clause = ",\n".join(values_rows)

        cursor.execute(f"""
            MERGE INTO {LIVE_PLAYS_TABLE} AS tgt
            USING (
                SELECT
                    column1 AS game_id, column2 AS play_id,
                    column3 AS period, column4 AS period_display,
                    column5 AS clock,
                    column6 AS action_type, column7 AS description,
                    column8 AS team_id, column9 AS team_name,
                    column10 AS scoring_play, column11 AS shooting_play,
                    column12 AS score_value,
                    column13 AS home_score, column14 AS away_score,
                    column15 AS coordinate_x, column16 AS coordinate_y
                FROM VALUES {values_clause}
            ) AS src
            ON tgt.game_id = src.game_id AND tgt.play_id = src.play_id
            WHEN MATCHED THEN UPDATE SET
                tgt.updated_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT (
                game_id, play_id, period, period_display, clock,
                action_type, description, team_id, team_name,
                scoring_play, shooting_play, score_value,
                home_score, away_score, coordinate_x, coordinate_y
            ) VALUES (
                src.game_id, src.play_id, src.period, src.period_display, src.clock,
                src.action_type, src.description, src.team_id, src.team_name,
                src.scoring_play, src.shooting_play, src.score_value,
                src.home_score, src.away_score, src.coordinate_x, src.coordinate_y
            )
        """)
        merged = cursor.rowcount

        result = {"merged": merged, "skipped": skipped}
        logger.info(f"merge_live_plays | merged={merged} | skipped={skipped}")
        return result

    finally:
        cursor.close()
        if own_conn:
            conn.close()


def snapshot_live_odds(conn=None) -> dict:
    """
    Append current live odds to archive table for line movement history.

    Non-fatal: if INSERT fails, log warning but don't crash the run.

    Args:
        conn: Optional existing Snowflake connection
    """
    own_conn = conn is None
    if own_conn:
        conn = get_snowflake_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(f"""
            INSERT INTO {ARCHIVE_ODDS_TABLE} (
                snapshot_time, event_id, game_date, home_team, away_team,
                commence_time_utc, bookmaker_key, bookmaker_title,
                bookmaker_last_update, market_key, outcome_name,
                outcome_price, outcome_point, updated_at
            )
            SELECT
                CURRENT_TIMESTAMP(),
                event_id, game_date, home_team, away_team,
                commence_time_utc, bookmaker_key, bookmaker_title,
                bookmaker_last_update, market_key, outcome_name,
                outcome_price, outcome_point, updated_at
            FROM {LIVE_ODDS_TABLE}
        """)
        inserted = cursor.rowcount
        logger.info(f"snapshot_live_odds | inserted={inserted}")
        return {"inserted": inserted}

    except Exception as e:
        logger.warning(f"snapshot_live_odds failed (non-fatal): {e}")
        return {"inserted": 0, "error": str(e)}

    finally:
        cursor.close()
        if own_conn:
            conn.close()


def cleanup_live_tables(max_age_days: int = 2) -> dict:
    """
    DELETE old data from live tables. Cold path already has this data in hist_*.

    Args:
        max_age_days: Remove games older than this many days (default 2)

    Returns:
        Dict with deletion counts per table
    """
    conn = get_snowflake_connection()
    cursor = conn.cursor()

    try:
        results = {}

        # Scoreboard
        cursor.execute(f"""
            DELETE FROM {LIVE_SCOREBOARD_TABLE}
            WHERE game_date < DATEADD('day', -{max_age_days}, CURRENT_DATE())
        """)
        results["scoreboard"] = cursor.rowcount

        # Box scores
        cursor.execute(f"""
            DELETE FROM {LIVE_BOX_SCORES_TABLE}
            WHERE game_date < DATEADD('day', -{max_age_days}, CURRENT_DATE())
        """)
        results["box_scores"] = cursor.rowcount

        # Odds (use commence_time_utc)
        cursor.execute(f"""
            DELETE FROM {LIVE_ODDS_TABLE}
            WHERE commence_time_utc < DATEADD('day', -{max_age_days}, CURRENT_TIMESTAMP())
        """)
        results["odds"] = cursor.rowcount

        # Plays (remove plays for games no longer in scoreboard)
        cursor.execute(f"""
            DELETE FROM {LIVE_PLAYS_TABLE}
            WHERE game_id NOT IN (SELECT game_id FROM {LIVE_SCOREBOARD_TABLE})
        """)
        results["plays"] = cursor.rowcount

        logger.info(f"cleanup_live_tables | max_age={max_age_days}d | {results}")
        return results

    finally:
        cursor.close()
        conn.close()
