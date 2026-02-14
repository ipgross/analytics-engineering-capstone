"""SQL queries and cached data-fetch functions for the Grades page."""

import streamlit as st
import pandas as pd

# ── Available dates with grades data ─────────────────────────────────────────

AVAILABLE_DATES_SQL = """
SELECT DISTINCT game_date
FROM ipgross.mart_nba__game_grades
ORDER BY game_date DESC
LIMIT 60
"""

# ── Full team game grades ────────────────────────────────────────────────────

TEAM_GRADES_SQL = """
SELECT
    game_id,
    game_date,
    team_id,
    team_name,
    season,
    is_home,
    opp_team_name,
    season_game_number,

    -- Actuals
    pts,
    opp_pts,
    reb,
    ast,
    turnovers,
    stl,
    blk,
    pf,
    fg_pct,
    fg3_pct,
    ft_pct,
    est_possessions,
    off_rating,
    def_rating,
    score_margin,
    total_points,

    -- Game result context
    home_spread,
    spread_result,
    ml_result,
    over_result,

    -- Deltas vs L10
    pts_delta_l10,
    opp_pts_delta_l10,
    reb_delta_l10,
    ast_delta_l10,
    turnovers_delta_l10,
    stl_delta_l10,
    blk_delta_l10,
    fg_pct_delta_l10,
    fg3_pct_delta_l10,
    off_rating_delta_l10,
    def_rating_delta_l10,

    -- L10 averages
    l10_avg_pts,
    l10_avg_opp_pts,
    l10_avg_off_rating,
    l10_avg_def_rating,

    -- Season averages
    season_avg_pts,
    season_avg_opp_pts,
    season_avg_off_rating,
    season_avg_def_rating,

    -- Grades
    off_performance_grade,
    def_performance_grade,
    performance_grade

FROM ipgross.mart_nba__game_grades
WHERE game_date = '{game_date}'
ORDER BY game_id, is_home DESC
"""

# ── Full player game grades ──────────────────────────────────────────────────

PLAYER_GRADES_SQL = """
SELECT
    game_id,
    game_date,
    player_id,
    player_name,
    team_id,
    team_name,
    season,
    is_home,

    -- Actuals
    minutes_played,
    pts,
    reb,
    ast,
    stl,
    blk,
    turnovers,
    pf,
    fg_pct,
    fg3_pct,
    ft_pct,
    game_score,

    -- Deltas vs L10
    pts_delta_l10,
    reb_delta_l10,
    ast_delta_l10,
    stl_delta_l10,
    blk_delta_l10,
    turnovers_delta_l10,
    game_score_delta_l10,
    minutes_delta_l10,

    -- L10 averages
    l10_avg_pts,
    l10_avg_reb,
    l10_avg_ast,
    l10_avg_game_score,
    l10_avg_minutes_played,

    -- Grade
    performance_grade

FROM ipgross.mart_nba__player_game_grades
WHERE game_date = '{game_date}'
ORDER BY game_id, is_home DESC, game_score DESC
"""


def get_available_grade_dates() -> list:
    """Return sorted list of distinct game_dates with grades (descending). Cached 5 min."""
    conn = st.connection("snowflake")
    df = conn.query(AVAILABLE_DATES_SQL, ttl=300)
    if df.empty:
        return []
    return list(df["GAME_DATE"])


def get_team_grades(game_date) -> pd.DataFrame:
    """Fetch full team grades for a game date. Cached 5 min."""
    conn = st.connection("snowflake")
    sql = TEAM_GRADES_SQL.format(game_date=game_date)
    return conn.query(sql, ttl=300)


def get_player_grades(game_date) -> pd.DataFrame:
    """Fetch full player grades for a game date. Cached 5 min."""
    conn = st.connection("snowflake")
    sql = PLAYER_GRADES_SQL.format(game_date=game_date)
    return conn.query(sql, ttl=300)
