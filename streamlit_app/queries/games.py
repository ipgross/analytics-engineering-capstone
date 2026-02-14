"""SQL queries and cached data-fetch functions for the Games page."""

import streamlit as st
import pandas as pd

# ── Scoreboard query (live data, short cache) ──────────────────────────────
# Filters to the most recent game_date in the scoreboard (= "today" in NBA terms).

SCOREBOARD_SQL = """
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
    home_team_score,
    visitor_team_id,
    visitor_team_name,
    visitor_team_score,
    home_q1, home_q2, home_q3, home_q4,
    home_ot1, home_ot2, home_ot3,
    visitor_q1, visitor_q2, visitor_q3, visitor_q4,
    visitor_ot1, visitor_ot2, visitor_ot3,
    home_timeouts_remaining, visitor_timeouts_remaining,
    home_in_bonus, visitor_in_bonus,
    postseason,
    postponed,
    updated_at
FROM ipgross.live_nba_scoreboard
ORDER BY game_datetime ASC
"""

# ── Predictions query (daily dbt data, long cache) ─────────────────────────
# Pivots 2 rows per game per market into home/away columns on a single row.

PREDICTIONS_SQL = """
WITH predictions AS (
    SELECT
        game_date,
        home_team,
        away_team,
        market_key,
        side,
        consensus_line,
        consensus_price,
        projected_home_score,
        projected_away_score,
        projected_total,
        cover_probability,
        expected_value,
        bet_rating
    FROM ipgross.mart_nba__game_predictions
),

home_side AS (
    SELECT *
    FROM predictions
    WHERE (market_key IN ('spreads', 'h2h') AND side = home_team)
       OR (market_key = 'totals' AND side = 'Over')
),

away_side AS (
    SELECT *
    FROM predictions
    WHERE (market_key IN ('spreads', 'h2h') AND side = away_team)
       OR (market_key = 'totals' AND side = 'Under')
)

SELECT
    h.game_date,
    h.home_team,
    h.away_team,
    h.market_key,
    h.consensus_line     AS home_consensus_line,
    h.consensus_price    AS home_consensus_price,
    h.cover_probability  AS home_cover_prob,
    h.expected_value     AS home_ev,
    h.bet_rating         AS home_bet_rating,
    a.consensus_line     AS away_consensus_line,
    a.consensus_price    AS away_consensus_price,
    a.cover_probability  AS away_cover_prob,
    a.expected_value     AS away_ev,
    a.bet_rating         AS away_bet_rating,
    h.projected_home_score,
    h.projected_away_score,
    h.projected_total
FROM home_side h
INNER JOIN away_side a
    ON h.game_date = a.game_date
    AND h.home_team = a.home_team
    AND h.market_key = a.market_key
"""

# ── Game results query (live view, short cache) ─────────────────────────
# One row per completed game with all betting outcomes denormalized.
# Uses live view (instant results when game goes Final) instead of cold-path mart.

GAME_RESULTS_SQL = """
SELECT
    game_date,
    game_id,
    home_team_name,
    visitor_team_name,
    home_team_score,
    visitor_team_score,
    score_margin,
    total_points,
    winner,
    home_spread,
    home_spread_price,
    home_spread_result,
    away_spread,
    away_spread_price,
    away_spread_result,
    total_line,
    over_price,
    over_result,
    home_ml_price,
    home_ml_result,
    away_ml_price,
    away_ml_result
FROM ipgross.mart_nba__game_results
"""

# ── Game grades query (live view, short cache) ──────────────────────────
# Two rows per completed game (home + away) with performance letter grades.

GAME_GRADES_SQL = """
SELECT
    game_id,
    game_date,
    team_id,
    team_name,
    is_home,
    performance_grade,
    off_performance_grade,
    def_performance_grade
FROM ipgross.mart_nba__game_grades
"""


# ── Single-game predictions (all markets, dialog detail) ─────────────────
# Raw grain from mart: one row per (event_id, market_key, side).
# Used by the Prediction tab in the game detail dialog.

GAME_PREDICTIONS_SQL = """
SELECT
    game_date,
    event_id,
    season,
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
WHERE game_date = '{game_date}'
  AND home_team = '{home_team}'
"""


# ── ATS records (matchup tab, daily dbt data) ────────────────────────────

ATS_RECORDS_SQL = """
SELECT
    season, team_name, games_played,
    ats_wins, ats_losses, ats_pushes, ats_pct, ats_rank,
    home_ats_wins, home_ats_losses, home_ats_pushes,
    away_ats_wins, away_ats_losses, away_ats_pushes,
    su_wins, su_losses, su_pct, su_rank,
    home_su_wins, home_su_losses,
    away_su_wins, away_su_losses,
    over_wins, under_wins, ou_pushes
FROM ipgross.mart_nba__team_ats_records
WHERE season = '{season}'
  AND team_name IN ('{home_team}', '{away_team}')
"""

# ── Team matchup stats (matchup tab, daily dbt data) ─────────────────────

MATCHUP_STATS_SQL = """
SELECT
    season, team_id, team_name, abbreviation,
    games_played,
    avg_pts, avg_opp_pts, avg_point_diff,
    avg_fgm, avg_fga, avg_fg_pct,
    avg_fg3m, avg_fg3a, avg_fg3_pct,
    avg_ftm, avg_fta, avg_ft_pct,
    avg_reb, avg_oreb, avg_dreb,
    avg_ast, avg_turnovers, avg_stl, avg_blk, avg_pf,
    avg_possessions, avg_off_rating, avg_def_rating,
    home_avg_pts, away_avg_pts,
    home_avg_off_rating, away_avg_off_rating,
    home_avg_def_rating, away_avg_def_rating,
    off_rating_rank, def_rating_rank, point_diff_rank
FROM ipgross.mart_nba__team_matchup_stats
WHERE season = '{season}'
  AND team_name IN ('{home_team}', '{away_team}')
"""

# ── Recent results per team (matchup tab, daily dbt data) ────────────────

RECENT_RESULTS_SQL = """
SELECT
    game_date, game_id, season,
    home_team_name, visitor_team_name,
    home_team_score, visitor_team_score,
    score_margin, total_points, winner,
    home_spread, home_spread_result,
    away_spread, away_spread_result,
    total_line, over_result,
    CASE WHEN home_team_name = '{team_name}' THEN 'home' ELSE 'away' END AS venue,
    CASE WHEN home_team_name = '{team_name}' THEN visitor_team_name
         ELSE home_team_name END AS opponent,
    CASE WHEN winner = '{team_name}' THEN 'W' ELSE 'L' END AS result,
    CASE WHEN home_team_name = '{team_name}' THEN home_team_score
         ELSE visitor_team_score END AS team_score,
    CASE WHEN home_team_name = '{team_name}' THEN visitor_team_score
         ELSE home_team_score END AS opp_score,
    CASE WHEN home_team_name = '{team_name}' THEN home_spread_result
         ELSE away_spread_result END AS ats_result,
    CASE WHEN home_team_name = '{team_name}' THEN home_spread
         ELSE away_spread END AS spread
FROM ipgross.mart_nba__game_results
WHERE season = '{season}'
  AND (home_team_name = '{team_name}' OR visitor_team_name = '{team_name}')
  AND game_date < '{game_date}'::DATE
ORDER BY game_date DESC
LIMIT 10
"""

# ── Head-to-head season series (matchup tab) ─────────────────────────────

H2H_SERIES_SQL = """
SELECT
    game_date, game_id,
    home_team_name, visitor_team_name,
    home_team_score, visitor_team_score,
    score_margin, total_points, winner,
    home_spread, home_spread_result,
    away_spread, away_spread_result,
    total_line, over_result
FROM ipgross.mart_nba__game_results
WHERE season = '{season}'
  AND (
    (home_team_name = '{home_team}' AND visitor_team_name = '{away_team}')
    OR
    (home_team_name = '{away_team}' AND visitor_team_name = '{home_team}')
  )
ORDER BY game_date DESC
"""

# ── Rest days (matchup tab) ──────────────────────────────────────────────

REST_DAYS_SQL = """
SELECT
    team_name,
    DATEDIFF('day', MAX(game_date), '{game_date}'::DATE) AS rest_days,
    MAX(game_date) AS last_game_date
FROM (
    -- Live scoreboard: most recent Final games (last ~2 days)
    SELECT home_team_name AS team_name, game_date
    FROM ipgross.live_nba_scoreboard
    WHERE home_team_name IN ('{home_team}', '{away_team}')
      AND game_date < '{game_date}'::DATE
      AND status = 'Final'
    UNION ALL
    SELECT visitor_team_name AS team_name, game_date
    FROM ipgross.live_nba_scoreboard
    WHERE visitor_team_name IN ('{home_team}', '{away_team}')
      AND game_date < '{game_date}'::DATE
      AND status = 'Final'
    UNION ALL
    -- Historical: all completed games (no season filter — rest is season-agnostic)
    SELECT home_team_name AS team_name, game_date
    FROM ipgross.mart_nba__game_results
    WHERE home_team_name IN ('{home_team}', '{away_team}')
      AND game_date < '{game_date}'::DATE
    UNION ALL
    SELECT visitor_team_name AS team_name, game_date
    FROM ipgross.mart_nba__game_results
    WHERE visitor_team_name IN ('{home_team}', '{away_team}')
      AND game_date < '{game_date}'::DATE
) sub
GROUP BY team_name
"""


def get_scoreboard() -> pd.DataFrame:
    """Fetch full live scoreboard (all dates in table). Cached 60s."""
    conn = st.connection("snowflake")
    return conn.query(SCOREBOARD_SQL, ttl=60)


def get_available_dates() -> list:
    """Return sorted list of distinct game_dates in the scoreboard (descending)."""
    df = get_scoreboard()
    if df.empty:
        return []
    dates = sorted(df["GAME_DATE"].unique(), reverse=True)
    return list(dates)


def get_predictions(market_key: str) -> pd.DataFrame:
    """Fetch pre-computed predictions for a market. Cached 1 hour (daily dbt data)."""
    conn = st.connection("snowflake")
    df = conn.query(PREDICTIONS_SQL, ttl=3600)
    return df[df["MARKET_KEY"] == market_key].copy()


def get_game_results() -> pd.DataFrame:
    """Fetch completed game results from live view. Cached 60s."""
    conn = st.connection("snowflake")
    return conn.query(GAME_RESULTS_SQL, ttl=300)


def get_game_grades() -> pd.DataFrame:
    """Fetch team performance grades from live view. Cached 60s."""
    conn = st.connection("snowflake")
    return conn.query(GAME_GRADES_SQL, ttl=300)


def get_games(market_key: str, game_date=None) -> pd.DataFrame:
    """Join scoreboard with predictions for the selected market.

    Args:
        market_key: 'spreads', 'h2h', or 'totals'.
        game_date: Filter to a specific game_date. None returns all.

    Returns one row per game with scoreboard + prediction columns.
    """
    scoreboard = get_scoreboard()
    if scoreboard.empty:
        return scoreboard

    if game_date is not None:
        scoreboard = scoreboard[scoreboard["GAME_DATE"] == game_date].copy()
        if scoreboard.empty:
            return scoreboard

    predictions = get_predictions(market_key)

    if predictions.empty:
        return scoreboard

    merged = scoreboard.merge(
        predictions,
        left_on=["GAME_DATE", "HOME_TEAM_NAME"],
        right_on=["GAME_DATE", "HOME_TEAM"],
        how="left",
        suffixes=("", "_pred"),
    )
    return merged


def get_game_results_for_date(game_date) -> dict:
    """Fetch game results keyed by (GAME_DATE, HOME_TEAM_NAME) for a date."""
    results_df = get_game_results()
    if results_df.empty:
        return {}
    results_df = results_df[results_df["GAME_DATE"] == game_date]
    results_map = {}
    for _, row in results_df.iterrows():
        key = (row["GAME_DATE"], row["HOME_TEAM_NAME"])
        results_map[key] = row.to_dict()
    return results_map


def get_game_grades_for_date(game_date) -> dict:
    """Fetch game grades keyed by (GAME_DATE, TEAM_NAME) for a date."""
    grades_df = get_game_grades()
    if grades_df.empty:
        return {}
    grades_df = grades_df[grades_df["GAME_DATE"] == game_date]
    grades_map = {}
    for _, row in grades_df.iterrows():
        key = (row["GAME_DATE"], row["TEAM_NAME"])
        grades_map[key] = row.to_dict()
    return grades_map


def get_predictions_for_game(game_date, home_team: str) -> pd.DataFrame:
    """Fetch all prediction rows for a specific game (all markets, both sides).

    Returns up to 6 rows: 2 per market (home/away for spreads/h2h,
    Over/Under for totals). Cached 1 hour (daily dbt data).
    """
    conn = st.connection("snowflake")
    sql = GAME_PREDICTIONS_SQL.format(
        game_date=game_date,
        home_team=home_team.replace("'", "''"),
    )
    return conn.query(sql, ttl=3600)


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


# ── Play-by-play query (single game, short cache) ─────────────────────────

PLAYS_SQL = """
SELECT
    game_id,
    play_id,
    period,
    period_display,
    clock,
    action_type,
    description,
    team_id,
    team_name,
    scoring_play,
    shooting_play,
    score_value,
    home_score,
    away_score
FROM ipgross.live_nba_plays
WHERE game_id = {game_id}
ORDER BY play_id DESC
"""

# ── Box score query (single game, short cache) ────────────────────────────

BOX_SCORE_SQL = """
SELECT
    game_id, player_id, player_name, team_id, team_name,
    is_home, min, pts, reb, ast, stl, blk, turnover, pf,
    fgm, fga, fg_pct, fg3m, fg3a, fg3_pct, ftm, fta, ft_pct
FROM ipgross.live_nba_player_box_scores
WHERE game_id = {game_id}
ORDER BY is_home DESC, pts DESC
"""


def get_plays_for_game(game_id: int) -> pd.DataFrame:
    """Fetch play-by-play data for a single game. Cached 30s."""
    conn = st.connection("snowflake")
    sql = PLAYS_SQL.format(game_id=int(game_id))
    return conn.query(sql, ttl=30)


def get_box_score_for_game(game_id: int) -> pd.DataFrame:
    """Fetch player box scores for a single game. Cached 30s."""
    conn = st.connection("snowflake")
    sql = BOX_SCORE_SQL.format(game_id=int(game_id))
    return conn.query(sql, ttl=30)


# ── Live odds query (single game, short cache) ──────────────────────────

LIVE_ODDS_SQL = """
SELECT
    event_id, game_date, home_team, away_team,
    bookmaker_key, bookmaker_title, bookmaker_last_update,
    market_key, outcome_name, outcome_price, outcome_point, updated_at
FROM ipgross.live_nba_odds
WHERE home_team = '{home_team}'
  AND game_date = '{game_date}'::DATE
ORDER BY bookmaker_key, market_key, outcome_name
"""

# ── Team box score query (single game, short cache) ──────────────────────

TEAM_BOX_SCORE_SQL = """
SELECT
    game_id, team_id, team_name, is_home,
    pts, reb, oreb, dreb, ast, stl, blk, turnovers, pf,
    fgm, fga, fg_pct, fg3m, fg3a, fg3_pct, ftm, fta, ft_pct,
    est_possessions
FROM ipgross.live_nba_team_box_scores
WHERE game_id = {game_id}
ORDER BY is_home DESC
"""


def get_live_odds_for_game(game_date, home_team: str) -> pd.DataFrame:
    """Fetch live odds for a single game (all bookmakers, all markets). Cached 30s."""
    conn = st.connection("snowflake")
    sql = LIVE_ODDS_SQL.format(
        game_date=game_date,
        home_team=home_team.replace("'", "''"),
    )
    return conn.query(sql, ttl=30)


def get_team_box_score_for_game(game_id: int) -> pd.DataFrame:
    """Fetch team-level aggregated box scores for a single game. Cached 30s."""
    conn = st.connection("snowflake")
    sql = TEAM_BOX_SCORE_SQL.format(game_id=int(game_id))
    return conn.query(sql, ttl=30)


def get_ats_records(season: str, home_team: str, away_team: str) -> pd.DataFrame:
    """Fetch ATS/SU/O/U records for two teams in a season. Cached 1 hour."""
    conn = st.connection("snowflake")
    sql = ATS_RECORDS_SQL.format(
        season=season,
        home_team=home_team.replace("'", "''"),
        away_team=away_team.replace("'", "''"),
    )
    return conn.query(sql, ttl=3600)


def get_matchup_stats(season: str, home_team: str, away_team: str) -> pd.DataFrame:
    """Fetch season matchup stats for two teams. Cached 1 hour."""
    conn = st.connection("snowflake")
    sql = MATCHUP_STATS_SQL.format(
        season=season,
        home_team=home_team.replace("'", "''"),
        away_team=away_team.replace("'", "''"),
    )
    return conn.query(sql, ttl=3600)


def get_recent_results(season: str, team_name: str, game_date) -> pd.DataFrame:
    """Fetch last 10 game results for a team before game_date. Cached 1 hour."""
    conn = st.connection("snowflake")
    sql = RECENT_RESULTS_SQL.format(
        season=season,
        team_name=team_name.replace("'", "''"),
        game_date=game_date,
    )
    return conn.query(sql, ttl=3600)


def get_h2h_series(season: str, home_team: str, away_team: str) -> pd.DataFrame:
    """Fetch head-to-head games between two teams this season. Cached 1 hour."""
    conn = st.connection("snowflake")
    sql = H2H_SERIES_SQL.format(
        season=season,
        home_team=home_team.replace("'", "''"),
        away_team=away_team.replace("'", "''"),
    )
    return conn.query(sql, ttl=3600)


def get_rest_days(
    game_date, home_team: str, away_team: str,
) -> dict:
    """Fetch rest days for both teams. Returns {team_name: rest_days}. Cached 5 min."""
    conn = st.connection("snowflake")
    sql = REST_DAYS_SQL.format(
        game_date=game_date,
        home_team=home_team.replace("'", "''"),
        away_team=away_team.replace("'", "''"),
    )
    df = conn.query(sql, ttl=300)
    if df.empty:
        return {}
    return {row["TEAM_NAME"]: int(row["REST_DAYS"]) for _, row in df.iterrows()}


def categorize_games(df: pd.DataFrame) -> dict:
    """Split games into LIVE, FINAL, UPCOMING sections.

    Uses period field (0 = not started, 1-4 = quarters, 5+ = OT)
    and status field ('Final' for completed games).
    """
    period = df["PERIOD"].fillna(0).astype(int)
    is_final = df["STATUS"] == "Final"

    live = df[(period > 0) & (~is_final)].copy()
    final = df[is_final].copy()
    upcoming = df[(period == 0) & (~is_final)].copy()

    return {"live": live, "final": final, "upcoming": upcoming}
