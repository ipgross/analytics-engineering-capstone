"""SQL queries and cached data-fetch functions for the Odds page."""

import math
import streamlit as st
import pandas as pd


# ── Current odds (live dbt view, all bookmakers + consensus) ─────────────────

ODDS_CURRENT_SQL = """
SELECT
    event_id,
    game_date,
    home_team,
    away_team,
    commence_time_utc,
    bookmaker_key,
    bookmaker_title,
    bookmaker_last_update,
    market_key,
    side,
    outcome_price,
    outcome_point,
    implied_probability,
    consensus_price,
    consensus_line,
    consensus_implied_prob,
    num_bookmakers,
    best_price,
    worst_price,
    updated_at
FROM ipgross.live_nba__odds_current
WHERE game_date = '{game_date}'::DATE
ORDER BY commence_time_utc, home_team, bookmaker_key, market_key, side
"""

# ── Line movement snapshots (5-min archive, single game) ────────────────────

ODDS_MOVEMENT_SQL = """
SELECT
    snapshot_time,
    event_id,
    game_date,
    home_team,
    away_team,
    commence_time_utc,
    bookmaker_key,
    bookmaker_title,
    bookmaker_last_update,
    market_key,
    outcome_name AS side,
    outcome_price,
    outcome_point,
    CASE
        WHEN outcome_price > 0 THEN 100.0 / (outcome_price + 100.0)
        WHEN outcome_price < 0 THEN ABS(outcome_price) / (ABS(outcome_price) + 100.0)
    END AS implied_probability
FROM ipgross.archive_nba_odds_snapshots
WHERE event_id = '{event_id}'
ORDER BY bookmaker_last_update ASC, bookmaker_key, market_key, outcome_name
"""

# ── Distinct games with odds data (for game selector tiles) ─────────────────

ODDS_GAMES_SQL = """
SELECT
    event_id,
    game_date,
    home_team,
    away_team,
    MIN(commence_time_utc) AS commence_time_utc
FROM ipgross.live_nba__odds_current
WHERE game_date = '{game_date}'::DATE
GROUP BY event_id, game_date, home_team, away_team
ORDER BY commence_time_utc
"""

# ── Scoreboard status for games on a date ────────────────────────────────────

GAME_STATUS_SQL = """
SELECT
    game_id,
    game_date,
    status,
    period,
    clock,
    home_team_name,
    visitor_team_name,
    home_team_score,
    visitor_team_score,
    game_datetime,
    updated_at
FROM ipgross.live_nba_scoreboard
WHERE game_date = '{game_date}'::DATE
ORDER BY game_datetime ASC
"""

# ── Odds data freshness ─────────────────────────────────────────────────────

ODDS_FRESHNESS_SQL = """
SELECT
    MAX(updated_at) AS last_update,
    COUNT(DISTINCT event_id) AS event_count,
    MAX(game_date) AS game_date
FROM ipgross.live_nba__odds_current
"""

# ── Historical opening lines (cold path, for open vs current comparison) ────

OPENING_ODDS_SQL = """
SELECT
    ds AS game_date,
    event_id,
    home_team,
    away_team,
    bookmaker_key,
    market_key,
    outcome_name AS side,
    outcome_price,
    outcome_point
FROM ipgross.hist_nba_odds_open
WHERE ds = '{game_date}'::DATE
ORDER BY event_id, bookmaker_key, market_key, side
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Fetch functions
# ═══════════════════════════════════════════════════════════════════════════════


def get_odds_for_date(game_date) -> pd.DataFrame:
    """Fetch all current odds for a game date. Cached 30s (live data)."""
    conn = st.connection("snowflake")
    sql = ODDS_CURRENT_SQL.format(game_date=game_date)
    return conn.query(sql, ttl=30)


def get_odds_movement(event_id: str) -> pd.DataFrame:
    """Fetch line movement snapshots for a single game. Cached 60s."""
    conn = st.connection("snowflake")
    sql = ODDS_MOVEMENT_SQL.format(event_id=event_id.replace("'", "''"))
    return conn.query(sql, ttl=60)


def get_odds_games(game_date) -> pd.DataFrame:
    """Fetch distinct games with odds data for a date. Cached 60s."""
    conn = st.connection("snowflake")
    sql = ODDS_GAMES_SQL.format(game_date=game_date)
    return conn.query(sql, ttl=60)


def get_game_statuses(game_date) -> pd.DataFrame:
    """Fetch scoreboard statuses for games on a date. Cached 60s."""
    conn = st.connection("snowflake")
    sql = GAME_STATUS_SQL.format(game_date=game_date)
    return conn.query(sql, ttl=60)


def get_odds_freshness() -> dict:
    """Get odds data freshness info. Cached 30s."""
    conn = st.connection("snowflake")
    df = conn.query(ODDS_FRESHNESS_SQL, ttl=30)
    if df.empty:
        return {"last_update": None, "event_count": 0, "game_date": None}
    return {
        "last_update": df.iloc[0]["LAST_UPDATE"],
        "event_count": int(df.iloc[0]["EVENT_COUNT"]),
        "game_date": df.iloc[0]["GAME_DATE"],
    }


def get_opening_odds(game_date) -> pd.DataFrame:
    """Fetch historical opening lines for comparison. Cached 1h (daily data)."""
    conn = st.connection("snowflake")
    sql = OPENING_ODDS_SQL.format(game_date=game_date)
    return conn.query(sql, ttl=3600)


# ═══════════════════════════════════════════════════════════════════════════════
# Utility / formatting helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _is_missing(val) -> bool:
    """Check if a value is None or NaN."""
    if val is None:
        return True
    try:
        return math.isnan(float(val))
    except (TypeError, ValueError):
        return False


def american_to_implied_prob(price) -> float | None:
    """Convert American odds to implied probability (0-1 scale)."""
    if _is_missing(price):
        return None
    p = float(price)
    if p > 0:
        return 100.0 / (p + 100.0)
    elif p < 0:
        return abs(p) / (abs(p) + 100.0)
    return None


def fmt_price(price) -> str:
    """Format American odds: +150 or -110."""
    if _is_missing(price):
        return "N/A"
    p = int(float(price))
    return f"+{p}" if p > 0 else str(p)


def fmt_line(line) -> str:
    """Format spread/total line: +6, -4.5, 224.5."""
    if _is_missing(line):
        return "N/A"
    val = float(line)
    if abs(val) > 100:
        # Totals (e.g. 224.5) — no sign prefix
        return f"{val:g}"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:g}"


def fmt_prob(prob) -> str:
    """Format implied probability as percentage string."""
    if _is_missing(prob):
        return "N/A"
    return f"{float(prob) * 100:.1f}%"
