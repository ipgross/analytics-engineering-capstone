"""SQL queries and cached data-fetch functions for the Predictions page."""

import streamlit as st
import pandas as pd
from datetime import timedelta


# ── Date filter builder ────────────────────────────────────────────────────

def _build_date_filter(mode: str, logical_today, picked_date=None) -> str:
    """Return SQL WHERE fragment for the selected date mode.

    Args:
        mode: 'today', 'upcoming', or 'pick_a_date'.
        logical_today: Python date (6am CST rollover).
        picked_date: Required when mode='pick_a_date'.
    """
    today_str = str(logical_today)
    if mode == "today":
        return f"game_date = '{today_str}'::DATE"
    elif mode == "upcoming":
        tomorrow_str = str(logical_today + timedelta(days=1))
        week_str = str(logical_today + timedelta(days=7))
        return f"game_date BETWEEN '{tomorrow_str}'::DATE AND '{week_str}'::DATE"
    elif mode == "pick_a_date":
        return f"game_date = '{picked_date}'::DATE"
    return f"game_date = '{today_str}'::DATE"


# ── All-markets predictions query ──────────────────────────────────────────
# Returns one row per game with all three markets (spreads, h2h, totals) as columns.
# Drives from predictions, LEFT JOINs scoreboard for live status/scores.
# Date range is parameterized via {{date_filter}} placeholder.

PREDICTIONS_ALL_MARKETS_SQL = """
WITH games AS (
    SELECT DISTINCT
        game_date,
        season,
        home_team,
        away_team,
        commence_time_utc,
        commence_time_et
    FROM ipgross.mart_nba__game_predictions
    WHERE {date_filter}
),

scoreboard AS (
    SELECT
        game_id,
        game_date,
        season,
        status,
        period,
        clock,
        game_datetime,
        home_team_id,
        home_team_name,
        visitor_team_id,
        visitor_team_name,
        home_team_score,
        visitor_team_score,
        updated_at
    FROM ipgross.live_nba_scoreboard
),

predictions AS (
    SELECT
        game_date,
        event_id,
        home_team,
        away_team,
        market_key,
        side,
        consensus_line,
        consensus_price,
        consensus_implied_prob,
        num_bookmakers,
        best_price,
        cover_probability,
        expected_value,
        bet_rating,
        season_market_wins,
        season_market_total,
        projected_home_score,
        projected_away_score,
        projected_total,
        home_l10_pts,
        home_l10_off_rating,
        home_l10_def_rating,
        away_l10_pts,
        away_l10_off_rating,
        away_l10_def_rating,
        home_rest_days,
        away_rest_days,
        home_l10_possessions,
        away_l10_possessions,
        home_l10_efg_pct,
        home_l10_tov_pct,
        home_l10_orb_pct,
        home_l10_ftr,
        home_l10_opp_efg_pct,
        home_l10_opp_tov_pct,
        home_l10_opp_orb_pct,
        home_l10_opp_ftr,
        away_l10_efg_pct,
        away_l10_tov_pct,
        away_l10_orb_pct,
        away_l10_ftr,
        away_l10_opp_efg_pct,
        away_l10_opp_tov_pct,
        away_l10_opp_orb_pct,
        away_l10_opp_ftr
    FROM ipgross.mart_nba__game_predictions
    WHERE {date_filter}
),

-- Pivot spreads
spreads_home AS (
    SELECT * FROM predictions
    WHERE market_key = 'spreads' AND side = home_team
),
spreads_away AS (
    SELECT * FROM predictions
    WHERE market_key = 'spreads' AND side = away_team
),

-- Pivot moneyline
ml_home AS (
    SELECT * FROM predictions
    WHERE market_key = 'h2h' AND side = home_team
),
ml_away AS (
    SELECT * FROM predictions
    WHERE market_key = 'h2h' AND side = away_team
),

-- Pivot totals
totals_over AS (
    SELECT * FROM predictions
    WHERE market_key = 'totals' AND side = 'Over'
),
totals_under AS (
    SELECT * FROM predictions
    WHERE market_key = 'totals' AND side = 'Under'
)

SELECT
    s.game_id,
    g.game_date,
    g.season,
    COALESCE(s.status, 'Scheduled') AS status,
    COALESCE(s.period, 0) AS period,
    s.clock,
    COALESCE(s.game_datetime, g.commence_time_utc::TIMESTAMP_NTZ) AS game_datetime,
    COALESCE(s.home_team_name, g.home_team) AS home_team_name,
    COALESCE(s.visitor_team_name, g.away_team) AS visitor_team_name,
    s.home_team_score,
    s.visitor_team_score,
    s.updated_at,

    -- Spreads
    sp_h.consensus_line AS spread_home_line,
    sp_h.consensus_price AS spread_home_price,
    sp_h.expected_value AS spread_home_ev,
    sp_h.bet_rating AS spread_home_rating,
    sp_h.cover_probability AS spread_home_prob,
    sp_a.consensus_line AS spread_away_line,
    sp_a.consensus_price AS spread_away_price,
    sp_a.expected_value AS spread_away_ev,
    sp_a.bet_rating AS spread_away_rating,

    -- Moneyline
    ml_h.consensus_price AS ml_home_price,
    ml_h.expected_value AS ml_home_ev,
    ml_h.bet_rating AS ml_home_rating,
    ml_h.cover_probability AS ml_home_prob,
    ml_a.consensus_price AS ml_away_price,
    ml_a.expected_value AS ml_away_ev,
    ml_a.bet_rating AS ml_away_rating,

    -- Totals
    t_o.consensus_line AS total_line,
    t_o.consensus_price AS over_price,
    t_o.expected_value AS over_ev,
    t_o.bet_rating AS over_rating,
    t_o.cover_probability AS over_prob,
    t_u.consensus_price AS under_price,
    t_u.expected_value AS under_ev,
    t_u.bet_rating AS under_rating,

    -- Projections (same across all markets for a game)
    COALESCE(sp_h.projected_home_score, ml_h.projected_home_score, t_o.projected_home_score) AS projected_home_score,
    COALESCE(sp_h.projected_away_score, ml_h.projected_away_score, t_o.projected_away_score) AS projected_away_score,
    COALESCE(sp_h.projected_total, ml_h.projected_total, t_o.projected_total) AS projected_total,

    -- L10 stats for expansion
    COALESCE(sp_h.home_l10_pts, ml_h.home_l10_pts) AS home_l10_pts,
    COALESCE(sp_h.home_l10_off_rating, ml_h.home_l10_off_rating) AS home_l10_off_rating,
    COALESCE(sp_h.home_l10_def_rating, ml_h.home_l10_def_rating) AS home_l10_def_rating,
    COALESCE(sp_h.away_l10_pts, ml_h.away_l10_pts) AS away_l10_pts,
    COALESCE(sp_h.away_l10_off_rating, ml_h.away_l10_off_rating) AS away_l10_off_rating,
    COALESCE(sp_h.away_l10_def_rating, ml_h.away_l10_def_rating) AS away_l10_def_rating,

    -- Rest days & pace (game-level, same across markets)
    COALESCE(sp_h.home_rest_days, ml_h.home_rest_days, t_o.home_rest_days) AS home_rest_days,
    COALESCE(sp_h.away_rest_days, ml_h.away_rest_days, t_o.away_rest_days) AS away_rest_days,
    COALESCE(sp_h.home_l10_possessions, ml_h.home_l10_possessions) AS home_l10_possessions,
    COALESCE(sp_h.away_l10_possessions, ml_h.away_l10_possessions) AS away_l10_possessions,

    -- Four Factors L10 (home offense)
    COALESCE(sp_h.home_l10_efg_pct, ml_h.home_l10_efg_pct) AS home_l10_efg_pct,
    COALESCE(sp_h.home_l10_tov_pct, ml_h.home_l10_tov_pct) AS home_l10_tov_pct,
    COALESCE(sp_h.home_l10_orb_pct, ml_h.home_l10_orb_pct) AS home_l10_orb_pct,
    COALESCE(sp_h.home_l10_ftr, ml_h.home_l10_ftr) AS home_l10_ftr,
    -- Four Factors L10 (home defense)
    COALESCE(sp_h.home_l10_opp_efg_pct, ml_h.home_l10_opp_efg_pct) AS home_l10_opp_efg_pct,
    COALESCE(sp_h.home_l10_opp_tov_pct, ml_h.home_l10_opp_tov_pct) AS home_l10_opp_tov_pct,
    COALESCE(sp_h.home_l10_opp_orb_pct, ml_h.home_l10_opp_orb_pct) AS home_l10_opp_orb_pct,
    COALESCE(sp_h.home_l10_opp_ftr, ml_h.home_l10_opp_ftr) AS home_l10_opp_ftr,
    -- Four Factors L10 (away offense)
    COALESCE(sp_h.away_l10_efg_pct, ml_h.away_l10_efg_pct) AS away_l10_efg_pct,
    COALESCE(sp_h.away_l10_tov_pct, ml_h.away_l10_tov_pct) AS away_l10_tov_pct,
    COALESCE(sp_h.away_l10_orb_pct, ml_h.away_l10_orb_pct) AS away_l10_orb_pct,
    COALESCE(sp_h.away_l10_ftr, ml_h.away_l10_ftr) AS away_l10_ftr,
    -- Four Factors L10 (away defense)
    COALESCE(sp_h.away_l10_opp_efg_pct, ml_h.away_l10_opp_efg_pct) AS away_l10_opp_efg_pct,
    COALESCE(sp_h.away_l10_opp_tov_pct, ml_h.away_l10_opp_tov_pct) AS away_l10_opp_tov_pct,
    COALESCE(sp_h.away_l10_opp_orb_pct, ml_h.away_l10_opp_orb_pct) AS away_l10_opp_orb_pct,
    COALESCE(sp_h.away_l10_opp_ftr, ml_h.away_l10_opp_ftr) AS away_l10_opp_ftr,

    -- Per-market detail columns (eliminates N+1 query)
    sp_h.season_market_wins AS spread_home_season_wins,
    sp_h.season_market_total AS spread_home_season_total,
    sp_a.season_market_wins AS spread_away_season_wins,
    sp_a.season_market_total AS spread_away_season_total,
    sp_a.cover_probability AS spread_away_prob,
    ml_h.season_market_wins AS ml_home_season_wins,
    ml_h.season_market_total AS ml_home_season_total,
    ml_a.season_market_wins AS ml_away_season_wins,
    ml_a.season_market_total AS ml_away_season_total,
    ml_a.cover_probability AS ml_away_prob,
    t_o.season_market_wins AS over_season_wins,
    t_o.season_market_total AS over_season_total,
    t_u.season_market_wins AS under_season_wins,
    t_u.season_market_total AS under_season_total,
    t_u.cover_probability AS under_prob,

    -- Best bet: highest rating across all markets for this game
    GREATEST(
        COALESCE(sp_h.bet_rating, 0),
        COALESCE(ml_h.bet_rating, 0),
        COALESCE(t_o.bet_rating, 0)
    ) AS best_rating,
    CASE
        WHEN COALESCE(sp_h.bet_rating, 0) >= COALESCE(ml_h.bet_rating, 0)
             AND COALESCE(sp_h.bet_rating, 0) >= COALESCE(t_o.bet_rating, 0)
        THEN 'spreads'
        WHEN COALESCE(ml_h.bet_rating, 0) >= COALESCE(t_o.bet_rating, 0)
        THEN 'h2h'
        ELSE 'totals'
    END AS best_market,
    CASE
        WHEN COALESCE(sp_h.bet_rating, 0) >= COALESCE(ml_h.bet_rating, 0)
             AND COALESCE(sp_h.bet_rating, 0) >= COALESCE(t_o.bet_rating, 0)
        THEN sp_h.expected_value
        WHEN COALESCE(ml_h.bet_rating, 0) >= COALESCE(t_o.bet_rating, 0)
        THEN ml_h.expected_value
        ELSE t_o.expected_value
    END AS best_ev

FROM games g
LEFT JOIN scoreboard s
    ON g.game_date = s.game_date AND g.home_team = s.home_team_name
LEFT JOIN spreads_home sp_h
    ON g.game_date = sp_h.game_date AND g.home_team = sp_h.home_team
LEFT JOIN spreads_away sp_a
    ON g.game_date = sp_a.game_date AND g.home_team = sp_a.home_team
LEFT JOIN ml_home ml_h
    ON g.game_date = ml_h.game_date AND g.home_team = ml_h.home_team
LEFT JOIN ml_away ml_a
    ON g.game_date = ml_a.game_date AND g.home_team = ml_a.home_team
LEFT JOIN totals_over t_o
    ON g.game_date = t_o.game_date AND g.home_team = t_o.home_team
LEFT JOIN totals_under t_u
    ON g.game_date = t_u.game_date AND g.home_team = t_u.home_team

ORDER BY g.game_date ASC, COALESCE(s.game_datetime, g.commence_time_utc::TIMESTAMP_NTZ) ASC
"""


# ── Best bets query (top EV across all markets) ────────────────────────────
# Returns individual bet recommendations sorted by EV descending.

BEST_BETS_SQL = """
SELECT
    game_date,
    home_team,
    away_team,
    market_key,
    side,
    consensus_line,
    consensus_price,
    expected_value,
    bet_rating,
    cover_probability
FROM ipgross.mart_nba__game_predictions
WHERE bet_rating >= 4
  AND {date_filter}
ORDER BY expected_value DESC
LIMIT 10
"""


def get_predictions_all_markets(mode: str = "today", logical_today=None, picked_date=None) -> pd.DataFrame:
    """Fetch predictions with all markets pivoted to columns.

    Args:
        mode: 'today', 'upcoming', or 'pick_a_date'.
        logical_today: Python date (6am CST rollover).
        picked_date: Required when mode='pick_a_date'.

    Returns one row per game with spreads, ML, and totals columns.
    Cached 60s (matches scoreboard refresh).
    """
    date_filter = _build_date_filter(mode, logical_today, picked_date)
    sql = PREDICTIONS_ALL_MARKETS_SQL.format(date_filter=date_filter)
    conn = st.connection("snowflake")
    return conn.query(sql, ttl=60)


def get_best_bets(mode: str = "today", logical_today=None, picked_date=None) -> pd.DataFrame:
    """Fetch top value bets (4+ stars) sorted by EV. Cached 60s."""
    date_filter = _build_date_filter(mode, logical_today, picked_date)
    sql = BEST_BETS_SQL.format(date_filter=date_filter)
    conn = st.connection("snowflake")
    return conn.query(sql, ttl=60)


def categorize_predictions(df: pd.DataFrame) -> dict:
    """Split predictions into LIVE, UPCOMING, and FINAL sections.

    Live: period > 0 AND status != 'Final'
    Upcoming: period == 0 AND status != 'Final'
    Final: status == 'Final'
    """
    if df.empty:
        return {"live": df, "upcoming": df, "final": df}

    period = df["PERIOD"].fillna(0).astype(int)
    is_final = df["STATUS"] == "Final"

    live = df[(period > 0) & (~is_final)].copy()
    upcoming = df[(period == 0) & (~is_final)].copy()
    final = df[is_final].copy()

    return {"live": live, "upcoming": upcoming, "final": final}


def get_freshness() -> dict:
    """Get scoreboard data freshness info."""
    conn = st.connection("snowflake")
    df = conn.query(
        "SELECT MAX(updated_at) AS last_update, MAX(game_date) AS game_date, "
        "COUNT(*) AS game_count FROM ipgross.live_nba_scoreboard",
        ttl=60,
    )
    if df.empty:
        return {"last_update": None, "game_count": 0, "game_date": None}
    return {
        "last_update": df.iloc[0]["LAST_UPDATE"],
        "game_count": int(df.iloc[0]["GAME_COUNT"]),
        "game_date": df.iloc[0]["GAME_DATE"],
    }
