"""
Test script: Inspect raw coordinate_x/coordinate_y from BallDontLie /plays.

Diagnose why Snowflake shows -214748340 / -214748365 for many rows.
Possible causes:
  1. API returns those exact values (sentinel for "no coordinates")
  2. API returns None/null and Snowflake VALUES clause mishandles it
  3. API returns a different type (string, float) that gets cast badly

Usage:
    python -m include.capstone.scripts.test_coordinates
"""
import json
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from include.capstone.config import BALLDONTLIE_API_KEY, BALLDONTLIE_BASE_URL


def fetch_raw_plays(game_id: int, max_plays: int = 50):
    """Fetch raw plays and return the unprocessed JSON data."""
    resp = requests.get(
        f"{BALLDONTLIE_BASE_URL}/plays",
        headers={"Authorization": BALLDONTLIE_API_KEY},
        params={"game_id": game_id, "per_page": max_plays},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def find_game_with_plays():
    """Find a recent Final or in-progress game to test with."""
    now_et = datetime.now(ZoneInfo("America/New_York"))

    # Try today and yesterday
    for offset in range(0, 3):
        date = (now_et - timedelta(days=offset)).strftime("%Y-%m-%d")
        print(f"Checking {date} for games...")

        resp = requests.get(
            f"{BALLDONTLIE_BASE_URL}/games",
            headers={"Authorization": BALLDONTLIE_API_KEY},
            params={"dates[]": date, "per_page": 100},
            timeout=30,
        )
        resp.raise_for_status()
        games = resp.json().get("data", [])

        for g in games:
            status = g.get("status", "")
            if status == "Final" or "Qtr" in status or "Half" in status:
                home = g.get("home_team", {}).get("full_name", "?")
                away = g.get("visitor_team", {}).get("full_name", "?")
                print(f"  Found: game_id={g['id']}  status={status}  {away} @ {home}")
                return g["id"]

    return None


def analyze_coordinates(game_id: int):
    """Fetch plays and analyze coordinate values in detail."""
    print(f"\n{'='*70}")
    print(f"Analyzing coordinates for game_id={game_id}")
    print(f"{'='*70}")

    raw = fetch_raw_plays(game_id, max_plays=100)
    plays = raw.get("data", [])
    print(f"Fetched {len(plays)} plays\n")

    if not plays:
        print("No plays returned!")
        return

    # Print first 3 raw plays in full to see structure
    print("--- First 3 raw plays (full JSON) ---")
    for i, play in enumerate(plays[:3]):
        print(f"\nPlay {i+1}:")
        print(json.dumps(play, indent=2))

    # Now analyze ALL plays for coordinate patterns
    print(f"\n{'='*70}")
    print("COORDINATE ANALYSIS")
    print(f"{'='*70}\n")

    coord_stats = {
        "null_null": 0,
        "has_coords": 0,
        "zero_zero": 0,
        "negative_large": 0,
        "other": 0,
    }

    print(f"{'#':>4} {'type':<20} {'scoring':>7} {'shooting':>8} "
          f"{'coord_x':>12} {'coord_y':>12} {'x_type':<10} {'y_type':<10}")
    print("-" * 100)

    for i, play in enumerate(plays):
        cx = play.get("coordinate_x")
        cy = play.get("coordinate_y")
        cx_type = type(cx).__name__
        cy_type = type(cy).__name__

        # Categorize
        if cx is None and cy is None:
            coord_stats["null_null"] += 1
        elif isinstance(cx, (int, float)) and isinstance(cy, (int, float)):
            if cx == 0 and cy == 0:
                coord_stats["zero_zero"] += 1
            elif abs(cx) > 1000 or abs(cy) > 1000:
                coord_stats["negative_large"] += 1
            else:
                coord_stats["has_coords"] += 1
        else:
            coord_stats["other"] += 1

        # Print each play's coordinate info
        action = str(play.get("type", ""))[:20]
        scoring = play.get("scoring_play")
        shooting = play.get("shooting_play")

        print(f"{i+1:>4} {action:<20} {str(scoring):>7} {str(shooting):>8} "
              f"{str(cx):>12} {str(cy):>12} {cx_type:<10} {cy_type:<10}")

    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"  Total plays:          {len(plays)}")
    print(f"  Both null:            {coord_stats['null_null']}")
    print(f"  Valid coordinates:    {coord_stats['has_coords']}")
    print(f"  Zero/zero:            {coord_stats['zero_zero']}")
    print(f"  Large/negative:       {coord_stats['negative_large']}")
    print(f"  Other (unexpected):   {coord_stats['other']}")

    # Show unique coordinate values
    unique_x = set()
    unique_y = set()
    for play in plays:
        cx = play.get("coordinate_x")
        cy = play.get("coordinate_y")
        if cx is not None:
            unique_x.add((cx, type(cx).__name__))
        if cy is not None:
            unique_y.add((cy, type(cy).__name__))

    print(f"\n  Unique non-null X values ({len(unique_x)}):")
    for val, typ in sorted(unique_x):
        print(f"    {val} ({typ})")

    print(f"\n  Unique non-null Y values ({len(unique_y)}):")
    for val, typ in sorted(unique_y):
        print(f"    {val} ({typ})")

    # Test what _escape_sql would produce
    print(f"\n{'='*70}")
    print("_escape_sql OUTPUT TEST")
    print(f"{'='*70}")
    print("Testing what our _escape_sql() would produce for sample values:\n")

    from include.capstone.database import _escape_sql

    sample_plays = plays[:10]
    for i, play in enumerate(sample_plays):
        cx = play.get("coordinate_x")
        cy = play.get("coordinate_y")
        esc_x = _escape_sql(cx)
        esc_y = _escape_sql(cy)
        print(f"  Play {i+1}: raw=({cx}, {cy})  escaped=({esc_x}, {esc_y})")


if __name__ == "__main__":
    game_id = find_game_with_plays()
    if game_id:
        analyze_coordinates(game_id)
    else:
        print("\nNo recent games found. Trying hardcoded game_id...")
        # Try a known recent game — update this if needed
        print("Edit this script with a known game_id and run again.")
