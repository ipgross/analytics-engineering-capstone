"""
Diagnostic script: Test The Odds API for upcoming NBA events and odds.

Hits the API directly (no DAG infrastructure) to diagnose why
nba_ingest_upcoming returns 0 results for future dates.

Run from project root:
    python -m include.capstone.scripts.test_upcoming_api

Cost: ~6 API credits (events are FREE, odds = 3 credits × 2 calls)
"""
import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# ── Config ────────────────────────────────────────────────────────────────────
API_KEY = "98314299d959c7b31e7d6a58de6a0ccc"
BASE_URL = "https://api.the-odds-api.com/v4"
SPORT = "basketball_nba"
EASTERN = ZoneInfo("America/New_York")

# Target date: 2/18 (known NBA game post All-Star break)
TARGET_DATE = "2026-02-18"
TARGET_NEXT = "2026-02-19"


def _print_header(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def _print_credits(resp: requests.Response):
    remaining = resp.headers.get("x-requests-remaining", "?")
    used = resp.headers.get("x-requests-used", "?")
    print(f"  Credits — remaining: {remaining}, used: {used}")


def test_1_events_unfiltered():
    """Hit /events with NO date filter — see ALL upcoming NBA events."""
    _print_header("TEST 1: Events (unfiltered) — all upcoming NBA games")

    url = f"{BASE_URL}/sports/{SPORT}/events"
    params = {"apiKey": API_KEY}

    print(f"  GET {url}")
    print("  Params: (none besides apiKey)")

    resp = requests.get(url, params=params, timeout=30)
    print(f"  HTTP {resp.status_code}")
    _print_credits(resp)

    if resp.status_code != 200:
        print(f"  ERROR: {resp.text[:500]}")
        return

    data = resp.json()
    print(f"  Results: {len(data)} events")

    if not data:
        print("  >> NO EVENTS — API has nothing listed for NBA right now")
        return

    # Print all events grouped by date
    events_by_date = {}
    for evt in data:
        ct = evt.get("commence_time", "")
        if ct:
            utc_dt = datetime.fromisoformat(ct.replace("Z", "+00:00"))
            et_dt = utc_dt.astimezone(EASTERN)
            date_et = et_dt.strftime("%Y-%m-%d")
            tip_et = et_dt.strftime("%I:%M %p ET")
        else:
            date_et = "unknown"
            tip_et = "?"

        events_by_date.setdefault(date_et, []).append({
            "id": evt.get("id", "?")[:16],
            "home": evt.get("home_team", "?"),
            "away": evt.get("away_team", "?"),
            "tip": tip_et,
        })

    for date in sorted(events_by_date.keys()):
        games = events_by_date[date]
        print(f"\n  {date} ({len(games)} games):")
        for g in games:
            print(f"    {g['away']} @ {g['home']} — {g['tip']}  [{g['id']}...]")

    # Show raw first event
    print("\n  Raw first event:")
    print(f"  {json.dumps(data[0], indent=2)[:600]}")


def test_2_events_filtered():
    """Hit /events with commenceTime filter for TARGET_DATE — mirrors fetch_events_for_date()."""
    _print_header(f"TEST 2: Events (filtered for {TARGET_DATE}) — mirrors DAG logic")

    url = f"{BASE_URL}/sports/{SPORT}/events"
    params = {
        "apiKey": API_KEY,
        "commenceTimeFrom": f"{TARGET_DATE}T10:00:00Z",
        "commenceTimeTo": f"{TARGET_NEXT}T06:00:00Z",
    }

    print(f"  GET {url}")
    print(f"  Params: commenceTimeFrom={params['commenceTimeFrom']}, commenceTimeTo={params['commenceTimeTo']}")

    resp = requests.get(url, params=params, timeout=30)
    print(f"  HTTP {resp.status_code}")
    _print_credits(resp)

    if resp.status_code != 200:
        print(f"  ERROR: {resp.text[:500]}")
        return

    data = resp.json()
    print(f"  Results: {len(data)} events")

    if not data:
        print(f"  >> NO EVENTS for {TARGET_DATE} with this filter")
        print(f"     Compare with Test 1 — if Test 1 has {TARGET_DATE} games but this doesn't,")
        print("     the commenceTime filter is the problem.")
        return

    for evt in data:
        ct = evt.get("commence_time", "")
        print(f"    {evt.get('away_team')} @ {evt.get('home_team')} — {ct}")


def test_3_odds_unfiltered():
    """Hit /odds with NO date filter — see which games have odds posted."""
    _print_header("TEST 3: Odds (unfiltered) — all upcoming games with odds")

    url = f"{BASE_URL}/sports/{SPORT}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american",
    }

    print(f"  GET {url}")
    print("  Params: regions=us, markets=h2h,spreads,totals")
    print("  Cost: 3 credits")

    resp = requests.get(url, params=params, timeout=30)
    print(f"  HTTP {resp.status_code}")
    _print_credits(resp)

    if resp.status_code != 200:
        print(f"  ERROR: {resp.text[:500]}")
        return

    data = resp.json()
    print(f"  Results: {len(data)} events with odds")

    if not data:
        print("  >> NO ODDS — bookmakers haven't posted lines for any upcoming NBA games")
        return

    # Print each event with bookmaker count
    for evt in data:
        ct = evt.get("commence_time", "")
        if ct:
            utc_dt = datetime.fromisoformat(ct.replace("Z", "+00:00"))
            et_dt = utc_dt.astimezone(EASTERN)
            date_et = et_dt.strftime("%Y-%m-%d")
            tip_et = et_dt.strftime("%I:%M %p ET")
        else:
            date_et = "?"
            tip_et = "?"

        bookmakers = evt.get("bookmakers", [])
        markets_found = set()
        for bk in bookmakers:
            for mkt in bk.get("markets", []):
                markets_found.add(mkt.get("key"))

        print(
            f"    {date_et} | {evt.get('away_team')} @ {evt.get('home_team')}"
            f" — {tip_et} | {len(bookmakers)} books | markets: {sorted(markets_found)}"
        )

    # Show raw first event (truncated)
    print("\n  Raw first event (truncated):")
    first = data[0].copy()
    if first.get("bookmakers"):
        first["bookmakers"] = [first["bookmakers"][0]]  # only first bookmaker
    print(f"  {json.dumps(first, indent=2)[:800]}")


def test_4_odds_filtered():
    """Hit /odds with commenceTime filter for TARGET_DATE — mirrors fetch_odds_for_date()."""
    _print_header(f"TEST 4: Odds (filtered for {TARGET_DATE}) — mirrors DAG logic")

    url = f"{BASE_URL}/sports/{SPORT}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american",
        "commenceTimeFrom": f"{TARGET_DATE}T10:00:00Z",
        "commenceTimeTo": f"{TARGET_NEXT}T06:00:00Z",
    }

    print(f"  GET {url}")
    print(f"  Params: commenceTimeFrom={params['commenceTimeFrom']}, commenceTimeTo={params['commenceTimeTo']}")
    print("  Cost: 3 credits")

    resp = requests.get(url, params=params, timeout=30)
    print(f"  HTTP {resp.status_code}")
    _print_credits(resp)

    if resp.status_code != 200:
        print(f"  ERROR: {resp.text[:500]}")
        return

    data = resp.json()
    print(f"  Results: {len(data)} events with odds")

    if not data:
        print(f"  >> NO ODDS for {TARGET_DATE}")
        print("     If Test 3 has odds for this date but this doesn't, the filter is wrong.")
        print("     If Test 3 also has no odds for this date, bookmakers haven't posted yet.")
        return

    for evt in data:
        bookmakers = evt.get("bookmakers", [])
        print(
            f"    {evt.get('away_team')} @ {evt.get('home_team')}"
            f" | {len(bookmakers)} bookmakers"
        )


if __name__ == "__main__":
    today = datetime.now(EASTERN).strftime("%Y-%m-%d")
    print(f"Running API diagnostics — today is {today} ET")
    print(f"Target date: {TARGET_DATE}")
    print(f"API base: {BASE_URL}/sports/{SPORT}")

    test_1_events_unfiltered()
    test_2_events_filtered()
    test_3_odds_unfiltered()
    test_4_odds_filtered()

    print(f"\n{'='*70}")
    print("  DONE — check results above to diagnose the issue")
    print(f"{'='*70}")
