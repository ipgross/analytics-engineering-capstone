"""
Test script: Verify BallDontLie /plays endpoint response structure.

Usage:
    python -m include.capstone.scripts.test_plays_endpoint

This fetches a single game's plays to inspect the actual field names
returned by the API, since the docs show different names than what
we assumed in fetch_live_plays().
"""
import json
import requests
from include.capstone.config import BALLDONTLIE_API_KEY, BALLDONTLIE_BASE_URL


def test_games_today():
    """Fetch today's games to find a game_id to test plays with."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    print(f"Fetching games for {today}...")

    resp = requests.get(
        f"{BALLDONTLIE_BASE_URL}/games",
        headers={"Authorization": BALLDONTLIE_API_KEY},
        params={"dates[]": today, "per_page": 100},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    games = data.get("data", [])

    print(f"Found {len(games)} games:")
    for g in games:
        home = g.get("home_team", {}).get("full_name", "?")
        away = g.get("visitor_team", {}).get("full_name", "?")
        print(f"  game_id={g.get('id')}  status={g.get('status')}  {away} @ {home}  "
              f"score={g.get('visitor_team_score')}-{g.get('home_team_score')}")

    return games


def test_plays(game_id: int):
    """Fetch plays for a game and print the raw response structure."""
    print(f"\nFetching plays for game_id={game_id}...")

    resp = requests.get(
        f"{BALLDONTLIE_BASE_URL}/plays",
        headers={"Authorization": BALLDONTLIE_API_KEY},
        params={"game_id": game_id, "per_page": 5},  # Just 5 to inspect structure
        timeout=30,
    )

    print(f"Status: {resp.status_code}")

    if resp.status_code != 200:
        print(f"Error: {resp.text}")
        return

    data = resp.json()

    # Print meta
    meta = data.get("meta", {})
    print(f"Meta: {json.dumps(meta, indent=2)}")

    # Print first play with ALL field names
    plays = data.get("data", [])
    print(f"\nTotal plays returned: {len(plays)}")

    if plays:
        print("\n--- First play (all fields) ---")
        print(json.dumps(plays[0], indent=2))

        print("\n--- Field names in play object ---")
        for key in plays[0].keys():
            val = plays[0][key]
            val_type = type(val).__name__
            preview = str(val)[:80] if val is not None else "None"
            print(f"  {key}: ({val_type}) {preview}")

        # Check for nested objects
        if plays[0].get("team"):
            print("\n--- Team object fields ---")
            for key in plays[0]["team"].keys():
                print(f"  team.{key}: {plays[0]['team'][key]}")

        if plays[0].get("player"):
            print("\n--- Player object fields ---")
            for key in plays[0]["player"].keys():
                print(f"  player.{key}: {plays[0]['player'][key]}")
        else:
            print("\n--- No 'player' field in play object ---")


if __name__ == "__main__":
    games = test_games_today()

    # Try to find an in-progress or final game to test plays
    test_game = None
    for g in games:
        status = g.get("status", "")
        if status == "Final" or ("Qtr" in status or "Half" in status or "OT" in status):
            test_game = g
            break

    if not test_game:
        # Try any game
        if games:
            test_game = games[0]

    if test_game:
        test_plays(test_game["id"])
    else:
        print("\nNo games found today. Try with a known game_id:")
        print("  Edit this script and call test_plays(GAME_ID) directly")
