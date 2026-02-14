"""
Cold-path database operations: stage, merge, and teams loading.

Pattern: S3 Parquet → COPY INTO staging → MERGE INTO production → cleanup staging.
"""
import logging
import time

from include.capstone.config import (
    STUDENT_SCHEMA,
    HIST_EVENTS_TABLE,
    HIST_ODDS_TABLE,
    HIST_GAMES_TABLE,
    HIST_BOX_SCORES_TABLE,
    HIST_TEAMS_TABLE,
    STG_EVENTS_TABLE,
    STG_ODDS_TABLE,
    STG_GAMES_TABLE,
    STG_BOX_SCORES_TABLE,
)
from include.capstone.database.connection import get_snowflake_connection, _setup_parquet_stage

logger = logging.getLogger(__name__)


# ===========================================
# STAGE: COPY INTO staging with FORCE=TRUE
# ===========================================

def stage_events(date_str: str, bulk_s3_path: str) -> dict:
    """Load events into staging table. FORCE=TRUE ignores load history."""
    t0 = time.monotonic()

    if not bulk_s3_path:
        logger.info(f"No bulk path for {date_str} - skipping stage")
        return {"ds": date_str, "staged": 0}

    conn = get_snowflake_connection()
    cursor = conn.cursor()

    try:
        stage_name = f"{STUDENT_SCHEMA}.hist_events_stage"
        _setup_parquet_stage(cursor, stage_name, "events")

        cursor.execute(f"DELETE FROM {STG_EVENTS_TABLE} WHERE ds = '{date_str}'")

        cursor.execute(f"""
            COPY INTO {STG_EVENTS_TABLE} (
                ds, event_id, season, sport_key, sport_title,
                commence_time_utc, commence_time_et, home_team, away_team,
                s3_path
            )
            FROM (
                SELECT
                    '{date_str}'::DATE,
                    $1:event_id::VARCHAR,
                    $1:season::VARCHAR,
                    $1:sport_key::VARCHAR,
                    $1:sport_title::VARCHAR,
                    $1:commence_time_utc::TIMESTAMP_NTZ,
                    $1:commence_time_et::TIMESTAMP_NTZ,
                    $1:home_team::VARCHAR,
                    $1:away_team::VARCHAR,
                    '{bulk_s3_path}'::VARCHAR
                FROM @{stage_name}/ds={date_str}/records.parquet
            )
            FORCE = TRUE
        """)
        staged = cursor.rowcount

        elapsed = time.monotonic() - t0
        result = {"ds": date_str, "staged": staged, "elapsed_sec": round(elapsed, 2)}
        logger.info(f"stage_events | ds={date_str} | staged={staged}")
        return result

    finally:
        cursor.close()
        conn.close()


def stage_odds(date_str: str, bulk_s3_path: str) -> dict:
    """Load odds into staging table. FORCE=TRUE ignores load history."""
    t0 = time.monotonic()

    if not bulk_s3_path:
        logger.info(f"No bulk path for {date_str} - skipping stage")
        return {"ds": date_str, "staged": 0}

    conn = get_snowflake_connection()
    cursor = conn.cursor()

    try:
        stage_name = f"{STUDENT_SCHEMA}.hist_odds_stage"
        _setup_parquet_stage(cursor, stage_name, "odds_open")

        cursor.execute(f"DELETE FROM {STG_ODDS_TABLE} WHERE ds = '{date_str}'")

        cursor.execute(f"""
            COPY INTO {STG_ODDS_TABLE} (
                ds, event_id, season, home_team, away_team,
                commence_time_utc, commence_time_et,
                bookmaker_key, bookmaker_title, bookmaker_last_update,
                market_key, outcome_name, outcome_price, outcome_point, s3_path
            )
            FROM (
                SELECT
                    '{date_str}'::DATE,
                    $1:event_id::VARCHAR,
                    $1:season::VARCHAR,
                    $1:home_team::VARCHAR,
                    $1:away_team::VARCHAR,
                    $1:commence_time_utc::TIMESTAMP_NTZ,
                    $1:commence_time_et::TIMESTAMP_NTZ,
                    $1:bookmaker_key::VARCHAR,
                    $1:bookmaker_title::VARCHAR,
                    TRY_TO_TIMESTAMP_NTZ($1:bookmaker_last_update::VARCHAR),
                    $1:market_key::VARCHAR,
                    $1:outcome_name::VARCHAR,
                    $1:outcome_price::INTEGER,
                    $1:outcome_point::FLOAT,
                    '{bulk_s3_path}'::VARCHAR
                FROM @{stage_name}/ds={date_str}/records.parquet
            )
            FORCE = TRUE
        """)
        staged = cursor.rowcount

        elapsed = time.monotonic() - t0
        result = {"ds": date_str, "staged": staged, "elapsed_sec": round(elapsed, 2)}
        logger.info(f"stage_odds | ds={date_str} | staged={staged}")
        return result

    finally:
        cursor.close()
        conn.close()


def stage_games(date_str: str, bulk_s3_path: str) -> dict:
    """Load games into staging table. FORCE=TRUE ignores load history."""
    t0 = time.monotonic()

    if not bulk_s3_path:
        logger.info(f"No bulk path for {date_str} - skipping stage")
        return {"ds": date_str, "staged": 0}

    conn = get_snowflake_connection()
    cursor = conn.cursor()

    try:
        stage_name = f"{STUDENT_SCHEMA}.hist_games_stage"
        _setup_parquet_stage(cursor, stage_name, "games")

        cursor.execute(f"DELETE FROM {STG_GAMES_TABLE} WHERE ds = '{date_str}'")

        cursor.execute(f"""
            COPY INTO {STG_GAMES_TABLE} (
                ds, game_id, season, game_date, status,
                home_team_id, home_team_name, home_team_score,
                visitor_team_id, visitor_team_name, visitor_team_score,
                postseason, s3_path
            )
            FROM (
                SELECT
                    '{date_str}'::DATE,
                    $1:game_id::INTEGER,
                    $1:season::VARCHAR,
                    $1:game_date::DATE,
                    $1:status::VARCHAR,
                    $1:home_team_id::INTEGER,
                    $1:home_team_name::VARCHAR,
                    $1:home_team_score::INTEGER,
                    $1:visitor_team_id::INTEGER,
                    $1:visitor_team_name::VARCHAR,
                    $1:visitor_team_score::INTEGER,
                    $1:postseason::BOOLEAN,
                    '{bulk_s3_path}'::VARCHAR
                FROM @{stage_name}/ds={date_str}/records.parquet
            )
            FORCE = TRUE
        """)
        staged = cursor.rowcount

        elapsed = time.monotonic() - t0
        result = {"ds": date_str, "staged": staged, "elapsed_sec": round(elapsed, 2)}
        logger.info(f"stage_games | ds={date_str} | staged={staged}")
        return result

    finally:
        cursor.close()
        conn.close()


def stage_box_scores(date_str: str, bulk_s3_path: str) -> dict:
    """Load player box scores into staging table. FORCE=TRUE ignores load history."""
    t0 = time.monotonic()

    if not bulk_s3_path:
        logger.info(f"No bulk path for {date_str} - skipping stage")
        return {"ds": date_str, "staged": 0}

    conn = get_snowflake_connection()
    cursor = conn.cursor()

    try:
        stage_name = f"{STUDENT_SCHEMA}.hist_box_scores_stage"
        _setup_parquet_stage(cursor, stage_name, "box_scores")

        cursor.execute(f"DELETE FROM {STG_BOX_SCORES_TABLE} WHERE ds = '{date_str}'")

        cursor.execute(f"""
            COPY INTO {STG_BOX_SCORES_TABLE} (
                ds, game_id, player_id, player_name, team_id, team_name,
                season, game_date, is_home,
                min, pts, reb, oreb, dreb, ast, stl, blk, turnover, pf,
                fgm, fga, fg_pct, fg3m, fg3a, fg3_pct, ftm, fta, ft_pct,
                s3_path
            )
            FROM (
                SELECT
                    '{date_str}'::DATE,
                    $1:game_id::INTEGER,
                    $1:player_id::INTEGER,
                    $1:player_name::VARCHAR,
                    $1:team_id::INTEGER,
                    $1:team_name::VARCHAR,
                    $1:season::INTEGER,
                    $1:game_date::DATE,
                    $1:is_home::BOOLEAN,
                    $1:min::VARCHAR,
                    $1:pts::INTEGER,
                    $1:reb::INTEGER,
                    $1:oreb::INTEGER,
                    $1:dreb::INTEGER,
                    $1:ast::INTEGER,
                    $1:stl::INTEGER,
                    $1:blk::INTEGER,
                    $1:turnover::INTEGER,
                    $1:pf::INTEGER,
                    $1:fgm::INTEGER,
                    $1:fga::INTEGER,
                    $1:fg_pct::FLOAT,
                    $1:fg3m::INTEGER,
                    $1:fg3a::INTEGER,
                    $1:fg3_pct::FLOAT,
                    $1:ftm::INTEGER,
                    $1:fta::INTEGER,
                    $1:ft_pct::FLOAT,
                    '{bulk_s3_path}'::VARCHAR
                FROM @{stage_name}/ds={date_str}/records.parquet
            )
            FORCE = TRUE
        """)
        staged = cursor.rowcount

        elapsed = time.monotonic() - t0
        result = {"ds": date_str, "staged": staged, "elapsed_sec": round(elapsed, 2)}
        logger.info(f"stage_box_scores | ds={date_str} | staged={staged}")
        return result

    finally:
        cursor.close()
        conn.close()


# ===========================================
# MERGE: Atomic upsert from staging to production
# ===========================================

def merge_events(date_str: str) -> dict:
    """MERGE events from staging into production. Atomic upsert."""
    conn = get_snowflake_connection()
    cursor = conn.cursor()

    try:
        # Remove existing duplicates in target before MERGE (self-healing).
        cursor.execute(f"""
            DELETE FROM {HIST_EVENTS_TABLE}
            WHERE ds = '{date_str}'
            AND event_id IN (
                SELECT event_id
                FROM {HIST_EVENTS_TABLE}
                WHERE ds = '{date_str}'
                GROUP BY event_id
                HAVING COUNT(*) > 1
            )
        """)
        deduped = cursor.rowcount
        if deduped:
            logger.info(f"merge_events | deduped {deduped} duplicate rows for ds={date_str}")

        cursor.execute(f"""
            MERGE INTO {HIST_EVENTS_TABLE} AS tgt
            USING (
                SELECT * FROM {STG_EVENTS_TABLE} WHERE ds = '{date_str}'
            ) AS src
            ON tgt.ds = src.ds AND tgt.event_id = src.event_id
            WHEN MATCHED THEN UPDATE SET
                tgt.season = src.season,
                tgt.sport_key = src.sport_key,
                tgt.sport_title = src.sport_title,
                tgt.commence_time_utc = src.commence_time_utc,
                tgt.commence_time_et = src.commence_time_et,
                tgt.home_team = src.home_team,
                tgt.away_team = src.away_team,
                tgt.s3_path = src.s3_path,
                tgt.ingested_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT (
                ds, event_id, season, sport_key, sport_title,
                commence_time_utc, commence_time_et, home_team, away_team,
                s3_path
            ) VALUES (
                src.ds, src.event_id, src.season, src.sport_key, src.sport_title,
                src.commence_time_utc, src.commence_time_et,
                src.home_team, src.away_team, src.s3_path
            )
        """)
        merged = cursor.rowcount

        # Cleanup staging
        cursor.execute(f"DELETE FROM {STG_EVENTS_TABLE} WHERE ds = '{date_str}'")

        result = {"ds": date_str, "merged": merged}
        logger.info(f"merge_events | ds={date_str} | merged={merged}")
        return result

    finally:
        cursor.close()
        conn.close()


def mark_postponed_events(date_str: str) -> dict:
    """Mark events as postponed based on actual game outcomes.

    Compares hist_nba_events against hist_nba_games by home_team + ds.
    Events with no matching game are marked postponed=TRUE.
    Events with a matching game are reset to postponed=FALSE (idempotent).

    Team names are normalized at ingestion (api_client.py) so direct
    equality works here.
    """
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    try:
        # Mark events with no matching game as postponed
        cursor.execute(f"""
            UPDATE {HIST_EVENTS_TABLE}
            SET postponed = TRUE
            WHERE ds = '{date_str}'
            AND postponed = FALSE
            AND NOT EXISTS (
                SELECT 1 FROM {HIST_GAMES_TABLE} g
                WHERE g.ds = '{date_str}' AND g.home_team_name = {HIST_EVENTS_TABLE}.home_team
            )
        """)
        marked = cursor.rowcount

        # Reset any previously marked that now have matching games (idempotent)
        cursor.execute(f"""
            UPDATE {HIST_EVENTS_TABLE}
            SET postponed = FALSE
            WHERE ds = '{date_str}'
            AND postponed = TRUE
            AND EXISTS (
                SELECT 1 FROM {HIST_GAMES_TABLE} g
                WHERE g.ds = '{date_str}' AND g.home_team_name = {HIST_EVENTS_TABLE}.home_team
            )
        """)
        reset = cursor.rowcount

        result = {"ds": date_str, "postponed": marked, "reset": reset}
        logger.info(f"mark_postponed_events | ds={date_str} | postponed={marked} | reset={reset}")
        return result

    finally:
        cursor.close()
        conn.close()


def merge_odds(date_str: str) -> dict:
    """MERGE odds from staging into production. Atomic upsert."""
    conn = get_snowflake_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(f"""
            MERGE INTO {HIST_ODDS_TABLE} AS tgt
            USING (
                SELECT * FROM {STG_ODDS_TABLE} WHERE ds = '{date_str}'
            ) AS src
            ON tgt.ds = src.ds
                AND tgt.event_id = src.event_id
                AND tgt.bookmaker_key = src.bookmaker_key
                AND tgt.market_key = src.market_key
                AND tgt.outcome_name = src.outcome_name
            WHEN MATCHED THEN UPDATE SET
                tgt.season = src.season,
                tgt.home_team = src.home_team,
                tgt.away_team = src.away_team,
                tgt.commence_time_utc = src.commence_time_utc,
                tgt.commence_time_et = src.commence_time_et,
                tgt.bookmaker_title = src.bookmaker_title,
                tgt.bookmaker_last_update = src.bookmaker_last_update,
                tgt.outcome_price = src.outcome_price,
                tgt.outcome_point = src.outcome_point,
                tgt.s3_path = src.s3_path,
                tgt.ingested_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT (
                ds, event_id, season, home_team, away_team,
                commence_time_utc, commence_time_et,
                bookmaker_key, bookmaker_title, bookmaker_last_update,
                market_key, outcome_name, outcome_price, outcome_point, s3_path
            ) VALUES (
                src.ds, src.event_id, src.season, src.home_team, src.away_team,
                src.commence_time_utc, src.commence_time_et,
                src.bookmaker_key, src.bookmaker_title, src.bookmaker_last_update,
                src.market_key, src.outcome_name, src.outcome_price, src.outcome_point,
                src.s3_path
            )
        """)
        merged = cursor.rowcount

        # Cleanup staging
        cursor.execute(f"DELETE FROM {STG_ODDS_TABLE} WHERE ds = '{date_str}'")

        result = {"ds": date_str, "merged": merged}
        logger.info(f"merge_odds | ds={date_str} | merged={merged}")
        return result

    finally:
        cursor.close()
        conn.close()


def merge_games(date_str: str) -> dict:
    """MERGE games from staging into production. Atomic upsert."""
    conn = get_snowflake_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(f"""
            MERGE INTO {HIST_GAMES_TABLE} AS tgt
            USING (
                SELECT * FROM {STG_GAMES_TABLE} WHERE ds = '{date_str}'
            ) AS src
            ON tgt.ds = src.ds AND tgt.game_id = src.game_id
            WHEN MATCHED THEN UPDATE SET
                tgt.season = src.season,
                tgt.game_date = src.game_date,
                tgt.status = src.status,
                tgt.home_team_id = src.home_team_id,
                tgt.home_team_name = src.home_team_name,
                tgt.home_team_score = src.home_team_score,
                tgt.visitor_team_id = src.visitor_team_id,
                tgt.visitor_team_name = src.visitor_team_name,
                tgt.visitor_team_score = src.visitor_team_score,
                tgt.postseason = src.postseason,
                tgt.s3_path = src.s3_path,
                tgt.ingested_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT (
                ds, game_id, season, game_date, status,
                home_team_id, home_team_name, home_team_score,
                visitor_team_id, visitor_team_name, visitor_team_score,
                postseason, s3_path
            ) VALUES (
                src.ds, src.game_id, src.season, src.game_date, src.status,
                src.home_team_id, src.home_team_name, src.home_team_score,
                src.visitor_team_id, src.visitor_team_name, src.visitor_team_score,
                src.postseason, src.s3_path
            )
        """)
        merged = cursor.rowcount

        # Cleanup staging
        cursor.execute(f"DELETE FROM {STG_GAMES_TABLE} WHERE ds = '{date_str}'")

        result = {"ds": date_str, "merged": merged}
        logger.info(f"merge_games | ds={date_str} | merged={merged}")
        return result

    finally:
        cursor.close()
        conn.close()


def merge_box_scores(date_str: str) -> dict:
    """MERGE box scores from staging into production. Atomic upsert."""
    conn = get_snowflake_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(f"""
            MERGE INTO {HIST_BOX_SCORES_TABLE} AS tgt
            USING (
                SELECT * FROM {STG_BOX_SCORES_TABLE} WHERE ds = '{date_str}'
            ) AS src
            ON tgt.ds = src.ds AND tgt.game_id = src.game_id AND tgt.player_id = src.player_id
            WHEN MATCHED THEN UPDATE SET
                tgt.player_name = src.player_name,
                tgt.team_id = src.team_id,
                tgt.team_name = src.team_name,
                tgt.season = src.season,
                tgt.game_date = src.game_date,
                tgt.is_home = src.is_home,
                tgt.min = src.min,
                tgt.pts = src.pts,
                tgt.reb = src.reb,
                tgt.oreb = src.oreb,
                tgt.dreb = src.dreb,
                tgt.ast = src.ast,
                tgt.stl = src.stl,
                tgt.blk = src.blk,
                tgt.turnover = src.turnover,
                tgt.pf = src.pf,
                tgt.fgm = src.fgm,
                tgt.fga = src.fga,
                tgt.fg_pct = src.fg_pct,
                tgt.fg3m = src.fg3m,
                tgt.fg3a = src.fg3a,
                tgt.fg3_pct = src.fg3_pct,
                tgt.ftm = src.ftm,
                tgt.fta = src.fta,
                tgt.ft_pct = src.ft_pct,
                tgt.s3_path = src.s3_path,
                tgt.ingested_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT (
                ds, game_id, player_id, player_name, team_id, team_name,
                season, game_date, is_home,
                min, pts, reb, oreb, dreb, ast, stl, blk, turnover, pf,
                fgm, fga, fg_pct, fg3m, fg3a, fg3_pct, ftm, fta, ft_pct,
                s3_path
            ) VALUES (
                src.ds, src.game_id, src.player_id, src.player_name,
                src.team_id, src.team_name, src.season, src.game_date, src.is_home,
                src.min, src.pts, src.reb, src.oreb, src.dreb,
                src.ast, src.stl, src.blk, src.turnover, src.pf,
                src.fgm, src.fga, src.fg_pct, src.fg3m, src.fg3a, src.fg3_pct,
                src.ftm, src.fta, src.ft_pct, src.s3_path
            )
        """)
        merged = cursor.rowcount

        # Cleanup staging
        cursor.execute(f"DELETE FROM {STG_BOX_SCORES_TABLE} WHERE ds = '{date_str}'")

        result = {"ds": date_str, "merged": merged}
        logger.info(f"merge_box_scores | ds={date_str} | merged={merged}")
        return result

    finally:
        cursor.close()
        conn.close()


# ===========================================
# Teams (TRUNCATE + INSERT for 30-row reference data)
# ===========================================

def load_teams_to_snowflake(bulk_s3_path: str) -> dict:
    """Load teams reference data. Idempotency: TRUNCATE + INSERT."""
    t0 = time.monotonic()

    if not bulk_s3_path:
        logger.info("No bulk path - skipping Snowflake load")
        return {"deleted": 0, "inserted": 0}

    conn = get_snowflake_connection()
    cursor = conn.cursor()

    try:
        stage_name = f"{STUDENT_SCHEMA}.hist_teams_stage"
        _setup_parquet_stage(cursor, stage_name, "teams")

        cursor.execute(f"TRUNCATE TABLE {HIST_TEAMS_TABLE}")
        logger.info("Truncated teams table")

        cursor.execute(f"""
            INSERT INTO {HIST_TEAMS_TABLE} (
                team_id, full_name, name, city, abbreviation, conference, division
            )
            SELECT
                $1:team_id::INTEGER,
                $1:full_name::VARCHAR,
                $1:name::VARCHAR,
                $1:city::VARCHAR,
                $1:abbreviation::VARCHAR,
                $1:conference::VARCHAR,
                $1:division::VARCHAR
            FROM @{stage_name}/records.parquet
        """)
        inserted_count = cursor.rowcount

        elapsed = time.monotonic() - t0
        result = {
            "inserted": inserted_count,
            "elapsed_sec": round(elapsed, 2),
        }
        logger.info(f"load_teams | inserted={inserted_count} | elapsed_sec={elapsed:.2f}")
        return result

    finally:
        cursor.close()
        conn.close()
