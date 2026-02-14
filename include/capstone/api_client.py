"""
The Odds API client for fetching NBA events.
Simple, focused on events endpoint only.
"""
import time
import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import requests

from include.capstone.config import (
    ODDS_API_BASE_URL,
    ODDS_API_KEY,
    SPORT_KEY,
    ODDS_MARKETS,
    ODDS_REGIONS,
    ODDS_FORMAT,
    get_season_for_date,
    normalize_team_name,
)

logger = logging.getLogger(__name__)

# Timezone for NBA (Eastern)
EASTERN = ZoneInfo("America/New_York")

# Rate limiting and retry config
RATE_LIMIT_RPS = 1.0
MAX_RETRIES = 3
RETRY_BACKOFF = [5, 30, 120]


class RateLimiter:
    """Simple rate limiter to control API request frequency."""

    def __init__(self, requests_per_second: float = RATE_LIMIT_RPS):
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0

    def wait(self) -> None:
        """Wait if necessary to respect rate limit."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()


class OddsApiClient:
    """Client for The Odds API with rate limiting and retries."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ODDS_API_KEY
        self.base_url = ODDS_API_BASE_URL
        self.rate_limiter = RateLimiter()
        self.session = requests.Session()
        self.requests_remaining: Optional[str] = None
        self.requests_used: Optional[str] = None

    def _make_request(self, endpoint: str, params: dict) -> dict:
        """Make API request with rate limiting and retries."""
        url = f"{self.base_url}/{endpoint}"
        params["apiKey"] = self.api_key

        for attempt in range(MAX_RETRIES):
            self.rate_limiter.wait()

            try:
                response = self.session.get(url, params=params, timeout=30)

                # Update usage tracking from headers
                self.requests_remaining = response.headers.get("x-requests-remaining")
                self.requests_used = response.headers.get("x-requests-used")

                if response.status_code == 200:
                    return response.json()

                if response.status_code == 429:
                    wait_time = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                    logger.warning(f"Rate limited (429). Waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue

                if response.status_code >= 500:
                    wait_time = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                    logger.warning(f"Server error ({response.status_code}). Waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue

                logger.error(f"API error {response.status_code}: {response.text}")
                response.raise_for_status()

            except requests.exceptions.Timeout:
                wait_time = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                logger.warning(f"Timeout. Waiting {wait_time}s before retry")
                time.sleep(wait_time)

            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")
                if attempt == MAX_RETRIES - 1:
                    raise

        raise Exception(f"Failed after {MAX_RETRIES} attempts")

    def get_usage(self) -> dict:
        """Return current API usage stats from last request."""
        return {
            "requests_remaining": self.requests_remaining,
            "requests_used": self.requests_used,
        }


def fetch_events_for_date(date_str: str) -> list[dict]:
    """
    Fetch NBA events for a specific date.

    Auto-selects endpoint:
    - Past dates: Historical events endpoint (1 credit, FREE if no games)
    - Today (after 10am EST): Scores endpoint (2 credits) - catches matinee games
    - Today (before 10am EST) or future: Regular events endpoint (FREE)

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        List of event dictionaries with normalized fields
    """
    t0 = time.monotonic()
    logger.info(f"Fetching events for {date_str}")

    client = OddsApiClient()

    # Get today in Eastern time
    today_et = datetime.now(EASTERN).strftime("%Y-%m-%d")
    now_et = datetime.now(EASTERN)

    # Compute UTC window that covers an entire Eastern date.
    # NBA games tip off between noon ET and ~10:30 PM ET.
    # noon ET = 17:00 UTC same day, 10:30 PM ET = 03:30 UTC next day.
    # We use a generous window: 10:00 UTC (5am ET) to next-day 06:00 UTC (1am ET).
    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    commence_from = f"{date_str}T10:00:00Z"
    commence_to = f"{next_day}T06:00:00Z"

    if date_str < today_et:
        # Historical endpoint for past dates
        # Morning snapshot (T12:00:00Z = 7am ET): all games still pre-match.
        # Postponed detection is handled retroactively by the reconcile DAG
        # (compares actual BDL games against events). Cost: 1 credit.
        logger.info(f"Using HISTORICAL endpoint for {date_str}")
        endpoint = f"historical/sports/{SPORT_KEY}/events"
        params = {
            "date": f"{date_str}T12:00:00Z",
            "commenceTimeFrom": commence_from,
            "commenceTimeTo": commence_to,
        }
        response = client._make_request(endpoint, params)
        raw_events = response.get("data", [])

    elif date_str == today_et and now_et.hour >= 10:
        # Today after 10am EST: Use scores endpoint (catches matinee games)
        # The regular events endpoint only shows UPCOMING games, missing any
        # games that have already started or completed (like matinees).
        # Scores endpoint returns all games: completed, live, and upcoming.
        logger.info(f"Using SCORES endpoint for TODAY ({date_str}) - after 10am EST")
        params = {"daysFrom": 1}
        endpoint = f"sports/{SPORT_KEY}/scores"
        raw_events = client._make_request(endpoint, params)
        # raw_events is a list directly (not wrapped in "data")

    else:
        # Today before 10am or future: Regular endpoint (FREE)
        logger.info(f"Using REGULAR endpoint for {date_str}")
        params = {
            "commenceTimeFrom": commence_from,
            "commenceTimeTo": commence_to,
        }
        endpoint = f"sports/{SPORT_KEY}/events"
        raw_events = client._make_request(endpoint, params)

    # Normalize events and filter to target date (Eastern time)
    events = []
    season = get_season_for_date(date_str)

    for event in raw_events:
        commence_time = event.get("commence_time", "")
        if not commence_time:
            continue

        # Convert UTC to Eastern for date comparison
        utc_dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
        et_dt = utc_dt.astimezone(EASTERN)
        game_date_et = et_dt.strftime("%Y-%m-%d")

        # Only include events that start on the target date (in Eastern time)
        if game_date_et == date_str:
            events.append({
                "event_id": event["id"],
                "sport_key": event.get("sport_key", SPORT_KEY),
                "sport_title": event.get("sport_title", "NBA"),
                "commence_time_utc": commence_time,
                "commence_time_et": et_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "home_team": normalize_team_name(event.get("home_team", "")),
                "away_team": normalize_team_name(event.get("away_team", "")),
                "season": season,
            })

    usage = client.get_usage()
    elapsed = time.monotonic() - t0
    logger.info(
        f"fetch_events | ds={date_str} | events={len(events)}"
        f" | elapsed_sec={elapsed:.2f} | api_remaining={usage.get('requests_remaining')}"
    )

    return events


def fetch_odds_for_date(date_str: str) -> tuple[list[dict], dict]:
    """
    Fetch NBA odds for a specific date.

    Auto-selects endpoint:
    - Past dates: Historical odds endpoint (30 credits for 3 markets, 1 region)
    - Today/future: Regular odds endpoint (3 credits for 3 markets, 1 region)

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        Tuple of (flattened_records, raw_response)
        - flattened_records: List of dicts ready for Snowflake (one row per outcome)
        - raw_response: Original API response for S3 archiving
    """
    t0 = time.monotonic()
    logger.info(f"Fetching odds for {date_str}")

    client = OddsApiClient()

    # Common params for both endpoints
    base_params = {
        "regions": ",".join(ODDS_REGIONS),
        "markets": ",".join(ODDS_MARKETS),
        "oddsFormat": ODDS_FORMAT,
    }

    # Get today in Eastern time
    today_et = datetime.now(EASTERN).strftime("%Y-%m-%d")

    # UTC window covering the full Eastern date (same logic as events)
    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    commence_from = f"{date_str}T10:00:00Z"
    commence_to = f"{next_day}T06:00:00Z"

    if date_str < today_et:
        # Historical odds endpoint (30 credits)
        # Morning snapshot captures opening lines while all games are pre-match
        logger.info(f"Using HISTORICAL odds endpoint for {date_str}")
        params = {
            **base_params,
            "date": f"{date_str}T12:00:00Z",
            "commenceTimeFrom": commence_from,
            "commenceTimeTo": commence_to,
        }
        endpoint = f"historical/sports/{SPORT_KEY}/odds"
        response = client._make_request(endpoint, params)
        raw_events = response.get("data", [])
        raw_response = response
    else:
        # Regular odds endpoint (3 credits)
        logger.info(f"Using REGULAR odds endpoint for {date_str}")
        params = {
            **base_params,
            "commenceTimeFrom": commence_from,
            "commenceTimeTo": commence_to,
        }
        endpoint = f"sports/{SPORT_KEY}/odds"
        raw_events = client._make_request(endpoint, params)
        raw_response = {"data": raw_events, "timestamp": datetime.utcnow().isoformat() + "Z"}

    # Flatten and filter by Eastern date
    records = []
    season = get_season_for_date(date_str)
    bookmaker_keys = set()

    for event in raw_events:
        commence_time = event.get("commence_time", "")
        if not commence_time:
            continue

        # Convert UTC to Eastern for date comparison
        utc_dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
        et_dt = utc_dt.astimezone(EASTERN)
        game_date_et = et_dt.strftime("%Y-%m-%d")

        # Only include events that start on the target date (in Eastern time)
        if game_date_et != date_str:
            continue

        event_id = event.get("id")
        home_team = normalize_team_name(event.get("home_team", ""))
        away_team = normalize_team_name(event.get("away_team", ""))
        commence_time_et = et_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Flatten bookmakers > markets > outcomes
        for bookmaker in event.get("bookmakers", []):
            bookmaker_key = bookmaker.get("key")
            bookmaker_title = bookmaker.get("title")
            bookmaker_last_update = bookmaker.get("last_update")
            bookmaker_keys.add(bookmaker_key)

            for market in bookmaker.get("markets", []):
                market_key = market.get("key")

                for outcome in market.get("outcomes", []):
                    records.append({
                        "event_id": event_id,
                        "season": season,
                        "home_team": home_team,
                        "away_team": away_team,
                        "commence_time_utc": commence_time,
                        "commence_time_et": commence_time_et,
                        "bookmaker_key": bookmaker_key,
                        "bookmaker_title": bookmaker_title,
                        "bookmaker_last_update": bookmaker_last_update,
                        "market_key": market_key,
                        "outcome_name": normalize_team_name(outcome.get("name", "")),
                        "outcome_price": outcome.get("price"),
                        "outcome_point": outcome.get("point"),  # None for h2h
                    })

    usage = client.get_usage()
    elapsed = time.monotonic() - t0
    logger.info(
        f"fetch_odds | ds={date_str} | records={len(records)}"
        f" | bookmakers={len(bookmaker_keys)}"
        f" | elapsed_sec={elapsed:.2f} | api_remaining={usage.get('requests_remaining')}"
    )

    return records, raw_response


# ===========================================
# HOT PATH — Live Odds Fetch
# ===========================================

def fetch_live_odds() -> list[dict]:
    """
    Fetch current NBA odds from The Odds API.

    Always uses the regular /odds endpoint (not historical).
    Derives game_date from commence_time_utc (ET conversion).
    No date parameter — fetches whatever is currently available.

    Cost: 3 credits per call (3 markets x 1 region).

    Returns:
        List of flattened odds records ready for MERGE
    """
    t0 = time.monotonic()
    logger.info("Fetching live odds")

    client = OddsApiClient()

    params = {
        "regions": ",".join(ODDS_REGIONS),
        "markets": ",".join(ODDS_MARKETS),
        "oddsFormat": ODDS_FORMAT,
    }

    endpoint = f"sports/{SPORT_KEY}/odds"
    raw_events = client._make_request(endpoint, params)

    records = []
    for event in raw_events:
        commence_time = event.get("commence_time", "")
        if not commence_time:
            continue

        # Derive game_date from commence_time (ET conversion)
        utc_dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
        et_dt = utc_dt.astimezone(EASTERN)
        game_date = et_dt.strftime("%Y-%m-%d")

        event_id = event.get("id")
        home_team = normalize_team_name(event.get("home_team", ""))
        away_team = normalize_team_name(event.get("away_team", ""))

        for bookmaker in event.get("bookmakers", []):
            bookmaker_key = bookmaker.get("key")
            bookmaker_title = bookmaker.get("title")
            bookmaker_last_update = bookmaker.get("last_update")

            for market in bookmaker.get("markets", []):
                market_key = market.get("key")

                for outcome in market.get("outcomes", []):
                    records.append({
                        "event_id": event_id,
                        "game_date": game_date,
                        "home_team": home_team,
                        "away_team": away_team,
                        "commence_time_utc": commence_time,
                        "bookmaker_key": bookmaker_key,
                        "bookmaker_title": bookmaker_title,
                        "bookmaker_last_update": bookmaker_last_update,
                        "market_key": market_key,
                        "outcome_name": normalize_team_name(outcome.get("name", "")),
                        "outcome_price": outcome.get("price"),
                        "outcome_point": outcome.get("point"),
                    })

    usage = client.get_usage()
    elapsed = time.monotonic() - t0
    logger.info(
        f"fetch_live_odds | records={len(records)}"
        f" | elapsed_sec={elapsed:.2f} | api_remaining={usage.get('requests_remaining')}"
    )
    return records
