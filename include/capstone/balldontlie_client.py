"""
BallDontLie API client for NBA game data.
Fetches game results, box scores, and team reference data.
"""
import logging
import time
from typing import Optional
from zoneinfo import ZoneInfo

import requests

from include.capstone.config import (
    BALLDONTLIE_API_KEY,
    BALLDONTLIE_BASE_URL,
    get_season_for_date,
)

logger = logging.getLogger(__name__)
EASTERN = ZoneInfo("America/New_York")


MAX_RETRIES = 3
RETRY_BACKOFF = [5, 30, 120]


def _make_request(endpoint: str, params: Optional[dict] = None) -> dict:
    """
    Make authenticated request to BallDontLie API with retry logic.

    Retries on timeouts and server errors with exponential backoff.

    Args:
        endpoint: API endpoint (e.g., '/games')
        params: Query parameters

    Returns:
        JSON response dict
    """
    url = f"{BALLDONTLIE_BASE_URL}{endpoint}"
    headers = {"Authorization": BALLDONTLIE_API_KEY}

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.Timeout, requests.exceptions.HTTPError) as e:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
            logger.warning(
                f"BallDontLie request failed (attempt {attempt + 1}): {e}. Retrying in {wait}s"
            )
            time.sleep(wait)

    raise Exception(f"BallDontLie request failed after {MAX_RETRIES} attempts")


def fetch_games_for_date(date_str: str) -> tuple[list[dict], dict]:
    """
    Fetch completed NBA games for a specific date.

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        Tuple of (processed game records, raw API response)
    """
    t0 = time.monotonic()
    logger.info(f"Fetching games for {date_str}")

    # BallDontLie uses dates[] array parameter
    params = {"dates[]": date_str, "per_page": 100}

    raw_response = _make_request("/games", params)
    games_data = raw_response.get("data", [])

    logger.info(f"Found {len(games_data)} games for {date_str}")

    # Filter to completed games only and flatten
    records = []
    season = get_season_for_date(date_str)

    for game in games_data:
        # Only process completed games
        if game.get("status") != "Final":
            logger.info(f"Skipping game {game.get('id')} - status: {game.get('status')}")
            continue

        home_team = game.get("home_team", {})
        visitor_team = game.get("visitor_team", {})

        record = {
            "game_id": game.get("id"),
            "season": season,
            "game_date": game.get("date"),
            "status": game.get("status"),
            "home_team_id": home_team.get("id"),
            "home_team_name": home_team.get("full_name"),
            "home_team_score": game.get("home_team_score"),
            "visitor_team_id": visitor_team.get("id"),
            "visitor_team_name": visitor_team.get("full_name"),
            "visitor_team_score": game.get("visitor_team_score"),
            "postseason": game.get("postseason", False),
        }
        records.append(record)

    elapsed = time.monotonic() - t0
    logger.info(
        f"fetch_games | ds={date_str} | games={len(records)}"
        f" | elapsed_sec={elapsed:.2f}"
    )
    return records, raw_response


def fetch_box_scores_for_date(date_str: str) -> tuple[list[dict], dict]:
    """
    Fetch player-level box scores for all games on a date.

    Returns raw player stats - aggregation to team level happens in dbt.

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        Tuple of (player box score records, raw API response)
    """
    t0 = time.monotonic()
    logger.info(f"Fetching box scores for {date_str}")

    params = {"date": date_str}
    raw_response = _make_request("/box_scores", params)
    games_data = raw_response.get("data", [])

    logger.info(f"Found {len(games_data)} games with box scores for {date_str}")

    records = []

    for game_data in games_data:
        # Game fields are at top level (not nested under a "game" key)
        if game_data.get("status") != "Final":
            logger.info(f"Skipping game {game_data.get('id')} - status: {game_data.get('status')}")
            continue

        game_id = game_data.get("id")
        game_date = game_data.get("date")
        season_year = game_data.get("season")

        home_team = game_data.get("home_team", {})
        visitor_team = game_data.get("visitor_team", {})

        # Players are nested under home_team.players[] and visitor_team.players[]
        for team_obj, is_home in [(home_team, True), (visitor_team, False)]:
            team_id = team_obj.get("id")
            team_name = team_obj.get("full_name")

            for player_data in team_obj.get("players", []):
                player = player_data.get("player", {})

                record = {
                    "game_id": game_id,
                    "player_id": player.get("id"),
                    "player_name": f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(),
                    "team_id": team_id,
                    "team_name": team_name,
                    "season": season_year,
                    "game_date": game_date,
                    "is_home": is_home,
                    # Raw stats - team aggregation happens in dbt
                    "min": player_data.get("min"),
                    "pts": player_data.get("pts"),
                    "reb": player_data.get("reb"),
                    "oreb": player_data.get("oreb"),
                    "dreb": player_data.get("dreb"),
                    "ast": player_data.get("ast"),
                    "stl": player_data.get("stl"),
                    "blk": player_data.get("blk"),
                    "turnover": player_data.get("turnover"),
                    "pf": player_data.get("pf"),
                    "fgm": player_data.get("fgm"),
                    "fga": player_data.get("fga"),
                    "fg_pct": player_data.get("fg_pct"),
                    "fg3m": player_data.get("fg3m"),
                    "fg3a": player_data.get("fg3a"),
                    "fg3_pct": player_data.get("fg3_pct"),
                    "ftm": player_data.get("ftm"),
                    "fta": player_data.get("fta"),
                    "ft_pct": player_data.get("ft_pct"),
                }
                records.append(record)

    elapsed = time.monotonic() - t0
    logger.info(
        f"fetch_box_scores | ds={date_str} | players={len(records)}"
        f" | elapsed_sec={elapsed:.2f}"
    )
    return records, raw_response


def fetch_all_teams() -> tuple[list[dict], dict]:
    """
    Fetch all NBA team reference data.

    One-time load - teams don't change often.

    Returns:
        Tuple of (team records, raw API response)
    """
    logger.info("Fetching all NBA teams")

    params = {"per_page": 100}
    raw_response = _make_request("/teams", params)
    teams_data = raw_response.get("data", [])

    logger.info(f"Found {len(teams_data)} teams")

    records = []
    for team in teams_data:
        # Filter out defunct/historical teams (BAA/NBL era) — they have blank division
        if not (team.get("division") or "").strip():
            continue

        record = {
            "team_id": team.get("id"),
            "full_name": team.get("full_name"),
            "name": team.get("name"),
            "city": team.get("city"),
            "abbreviation": team.get("abbreviation"),
            "conference": team.get("conference"),
            "division": team.get("division"),
        }
        records.append(record)

    logger.info(f"Processed {len(records)} NBA team records (filtered {len(teams_data) - len(records)} defunct)")
    return records, raw_response


# ===========================================
# HOT PATH — Live Fetch Functions
# ===========================================

def fetch_live_games(date_str: str) -> list[dict]:
    """
    Fetch ALL NBA games for a date (scheduled, live, and final).

    Unlike fetch_games_for_date(), this does NOT filter to Final only.
    Includes period, clock, and quarter scores for live dashboard display.

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        List of game records (no raw_response — no S3 archiving for hot path)
    """
    t0 = time.monotonic()
    logger.info(f"Fetching live games for {date_str}")

    params = {"dates[]": date_str, "per_page": 100}
    raw_response = _make_request("/games", params)
    games_data = raw_response.get("data", [])

    records = []
    for game in games_data:
        home_team = game.get("home_team", {})
        visitor_team = game.get("visitor_team", {})

        records.append({
            "game_id": game.get("id"),
            "game_date": game.get("date"),
            "season": game.get("season"),
            "status": game.get("status", ""),
            "period": game.get("period"),
            "clock": game.get("time"),
            "game_datetime": game.get("datetime"),
            "home_team_id": home_team.get("id"),
            "home_team_name": home_team.get("full_name"),
            "home_team_score": game.get("home_team_score", 0) or 0,
            "home_q1": game.get("home_q1"),
            "home_q2": game.get("home_q2"),
            "home_q3": game.get("home_q3"),
            "home_q4": game.get("home_q4"),
            "home_ot1": game.get("home_ot1"),
            "home_ot2": game.get("home_ot2"),
            "home_ot3": game.get("home_ot3"),
            "home_timeouts_remaining": game.get("home_timeouts_remaining"),
            "home_in_bonus": game.get("home_in_bonus"),
            "visitor_team_id": visitor_team.get("id"),
            "visitor_team_name": visitor_team.get("full_name"),
            "visitor_team_score": game.get("visitor_team_score", 0) or 0,
            "visitor_q1": game.get("visitor_q1"),
            "visitor_q2": game.get("visitor_q2"),
            "visitor_q3": game.get("visitor_q3"),
            "visitor_q4": game.get("visitor_q4"),
            "visitor_ot1": game.get("visitor_ot1"),
            "visitor_ot2": game.get("visitor_ot2"),
            "visitor_ot3": game.get("visitor_ot3"),
            "visitor_timeouts_remaining": game.get("visitor_timeouts_remaining"),
            "visitor_in_bonus": game.get("visitor_in_bonus"),
            "postseason": game.get("postseason", False),
            "postponed": game.get("postponed", False),
        })

    elapsed = time.monotonic() - t0
    logger.info(
        f"fetch_live_games | ds={date_str} | games={len(records)}"
        f" | elapsed_sec={elapsed:.2f}"
    )
    return records


def fetch_live_box_scores(date_str: str) -> list[dict]:
    """
    Fetch player box scores for ALL games on a date (live + final).

    Unlike fetch_box_scores_for_date(), this does NOT filter to Final only.
    Includes game status on each record for the team VIEW.

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        List of player box score records
    """
    t0 = time.monotonic()
    logger.info(f"Fetching live box scores for {date_str}")

    params = {"date": date_str}
    raw_response = _make_request("/box_scores", params)
    games_data = raw_response.get("data", [])

    records = []
    for game_data in games_data:
        # Skip scheduled games — no box scores until game starts
        status = game_data.get("status", "")
        if status and status not in ("Final",) and "Qtr" not in status and "Half" not in status and "OT" not in status:
            # Status is a time string like "7:00 pm ET" — scheduled game
            # Only skip if it looks like a time (contains "pm" or "am")
            if "pm" in status.lower() or "am" in status.lower():
                continue

        game_id = game_data.get("id")
        game_date = game_data.get("date")
        season_year = game_data.get("season")

        home_team = game_data.get("home_team", {})
        visitor_team = game_data.get("visitor_team", {})

        for team_obj, is_home in [(home_team, True), (visitor_team, False)]:
            team_id = team_obj.get("id")
            team_name = team_obj.get("full_name")

            for player_data in team_obj.get("players", []):
                player = player_data.get("player", {})

                records.append({
                    "game_id": game_id,
                    "player_id": player.get("id"),
                    "player_name": f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(),
                    "team_id": team_id,
                    "team_name": team_name,
                    "is_home": is_home,
                    "game_date": game_date,
                    "season": season_year,
                    "status": status,
                    "min": player_data.get("min"),
                    "pts": player_data.get("pts", 0) or 0,
                    "reb": player_data.get("reb", 0) or 0,
                    "oreb": player_data.get("oreb", 0) or 0,
                    "dreb": player_data.get("dreb", 0) or 0,
                    "ast": player_data.get("ast", 0) or 0,
                    "stl": player_data.get("stl", 0) or 0,
                    "blk": player_data.get("blk", 0) or 0,
                    "turnover": player_data.get("turnover", 0) or 0,
                    "pf": player_data.get("pf", 0) or 0,
                    "fgm": player_data.get("fgm", 0) or 0,
                    "fga": player_data.get("fga", 0) or 0,
                    "fg_pct": player_data.get("fg_pct"),
                    "fg3m": player_data.get("fg3m", 0) or 0,
                    "fg3a": player_data.get("fg3a", 0) or 0,
                    "fg3_pct": player_data.get("fg3_pct"),
                    "ftm": player_data.get("ftm", 0) or 0,
                    "fta": player_data.get("fta", 0) or 0,
                    "ft_pct": player_data.get("ft_pct"),
                })

    elapsed = time.monotonic() - t0
    logger.info(
        f"fetch_live_box_scores | ds={date_str} | players={len(records)}"
        f" | elapsed_sec={elapsed:.2f}"
    )
    return records


def fetch_live_plays(game_id: int) -> list[dict]:
    """
    Fetch play-by-play data for a specific game.

    Available for 2025 season onward. Plays are immutable — once created
    they don't change, so MERGE acts as insert-once.

    Args:
        game_id: BallDontLie game ID

    Returns:
        List of play records
    """
    t0 = time.monotonic()
    logger.info(f"Fetching plays for game_id={game_id}")

    all_plays = []
    cursor = None

    # Paginate through all plays
    while True:
        params = {"game_id": game_id, "per_page": 100}
        if cursor:
            params["cursor"] = cursor

        raw_response = _make_request("/plays", params)
        plays_data = raw_response.get("data", [])

        for play in plays_data:
            # BDL /plays fields: order, type, text, clock, period,
            # period_display, home_score, away_score, team (nested),
            # scoring_play, shooting_play, score_value, coordinate_x/y.
            # No nested player object — only team.
            team = play.get("team", {}) or {}

            # API uses -214748340/-214748365 as sentinel for "no coordinates"
            # (substitutions, free throws, timeouts, etc.). Convert to None.
            raw_x = play.get("coordinate_x")
            raw_y = play.get("coordinate_y")
            coord_x = raw_x if isinstance(raw_x, int) and abs(raw_x) < 1000 else None
            coord_y = raw_y if isinstance(raw_y, int) and abs(raw_y) < 1000 else None

            all_plays.append({
                "game_id": game_id,
                "play_id": play.get("order"),
                "period": play.get("period"),
                "period_display": play.get("period_display"),
                "clock": play.get("clock"),
                "action_type": play.get("type"),
                "description": play.get("text"),
                "team_id": team.get("id"),
                "team_name": team.get("full_name"),
                "scoring_play": play.get("scoring_play", False),
                "shooting_play": play.get("shooting_play", False),
                "score_value": play.get("score_value"),
                "home_score": play.get("home_score", 0) or 0,
                "away_score": play.get("away_score", 0) or 0,
                "coordinate_x": coord_x,
                "coordinate_y": coord_y,
            })

        # Check for next page
        meta = raw_response.get("meta", {})
        cursor = meta.get("next_cursor")
        if not cursor:
            break

    elapsed = time.monotonic() - t0
    logger.info(
        f"fetch_live_plays | game_id={game_id} | plays={len(all_plays)}"
        f" | elapsed_sec={elapsed:.2f}"
    )
    return all_plays
