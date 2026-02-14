"""
Test script: compare Odds API events vs BDL games for a date.
Shows which event has no matching Final game (= postponed).

Usage:  python -m include.capstone.scripts.test_bdl_games 2024-01-17
"""
import sys

from include.capstone.balldontlie_client import _make_request


def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else "2024-01-17"

    params = {"dates[]": date_str, "per_page": 100}
    raw = _make_request("/games", params)
    games = raw.get("data", [])

    print(f"\n=== BDL games for {date_str} ===")
    print(f"Total games returned: {len(games)}\n")

    for g in games:
        home = g.get("home_team", {}).get("full_name", "?")
        away = g.get("visitor_team", {}).get("full_name", "?")
        status = g.get("status")
        postponed = g.get("postponed")
        score = f"{g.get('home_team_score', '?')}-{g.get('visitor_team_score', '?')}"
        print(f"  {away:30s} @ {home:30s} | status={status:10s} | postponed={postponed} | score={score}")


if __name__ == "__main__":
    main()
