"""
Validates all dbt models by running Snowflake queries against materialized tables/views.
Checks row counts, NULLs, value ranges, uniqueness, and cross-model integrity.

Usage:
    python -m include.capstone.scripts.validate_dbt_models
"""

import sys
import logging
from typing import Any, Callable

from include.capstone.database.connection import get_snowflake_connection
from include.capstone.config import STUDENT_SCHEMA

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

S = STUDENT_SCHEMA  # shorthand for queries

# ─── Helpers ───────────────────────────────────────────────────────────────


def run_check(
    cursor,
    name: str,
    query: str,
    validator: Callable[[Any], bool],
    counters: dict,
) -> bool:
    """Run a query, apply validator to first row, print PASS/FAIL."""
    try:
        cursor.execute(query)
        result = cursor.fetchone()
        passed = validator(result)
        status = "PASS" if passed else "FAIL"
        tag = "" if passed else " <<<<<"
        logger.info(f"  [{status}] {name}: {result}{tag}")
        counters["passed" if passed else "failed"] += 1
        return passed
    except Exception as e:
        logger.info(f"  [ERROR] {name}: {e}")
        counters["failed"] += 1
        return False


def section(title: str):
    logger.info(f"\n{'='*60}")
    logger.info(f"  {title}")
    logger.info(f"{'='*60}")


# ─── Source Table Checks ───────────────────────────────────────────────────


def check_sources(cursor, c):
    section("SOURCE TABLES (hist_nba_*)")

    tables = [
        ("hist_nba_events", True),
        ("hist_nba_odds_open", True),
        ("hist_nba_games", True),
        ("hist_nba_player_box_scores", True),
        ("hist_nba_teams", False),
    ]

    for table, has_ingested_at in tables:
        run_check(
            cursor,
            f"{table} row count > 0",
            f"SELECT COUNT(*) FROM {S}.{table}",
            lambda r: r[0] > 0,
            c,
        )

        if has_ingested_at:
            run_check(
                cursor,
                f"{table} freshness (max ingested_at)",
                f"SELECT MAX(ingested_at)::varchar FROM {S}.{table}",
                lambda r: r[0] is not None,
                c,
            )

    run_check(
        cursor,
        "hist_nba_teams has exactly 30 rows",
        f"SELECT COUNT(*) FROM {S}.hist_nba_teams",
        lambda r: r[0] == 30,
        c,
    )


# ─── Staging View Checks ──────────────────────────────────────────────────


def check_staging(cursor, c):
    section("STAGING VIEWS (stg_nba__*)")

    # stg_nba__events
    run_check(
        cursor,
        "stg_nba__events row count > 0",
        f"SELECT COUNT(*) FROM {S}.stg_nba__events",
        lambda r: r[0] > 0,
        c,
    )
    run_check(
        cursor,
        "stg_nba__events no NULL event_id",
        f"SELECT COUNT_IF(event_id IS NULL) FROM {S}.stg_nba__events",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "stg_nba__events no NULL game_date",
        f"SELECT COUNT_IF(game_date IS NULL) FROM {S}.stg_nba__events",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "stg_nba__events no NULL home_team",
        f"SELECT COUNT_IF(home_team IS NULL) FROM {S}.stg_nba__events",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "stg_nba__events season format YYYY-YY",
        f"""SELECT COUNT_IF(season NOT RLIKE '^[0-9]{{4}}-[0-9]{{2}}$')
            FROM {S}.stg_nba__events""",
        lambda r: r[0] == 0,
        c,
    )

    # stg_nba__odds_open
    run_check(
        cursor,
        "stg_nba__odds_open row count > 0",
        f"SELECT COUNT(*) FROM {S}.stg_nba__odds_open",
        lambda r: r[0] > 0,
        c,
    )
    run_check(
        cursor,
        "stg_nba__odds_open market_key values valid",
        f"""SELECT COUNT_IF(market_key NOT IN ('h2h', 'spreads', 'totals'))
            FROM {S}.stg_nba__odds_open""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "stg_nba__odds_open implied_probability 0-1",
        f"""SELECT
                COUNT_IF(implied_probability < 0 OR implied_probability > 1)
            FROM {S}.stg_nba__odds_open""",
        lambda r: r[0] == 0,
        c,
    )

    # stg_nba__games
    run_check(
        cursor,
        "stg_nba__games row count > 0",
        f"SELECT COUNT(*) FROM {S}.stg_nba__games",
        lambda r: r[0] > 0,
        c,
    )
    run_check(
        cursor,
        "stg_nba__games all status = Final",
        f"""SELECT COUNT_IF(status != 'Final')
            FROM {S}.stg_nba__games""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "stg_nba__games home_team_score 50-200",
        f"""SELECT COUNT_IF(home_team_score < 50 OR home_team_score > 200)
            FROM {S}.stg_nba__games""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "stg_nba__games visitor_team_score 50-200",
        f"""SELECT COUNT_IF(visitor_team_score < 50 OR visitor_team_score > 200)
            FROM {S}.stg_nba__games""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "stg_nba__games game_id unique",
        f"""SELECT COUNT(*) - COUNT(DISTINCT game_id)
            FROM {S}.stg_nba__games""",
        lambda r: r[0] == 0,
        c,
    )
    # Critical: season format
    run_check(
        cursor,
        "stg_nba__games season format (sample)",
        f"SELECT DISTINCT season FROM {S}.stg_nba__games LIMIT 5",
        lambda r: r is not None,  # just display the values
        c,
    )
    # Fetch all distinct seasons to display
    cursor.execute(f"SELECT DISTINCT season FROM {S}.stg_nba__games ORDER BY season")
    seasons = [row[0] for row in cursor.fetchall()]
    logger.info(f"  [INFO] stg_nba__games distinct seasons: {seasons}")

    # stg_nba__player_box_scores
    run_check(
        cursor,
        "stg_nba__player_box_scores row count > 0",
        f"SELECT COUNT(*) FROM {S}.stg_nba__player_box_scores",
        lambda r: r[0] > 0,
        c,
    )
    run_check(
        cursor,
        "stg_nba__player_box_scores minutes_played 0-65",
        f"""SELECT COUNT_IF(minutes_played < 0 OR minutes_played > 65)
            FROM {S}.stg_nba__player_box_scores""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "stg_nba__player_box_scores pts 0-100",
        f"""SELECT COUNT_IF(pts < 0 OR pts > 100)
            FROM {S}.stg_nba__player_box_scores""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "stg_nba__player_box_scores season format YYYY-YY",
        f"""SELECT COUNT_IF(season NOT RLIKE '^[0-9]{{4}}-[0-9]{{2}}$')
            FROM {S}.stg_nba__player_box_scores""",
        lambda r: r[0] == 0,
        c,
    )
    # Display distinct seasons
    cursor.execute(
        f"SELECT DISTINCT season FROM {S}.stg_nba__player_box_scores ORDER BY season"
    )
    seasons = [row[0] for row in cursor.fetchall()]
    logger.info(f"  [INFO] stg_nba__player_box_scores distinct seasons: {seasons}")

    # stg_nba__teams
    run_check(
        cursor,
        "stg_nba__teams exactly 30 rows",
        f"SELECT COUNT(*) FROM {S}.stg_nba__teams",
        lambda r: r[0] == 30,
        c,
    )
    run_check(
        cursor,
        "stg_nba__teams conference in (East, West)",
        f"""SELECT COUNT_IF(conference NOT IN ('East', 'West'))
            FROM {S}.stg_nba__teams""",
        lambda r: r[0] == 0,
        c,
    )


# ─── Intermediate Table Checks ────────────────────────────────────────────


def check_intermediate(cursor, c):
    section("INTERMEDIATE TABLES (int_nba__*)")

    # int_nba__team_game_stats
    run_check(
        cursor,
        "int_nba__team_game_stats row count > 0",
        f"SELECT COUNT(*) FROM {S}.int_nba__team_game_stats",
        lambda r: r[0] > 0,
        c,
    )
    run_check(
        cursor,
        "int_nba__team_game_stats 2 rows per game_id",
        f"""SELECT COUNT_IF(team_count != 2)
            FROM (
                SELECT game_id, COUNT(DISTINCT team_id) as team_count
                FROM {S}.int_nba__team_game_stats
                GROUP BY game_id
            )""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "int_nba__team_game_stats est_possessions 50-150",
        f"""SELECT COUNT_IF(est_possessions < 50 OR est_possessions > 150)
            FROM {S}.int_nba__team_game_stats""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "int_nba__team_game_stats off_rating 60-170",
        f"""SELECT COUNT_IF(off_rating < 60 OR off_rating > 170)
            FROM {S}.int_nba__team_game_stats
            WHERE off_rating IS NOT NULL""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "int_nba__team_game_stats def_rating 60-170",
        f"""SELECT COUNT_IF(def_rating < 60 OR def_rating > 170)
            FROM {S}.int_nba__team_game_stats
            WHERE def_rating IS NOT NULL""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "int_nba__team_game_stats efg_pct 0.15-0.85",
        f"""SELECT COUNT_IF(efg_pct < 0.15 OR efg_pct > 0.85)
            FROM {S}.int_nba__team_game_stats
            WHERE efg_pct IS NOT NULL""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "int_nba__team_game_stats tov_pct 0.02-0.40",
        f"""SELECT COUNT_IF(tov_pct < 0.02 OR tov_pct > 0.40)
            FROM {S}.int_nba__team_game_stats
            WHERE tov_pct IS NOT NULL""",
        lambda r: r[0] == 0,
        c,
    )

    # int_nba__consensus_lines
    run_check(
        cursor,
        "int_nba__consensus_lines row count > 0",
        f"SELECT COUNT(*) FROM {S}.int_nba__consensus_lines",
        lambda r: r[0] > 0,
        c,
    )
    run_check(
        cursor,
        "int_nba__consensus_lines num_bookmakers 1-30",
        f"""SELECT COUNT_IF(num_bookmakers < 1 OR num_bookmakers > 30)
            FROM {S}.int_nba__consensus_lines""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "int_nba__consensus_lines market_key valid",
        f"""SELECT COUNT_IF(market_key NOT IN ('h2h', 'spreads', 'totals'))
            FROM {S}.int_nba__consensus_lines""",
        lambda r: r[0] == 0,
        c,
    )

    # int_nba__game_betting_results
    run_check(
        cursor,
        "int_nba__game_betting_results row count > 0",
        f"SELECT COUNT(*) FROM {S}.int_nba__game_betting_results",
        lambda r: r[0] > 0,
        c,
    )
    run_check(
        cursor,
        "int_nba__game_betting_results cover_result valid",
        f"""SELECT COUNT_IF(cover_result NOT IN ('COVERED', 'MISSED', 'PUSH'))
            FROM {S}.int_nba__game_betting_results""",
        lambda r: r[0] == 0,
        c,
    )

    # int_nba__team_rolling_stats
    run_check(
        cursor,
        "int_nba__team_rolling_stats row count > 0",
        f"SELECT COUNT(*) FROM {S}.int_nba__team_rolling_stats",
        lambda r: r[0] > 0,
        c,
    )
    run_check(
        cursor,
        "int_nba__team_rolling_stats L10 populated after game 11",
        f"""SELECT COUNT_IF(l10_avg_pts IS NULL AND season_game_number >= 11)
            FROM {S}.int_nba__team_rolling_stats""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "int_nba__team_rolling_stats season_avg populated after game 2",
        f"""SELECT COUNT_IF(season_avg_pts IS NULL AND season_game_number >= 2)
            FROM {S}.int_nba__team_rolling_stats""",
        lambda r: r[0] == 0,
        c,
    )

    # int_nba__player_rolling_stats
    run_check(
        cursor,
        "int_nba__player_rolling_stats row count > 0",
        f"SELECT COUNT(*) FROM {S}.int_nba__player_rolling_stats",
        lambda r: r[0] > 0,
        c,
    )
    run_check(
        cursor,
        "int_nba__player_rolling_stats game_score -20 to 80",
        f"""SELECT COUNT_IF(game_score < -20 OR game_score > 80)
            FROM {S}.int_nba__player_rolling_stats""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "int_nba__player_rolling_stats no zero-minute players",
        f"""SELECT COUNT_IF(minutes_played <= 0)
            FROM {S}.int_nba__player_rolling_stats""",
        lambda r: r[0] == 0,
        c,
    )


# ─── Mart Table Checks ────────────────────────────────────────────────────


def check_marts(cursor, c):
    section("MART TABLES (mart_nba__*)")

    # mart_nba__game_results
    run_check(
        cursor,
        "mart_nba__game_results row count > 0",
        f"SELECT COUNT(*) FROM {S}.mart_nba__game_results",
        lambda r: r[0] > 0,
        c,
    )
    run_check(
        cursor,
        "mart_nba__game_results game_id unique",
        f"""SELECT COUNT(*) - COUNT(DISTINCT game_id)
            FROM {S}.mart_nba__game_results""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "mart_nba__game_results winner not NULL",
        f"""SELECT COUNT_IF(winner IS NULL)
            FROM {S}.mart_nba__game_results""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "mart_nba__game_results home_spread_result valid",
        f"""SELECT COUNT_IF(home_spread_result NOT IN ('COVERED', 'MISSED', 'PUSH'))
            FROM {S}.mart_nba__game_results
            WHERE home_spread_result IS NOT NULL""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "mart_nba__game_results over_result valid",
        f"""SELECT COUNT_IF(over_result NOT IN ('COVERED', 'MISSED', 'PUSH'))
            FROM {S}.mart_nba__game_results
            WHERE over_result IS NOT NULL""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "mart_nba__game_results home_ml_result valid",
        f"""SELECT COUNT_IF(home_ml_result NOT IN ('COVERED', 'MISSED'))
            FROM {S}.mart_nba__game_results
            WHERE home_ml_result IS NOT NULL""",
        lambda r: r[0] == 0,
        c,
    )

    # mart_nba__team_ats_records
    run_check(
        cursor,
        "mart_nba__team_ats_records row count > 0",
        f"SELECT COUNT(*) FROM {S}.mart_nba__team_ats_records",
        lambda r: r[0] > 0,
        c,
    )
    run_check(
        cursor,
        "mart_nba__team_ats_records ~30 teams per season",
        f"""SELECT MIN(cnt), MAX(cnt) FROM (
                SELECT season, COUNT(DISTINCT team_name) as cnt
                FROM {S}.mart_nba__team_ats_records
                GROUP BY season
            )""",
        lambda r: r[0] >= 25 and r[1] <= 30,
        c,
    )
    run_check(
        cursor,
        "mart_nba__team_ats_records ats_pct 0-1",
        f"""SELECT COUNT_IF(ats_pct < 0 OR ats_pct > 1)
            FROM {S}.mart_nba__team_ats_records
            WHERE ats_pct IS NOT NULL""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "mart_nba__team_ats_records ats_rank 1-30",
        f"""SELECT COUNT_IF(ats_rank < 1 OR ats_rank > 30)
            FROM {S}.mart_nba__team_ats_records""",
        lambda r: r[0] == 0,
        c,
    )

    # mart_nba__team_matchup_stats
    run_check(
        cursor,
        "mart_nba__team_matchup_stats row count > 0",
        f"SELECT COUNT(*) FROM {S}.mart_nba__team_matchup_stats",
        lambda r: r[0] > 0,
        c,
    )
    run_check(
        cursor,
        "mart_nba__team_matchup_stats unique (season, team_id)",
        f"""SELECT COUNT(*) - COUNT(DISTINCT season || '|' || team_id)
            FROM {S}.mart_nba__team_matchup_stats""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "mart_nba__team_matchup_stats avg_fg_pct 0.3-0.7",
        f"""SELECT COUNT_IF(avg_fg_pct < 0.3 OR avg_fg_pct > 0.7)
            FROM {S}.mart_nba__team_matchup_stats""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "mart_nba__team_matchup_stats off_rating_rank 1-30",
        f"""SELECT COUNT_IF(off_rating_rank < 1 OR off_rating_rank > 30)
            FROM {S}.mart_nba__team_matchup_stats""",
        lambda r: r[0] == 0,
        c,
    )

    # mart_nba__game_predictions (may be empty if no upcoming games loaded)
    cursor.execute(f"SELECT COUNT(*) FROM {S}.mart_nba__game_predictions")
    pred_count = cursor.fetchone()[0]
    if pred_count == 0:
        logger.info(
            "  [WARN] mart_nba__game_predictions is EMPTY"
            " (expected if no upcoming games loaded)"
        )
    else:
        run_check(
            cursor,
            "mart_nba__game_predictions row count > 0",
            f"SELECT COUNT(*) FROM {S}.mart_nba__game_predictions",
            lambda r: r[0] > 0,
            c,
        )
        run_check(
            cursor,
            "mart_nba__game_predictions cover_probability 0-1",
            f"""SELECT COUNT_IF(cover_probability < 0 OR cover_probability > 1)
                FROM {S}.mart_nba__game_predictions
                WHERE cover_probability IS NOT NULL""",
            lambda r: r[0] == 0,
            c,
        )
        run_check(
            cursor,
            "mart_nba__game_predictions bet_rating 1-5",
            f"""SELECT COUNT_IF(bet_rating NOT IN (1, 2, 3, 4, 5))
                FROM {S}.mart_nba__game_predictions""",
            lambda r: r[0] == 0,
            c,
        )
        run_check(
            cursor,
            "mart_nba__game_predictions projected_home_score 70-150",
            f"""SELECT COUNT_IF(projected_home_score < 70 OR projected_home_score > 150)
                FROM {S}.mart_nba__game_predictions
                WHERE projected_home_score IS NOT NULL""",
            lambda r: r[0] == 0,
            c,
        )
        run_check(
            cursor,
            "mart_nba__game_predictions market_key valid",
            f"""SELECT COUNT_IF(market_key NOT IN ('h2h', 'spreads', 'totals'))
                FROM {S}.mart_nba__game_predictions""",
            lambda r: r[0] == 0,
            c,
        )

    # mart_nba__game_grades
    run_check(
        cursor,
        "mart_nba__game_grades row count > 0",
        f"SELECT COUNT(*) FROM {S}.mart_nba__game_grades",
        lambda r: r[0] > 0,
        c,
    )
    run_check(
        cursor,
        "mart_nba__game_grades performance_grade valid",
        f"""SELECT COUNT_IF(performance_grade NOT IN ('A+', 'A', 'B', 'C', 'D', 'F'))
            FROM {S}.mart_nba__game_grades""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "mart_nba__game_grades off_performance_grade valid",
        f"""SELECT COUNT_IF(off_performance_grade NOT IN ('A+', 'A', 'B', 'C', 'D', 'F'))
            FROM {S}.mart_nba__game_grades""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "mart_nba__game_grades def_performance_grade valid",
        f"""SELECT COUNT_IF(def_performance_grade NOT IN ('A+', 'A', 'B', 'C', 'D', 'F'))
            FROM {S}.mart_nba__game_grades""",
        lambda r: r[0] == 0,
        c,
    )

    # mart_nba__player_game_grades
    run_check(
        cursor,
        "mart_nba__player_game_grades row count > 0",
        f"SELECT COUNT(*) FROM {S}.mart_nba__player_game_grades",
        lambda r: r[0] > 0,
        c,
    )
    run_check(
        cursor,
        "mart_nba__player_game_grades performance_grade valid",
        f"""SELECT COUNT_IF(performance_grade NOT IN ('A+', 'A', 'B', 'C', 'D', 'F'))
            FROM {S}.mart_nba__player_game_grades""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "mart_nba__player_game_grades game_score -20 to 80",
        f"""SELECT COUNT_IF(game_score < -20 OR game_score > 80)
            FROM {S}.mart_nba__player_game_grades""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "mart_nba__player_game_grades minutes_played > 0",
        f"""SELECT COUNT_IF(minutes_played <= 0)
            FROM {S}.mart_nba__player_game_grades""",
        lambda r: r[0] == 0,
        c,
    )


# ─── Live View Checks ─────────────────────────────────────────────────────


def check_live(cursor, c):
    section("LIVE VIEWS (live_nba__*)")
    logger.info("  (Live tables may be empty outside game hours)")

    live_checks = [
        (
            "live_nba__scoreboard",
            [
                (
                    "unique game_id",
                    f"""SELECT COUNT(*) - COUNT(DISTINCT game_id)
                        FROM {S}.live_nba__scoreboard""",
                    lambda r: r[0] == 0,
                ),
            ],
        ),
        (
            "live_nba__player_box_scores",
            [
                (
                    "unique (game_id, player_id)",
                    f"""SELECT COUNT(*) - COUNT(DISTINCT game_id || '|' || player_id)
                        FROM {S}.live_nba__player_box_scores""",
                    lambda r: r[0] == 0,
                ),
            ],
        ),
        (
            "live_nba__team_box_scores",
            [
                (
                    "unique (game_id, team_id)",
                    f"""SELECT COUNT(*) - COUNT(DISTINCT game_id || '|' || team_id)
                        FROM {S}.live_nba__team_box_scores""",
                    lambda r: r[0] == 0,
                ),
            ],
        ),
        (
            "live_nba__plays",
            [
                (
                    "unique (game_id, play_id)",
                    f"""SELECT COUNT(*) - COUNT(DISTINCT game_id || '|' || play_id)
                        FROM {S}.live_nba__plays""",
                    lambda r: r[0] == 0,
                ),
            ],
        ),
        (
            "live_nba__odds_current",
            [
                (
                    "market_key valid",
                    f"""SELECT COUNT_IF(market_key NOT IN ('h2h', 'spreads', 'totals'))
                        FROM {S}.live_nba__odds_current""",
                    lambda r: r[0] == 0,
                ),
            ],
        ),
        (
            "live_nba__odds_movement",
            [
                (
                    "snapshot_time not NULL",
                    f"""SELECT COUNT_IF(snapshot_time IS NULL)
                        FROM {S}.live_nba__odds_movement""",
                    lambda r: r[0] == 0,
                ),
            ],
        ),
        (
            "live_nba__game_detail",
            [
                (
                    "unique game_id",
                    f"""SELECT COUNT(*) - COUNT(DISTINCT game_id)
                        FROM {S}.live_nba__game_detail""",
                    lambda r: r[0] == 0,
                ),
            ],
        ),
        (
            "live_nba__game_results",
            [
                (
                    "row count (may be 0 outside game hours)",
                    f"SELECT COUNT(*) FROM {S}.live_nba__game_results",
                    lambda r: r[0] >= 0,
                ),
            ],
        ),
        (
            "live_nba__game_grades",
            [
                (
                    "grades valid (if data exists)",
                    f"""SELECT COUNT_IF(performance_grade NOT IN ('A+', 'A', 'B', 'C', 'D', 'F'))
                        FROM {S}.live_nba__game_grades""",
                    lambda r: r[0] == 0,
                ),
            ],
        ),
        (
            "live_nba__player_game_grades",
            [
                (
                    "grades valid (if data exists)",
                    f"""SELECT COUNT_IF(performance_grade NOT IN ('A+', 'A', 'B', 'C', 'D', 'F'))
                        FROM {S}.live_nba__player_game_grades""",
                    lambda r: r[0] == 0,
                ),
            ],
        ),
    ]

    for view_name, checks in live_checks:
        for check_name, query, validator in checks:
            try:
                run_check(
                    cursor,
                    f"{view_name} {check_name}",
                    query,
                    validator,
                    c,
                )
            except Exception as e:
                logger.info(f"  [SKIP] {view_name} {check_name}: {e}")


# ─── Cross-Model Integrity ────────────────────────────────────────────────


def check_cross_model(cursor, c):
    section("CROSS-MODEL INTEGRITY")

    # Season format consistency — display differences for diagnosis
    cursor.execute(
        f"SELECT DISTINCT season FROM {S}.stg_nba__games ORDER BY season"
    )
    games_seasons = [r[0] for r in cursor.fetchall()]
    cursor.execute(
        f"SELECT DISTINCT season FROM {S}.stg_nba__player_box_scores ORDER BY season"
    )
    box_seasons = [r[0] for r in cursor.fetchall()]
    cursor.execute(
        f"SELECT DISTINCT season FROM {S}.stg_nba__events ORDER BY season"
    )
    events_seasons = [r[0] for r in cursor.fetchall()]

    logger.info(f"  [INFO] games seasons:      {games_seasons}")
    logger.info(f"  [INFO] box_scores seasons:  {box_seasons}")
    logger.info(f"  [INFO] events seasons:      {events_seasons}")

    games_only = set(games_seasons) - set(box_seasons)
    if games_only:
        logger.info(f"  [INFO] seasons in games but NOT box_scores: {games_only}")

    run_check(
        cursor,
        "season format: games vs player_box_scores match",
        f"""SELECT COUNT(*) FROM (
                SELECT DISTINCT season FROM {S}.stg_nba__games
                EXCEPT
                SELECT DISTINCT season FROM {S}.stg_nba__player_box_scores
            )""",
        lambda r: r[0] == 0,
        c,
    )

    run_check(
        cursor,
        "season format: events vs games match",
        f"""SELECT COUNT(*) FROM (
                SELECT DISTINCT season FROM {S}.stg_nba__events
                WHERE season IS NOT NULL
                EXCEPT
                SELECT DISTINCT season FROM {S}.stg_nba__games
            )""",
        lambda r: r[0] == 0,
        c,
    )

    # Games ↔ Events join coverage
    run_check(
        cursor,
        "games with matching events (% coverage)",
        f"""SELECT
                ROUND(
                    COUNT(DISTINCT CASE WHEN e.event_id IS NOT NULL
                          THEN g.game_id END)::float
                    / NULLIF(COUNT(DISTINCT g.game_id), 0) * 100,
                    1
                ) as pct
            FROM {S}.stg_nba__games g
            LEFT JOIN {S}.stg_nba__events e
                ON g.game_date = e.game_date
                AND g.home_team_name = e.home_team
                AND NOT e.is_postponed""",
        lambda r: r[0] is not None and r[0] > 90,  # expect >90% match
        c,
    )

    # Game results with betting data
    run_check(
        cursor,
        "game_results with spread data (% coverage)",
        f"""SELECT
                ROUND(
                    COUNT_IF(home_spread IS NOT NULL)::float
                    / NULLIF(COUNT(*), 0) * 100,
                    1
                ) as pct
            FROM {S}.mart_nba__game_results""",
        lambda r: r[0] is not None and r[0] > 80,  # expect >80%
        c,
    )

    run_check(
        cursor,
        "game_results with moneyline data (% coverage)",
        f"""SELECT
                ROUND(
                    COUNT_IF(home_ml_price IS NOT NULL)::float
                    / NULLIF(COUNT(*), 0) * 100,
                    1
                ) as pct
            FROM {S}.mart_nba__game_results""",
        lambda r: r[0] is not None and r[0] > 80,
        c,
    )

    # Grain checks on key tables
    run_check(
        cursor,
        "int_nba__team_game_stats unique (game_date, game_id, team_id)",
        f"""SELECT COUNT(*) - COUNT(DISTINCT game_date || '|' || game_id || '|' || team_id)
            FROM {S}.int_nba__team_game_stats""",
        lambda r: r[0] == 0,
        c,
    )
    run_check(
        cursor,
        "int_nba__consensus_lines unique (game_date, event_id, market_key, side)",
        f"""SELECT COUNT(*)
                - COUNT(DISTINCT game_date || '|' || event_id || '|' || market_key || '|' || side)
            FROM {S}.int_nba__consensus_lines""",
        lambda r: r[0] == 0,
        c,
    )
    cursor.execute(f"SELECT COUNT(*) FROM {S}.mart_nba__game_predictions")
    xmodel_pred_count = cursor.fetchone()[0]
    if xmodel_pred_count > 0:
        run_check(
            cursor,
            "mart_nba__game_predictions unique (event_id, market_key, side)",
            f"""SELECT COUNT(*)
                    - COUNT(DISTINCT event_id || '|' || market_key || '|' || side)
                FROM {S}.mart_nba__game_predictions""",
            lambda r: r[0] == 0,
            c,
        )


# ─── Main ──────────────────────────────────────────────────────────────────


def main():
    logger.info("dbt Model Validation Script")
    logger.info("Connecting to Snowflake...")

    conn = get_snowflake_connection()
    cursor = conn.cursor()

    # Set schema context
    cursor.execute(f"USE SCHEMA {S}")

    c = {"passed": 0, "failed": 0}

    try:
        check_sources(cursor, c)
        check_staging(cursor, c)
        check_intermediate(cursor, c)
        check_marts(cursor, c)
        check_live(cursor, c)
        check_cross_model(cursor, c)
    finally:
        cursor.close()
        conn.close()

    section("SUMMARY")
    total = c["passed"] + c["failed"]
    logger.info(f"  {c['passed']} passed, {c['failed']} failed (of {total} checks)")

    if c["failed"] > 0:
        logger.info("\n  Review FAIL items above and fix the underlying models.")
        sys.exit(1)
    else:
        logger.info("\n  All checks passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
