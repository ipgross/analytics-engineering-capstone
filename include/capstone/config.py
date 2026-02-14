"""
Configuration for NBA Analytics pipeline.
Credentials pattern: hardcoded for bootcamp + Airflow Variables for shared infra.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ===========================================
# STUDENT CONFIG (hardcoded for bootcamp)
# ===========================================
STUDENT_SCHEMA = "ipgross"
SNOWFLAKE_USER = "ipgross"
SNOWFLAKE_PASSWORD = "YOUR_SNOWFLAKE_PASSWORD"
ODDS_API_KEY = "YOUR_ODDS_API_KEY"
BALLDONTLIE_API_KEY = "YOUR_BALLDONTLIE_API_KEY"

# ===========================================
# SHARED INFRASTRUCTURE (don't change)
# ===========================================
SNOWFLAKE_ACCOUNT = "aab46027.us-west-2"
SNOWFLAKE_WAREHOUSE = "COMPUTE_WH"
SNOWFLAKE_DATABASE = "DATAEXPERT_STUDENT"
SNOWFLAKE_ROLE = "ALL_USERS_ROLE"

# ===========================================
# S3 CONFIGURATION
# ===========================================
S3_ARCHIVE_PREFIX = "ipgross/archive"
S3_BULK_PREFIX = "ipgross/bulk"

# ===========================================
# SNOWFLAKE TABLE NAMES (Cold Path)
# ===========================================
HIST_EVENTS_TABLE = f"{STUDENT_SCHEMA}.hist_nba_events"
HIST_ODDS_TABLE = f"{STUDENT_SCHEMA}.hist_nba_odds_open"
HIST_GAMES_TABLE = f"{STUDENT_SCHEMA}.hist_nba_games"
HIST_BOX_SCORES_TABLE = f"{STUDENT_SCHEMA}.hist_nba_player_box_scores"
HIST_TEAMS_TABLE = f"{STUDENT_SCHEMA}.hist_nba_teams"

# Staging tables (TRANSIENT — no fail-safe, cleared per-date before each load)
STG_EVENTS_TABLE = f"{STUDENT_SCHEMA}.stg_nba_events"
STG_ODDS_TABLE = f"{STUDENT_SCHEMA}.stg_nba_odds_open"
STG_GAMES_TABLE = f"{STUDENT_SCHEMA}.stg_nba_games"
STG_BOX_SCORES_TABLE = f"{STUDENT_SCHEMA}.stg_nba_player_box_scores"

# Ops metadata
OPS_TABLE = f"{STUDENT_SCHEMA}.ops_ingestion_runs"

# ===========================================
# SNOWFLAKE TABLE NAMES (Hot Path - Live)
# ===========================================
LIVE_SCOREBOARD_TABLE = f"{STUDENT_SCHEMA}.live_nba_scoreboard"
LIVE_BOX_SCORES_TABLE = f"{STUDENT_SCHEMA}.live_nba_player_box_scores"
LIVE_ODDS_TABLE = f"{STUDENT_SCHEMA}.live_nba_odds"
LIVE_PLAYS_TABLE = f"{STUDENT_SCHEMA}.live_nba_plays"
ARCHIVE_ODDS_TABLE = f"{STUDENT_SCHEMA}.archive_nba_odds_snapshots"

# ===========================================
# API CONFIGURATION
# ===========================================
ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"
SPORT_KEY = "basketball_nba"

# Odds API parameters
ODDS_MARKETS = ["h2h", "spreads", "totals"]
ODDS_REGIONS = ["us"]
ODDS_FORMAT = "american"

# BallDontLie API configuration
BALLDONTLIE_BASE_URL = "https://api.balldontlie.io/v1"

# ===========================================
# TEAM NAME NORMALIZATION (Odds API → BallDontLie)
# ===========================================
# The Odds API and BallDontLie use different names for some teams.
# We normalize to BDL names at ingestion so all warehouse joins work.
TEAM_NAME_MAP = {
    "Los Angeles Clippers": "LA Clippers",
}


def normalize_team_name(name: str) -> str:
    """Map Odds API team name to BallDontLie canonical name."""
    return TEAM_NAME_MAP.get(name, name)


# ===========================================
# NBA SEASON DATES
# ===========================================
SEASON_DATE_RANGES = {
    "2023-24": ("2023-10-24", "2024-06-17"),
    "2024-25": ("2024-10-22", "2025-06-22"),
    "2025-26": ("2025-10-21", "2026-06-21"),
}


def get_season_for_date(date_str: str) -> str:
    """
    Get the NBA season name for a date (e.g., '2023-24').

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        Season string like '2023-24' or 'unknown'
    """
    for season, (start, end) in SEASON_DATE_RANGES.items():
        if start <= date_str <= end:
            return season
    return "unknown"


def is_nba_season(date_str: str) -> bool:
    """
    Check if a date falls within an NBA season.

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        True if within a season, False otherwise
    """
    for start, end in SEASON_DATE_RANGES.values():
        if start <= date_str <= end:
            return True
    return False


def is_game_window() -> bool:
    """
    Check if current time is within NBA game hours (11am-2am ET).

    NBA games tip off as early as 12pm ET (matinees) and as late as 10:30pm ET.
    West coast games can end around 1:30am ET. 11am-2am covers all cases.

    Returns:
        True if within game window, False otherwise
    """
    now_et = datetime.now(ZoneInfo("America/New_York"))
    return now_et.hour >= 11 or now_et.hour < 2


def get_live_game_dates() -> list[str]:
    """
    Get date strings to query for live games.

    Always returns today. Also returns yesterday if before 5am ET,
    since west coast late games from yesterday may still be in progress.

    Returns:
        List of date strings in YYYY-MM-DD format (1 or 2 dates)
    """
    now_et = datetime.now(ZoneInfo("America/New_York"))
    today = now_et.strftime("%Y-%m-%d")
    yesterday = (now_et - timedelta(days=1)).strftime("%Y-%m-%d")
    return [yesterday, today] if now_et.hour < 5 else [today]
