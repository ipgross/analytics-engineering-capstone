"""
Test script: compare morning vs late-night Odds API snapshots for a date.
Morning snapshot = all games pre-match (10 events).
Late snapshot = only unfinished/postponed games remain (completed games removed).

Usage:  python -m include.capstone.scripts.test_odds_api_fields 2024-01-17
Cost:   2 credits (1 per snapshot)
"""
import sys
from datetime import datetime, timedelta

from include.capstone.api_client import OddsApiClient
from include.capstone.config import SPORT_KEY


def fetch_snapshot(client, date_str, snapshot_time, label):
    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    params = {
        "date": f"{date_str}T{snapshot_time}Z",
        "commenceTimeFrom": f"{date_str}T10:00:00Z",
        "commenceTimeTo": f"{next_day}T06:00:00Z",
    }
    endpoint = f"historical/sports/{SPORT_KEY}/events"
    response = client._make_request(endpoint, params)
    events = response.get("data", [])

    print(f"\n=== {label}: {date_str}T{snapshot_time}Z ({len(events)} events) ===")
    for event in events:
        home = event.get("home_team", "?")
        away = event.get("away_team", "?")
        commence = event.get("commence_time", "?")
        print(f"  {away:30s} @ {home:30s} | {commence}")
    return events


def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else "2024-01-17"
    client = OddsApiClient()

    # Morning: all games pre-match
    morning = fetch_snapshot(client, date_str, "12:00:00", "MORNING (7am ET)")

    # Late night: completed games removed, postponed games remain
    late = fetch_snapshot(client, date_str, "23:59:59", "LATE NIGHT (7pm ET)")

    # Diff: events in morning but not in late = completed games
    # Events in late = still pre-match (postponed or not yet started)
    morning_ids = {e["id"] for e in morning}
    late_ids = {e["id"] for e in late}

    still_there = morning_ids & late_ids
    removed = morning_ids - late_ids

    print("\n=== DIFF ===")
    print(f"Morning events: {len(morning_ids)}")
    print(f"Late events:    {len(late_ids)}")
    print(f"Removed (completed): {len(removed)}")
    print(f"Still there (pre-match/postponed): {len(still_there)}")

    if still_there:
        print("\nEvents still pre-match at late snapshot (likely postponed):")
        for event in morning:
            if event["id"] in still_there:
                print(f"  {event.get('away_team')} @ {event.get('home_team')} | {event.get('commence_time')}")

    print(f"\nCredits remaining: {client.requests_remaining}")


if __name__ == "__main__":
    main()
