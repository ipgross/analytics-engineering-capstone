# CLAUDE.md — NBA Betting Analytics dbt Project

## Project Overview

dbt transformation layer for an NBA spread-beating analytics dashboard. Transforms raw data from two APIs (The Odds API + BallDontLie) loaded into Snowflake by Airflow DAGs into analytics-ready models consumed by a Streamlit dashboard.

**Project name:** `nba_betting_analytics`
**Profile:** `nba_betting_analytics` (Snowflake, schema `ipgross`)
**dbt version:** 1.11.4, dbt-snowflake 1.10.4
**Packages:** dbt_utils, dbt_expectations, codegen

---

## Local Setup

```powershell
cd C:\Users\isaac\repos\capstone\airflow-dbt-project\dbt_project
.\venv\Scripts\Activate

# Set env vars (required every new terminal session)
$env:STUDENT_SCHEMA="ipgross"
$env:SNOWFLAKE_USER="ipgross"
$env:SNOWFLAKE_PRIVATE_KEY_PATH="C:\Users\isaac\repos\capstone\airflow-dbt-project\rsa_key.p8"
$env:SNOWFLAKE_PRIVATE_KEY_PASSPHRASE="Houston25"

dbt debug       # verify connection
dbt deps        # install packages
dbt compile --select tag:nba   # check for parse errors
dbt run --select tag:nba --full-refresh   # first build
dbt test --select tag:nba      # run all tests
```

**VS Code note:** Add `"files.watcherExclude": { "**/dbt_packages/**": true }` to VS Code settings to prevent file lock issues on Windows.

---

## Architecture

### Data Flow

```
Airflow Cold Path (daily) → hist_nba_* tables → dbt staging → intermediate → marts
Airflow Hot Path (1-5 min) → live_nba_* tables → dbt live views (always fresh)
```

dbt runs **daily only** after the cold path Airflow DAGs complete. Live models are views — no dbt run needed for real-time data.

### Model Layers

```
models/nba/
├── staging/        # Views, 1:1 with sources. Rename, cast, clean.
├── intermediate/   # Incremental. Heavy transforms: aggregation, joins, windows.
├── marts/          # Tables/incremental. Dashboard-ready analytics.
└── live/           # Views on hot-path tables. Always fresh.
```

| Layer | Materialization | Naming | Purpose |
|-------|----------------|--------|---------|
| Staging | view | `stg_nba__*` | 1:1 source cleaning |
| Intermediate | incremental (merge) | `int_nba__*` | Business logic transforms |
| Marts | table or incremental | `mart_nba__*` | Dashboard consumption |
| Live | view | `live_nba__*` | Real-time Streamlit queries |

### Model Dependency DAG

```
Sources (Snowflake hist_*/live_* tables)
  │
  ▼
Staging (views)
  stg_nba__events, stg_nba__odds_open, stg_nba__games
  stg_nba__player_box_scores, stg_nba__teams
  │
  ├──► int_nba__team_game_stats (player→team aggregation)
  │      └──► int_nba__team_rolling_stats (L10 + season avgs)
  │             ├──► mart_nba__game_grades
  │             └──► mart_nba__game_predictions
  │
  ├──► int_nba__consensus_lines (median across bookmakers)
  │      └──► int_nba__game_betting_results (cover outcomes)
  │             ├──► mart_nba__game_results (central fact)
  │             ├──► mart_nba__team_ats_records (ATS/SU/OU records)
  │             └──► mart_nba__game_predictions
  │
  └──► stg_nba__teams ──► mart_nba__team_matchup_stats

Live sources ──► live_nba__scoreboard, live_nba__player_box_scores
                 live_nba__team_box_scores, live_nba__plays
                 live_nba__odds_current, live_nba__odds_movement
                 live_nba__game_detail
               │
               ├──► live_nba__game_results (Final games + live odds consensus → cover outcomes)
               │      │
               ├──► live_nba__game_grades (live box scores + cold int_nba__team_rolling_stats → letter grades)
               │
               └──► live_nba__player_game_grades (live player stats + cold int_nba__player_rolling_stats → Hollinger grades)
```

**Cross-path references:** The live grade views `ref()` cold-path incremental tables (`int_nba__team_rolling_stats`, `int_nba__player_rolling_stats`) for L10/season baselines. These are materialized tables that the views read on each query. Rolling stats may be ~1 game stale (updated at 3:02 AM); cold-path marts produce exact grades overnight.

---

## Key Business Logic

### Cross-API Join (Odds API ↔ BallDontLie)

The two APIs share no common ID. We join on **(game_date, home_team_name)** because:
- Team names are normalized at ingestion by Airflow (`normalize_team_name()`)
- An NBA team plays at most once per day
- `home_team` is unambiguous (no neutral-site regular season games)

This join happens in `int_nba__game_betting_results`:
```
stg_nba__games JOIN stg_nba__events ON (game_date, home_team_name = home_team)
→ gets event_id → joins to int_nba__consensus_lines
```

### Spread Cover Logic

For spreads, `consensus_line` is from the team's perspective (home favorite = negative):
- **Home covers:** `score_margin + consensus_line > 0` → COVERED
- **Away covers:** `-score_margin + consensus_line > 0` → COVERED
- Equal = PUSH

For h2h: team covers if they win outright.
For totals: Over covers if `total_points > consensus_line`.

### Consensus Line

MEDIAN across all bookmakers (fanduel, draftkings, betmgm, caesars, etc.) for each game/market/side. Computed in `int_nba__consensus_lines`.

### Rolling Averages

Window frame: `ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING` — excludes the current game so values represent **pre-game expectations**. Used for predictions (what should happen) and grades (what was expected vs actual).

### Projected Scores

```
projected_home_score = (home_L10_avg_pts + away_L10_avg_pts_allowed) / 2
projected_away_score = (away_L10_avg_pts + home_L10_avg_pts_allowed) / 2
```

### Expected Value

```
EV = (cover_prob × payout) - (1 - cover_prob) × $1
```
Computed via `calculate_expected_value` macro. Positive EV = favorable bet.

### Bet Rating (1-5 stars)

| EV | Rating |
|----|--------|
| >= 10% | 5 stars |
| >= 5% | 4 stars |
| >= 2% | 3 stars |
| >= 0% | 2 stars |
| < 0% | 1 star |

---

## Sources

Two source groups in `_nba__sources.yml`:

**`nba_cold`** (daily batch, freshness checked):
- `hist_nba_events` — game schedule from Odds API
- `hist_nba_odds_open` — morning-line odds from Odds API
- `hist_nba_games` — final scores from BallDontLie
- `hist_nba_player_box_scores` — player stats from BallDontLie
- `hist_nba_teams` — team reference (manual, no freshness)

**`nba_live`** (1-5 min refresh, no dbt freshness):
- `live_nba_scoreboard` — live game scores
- `live_nba_player_box_scores` — live player stats
- `live_nba_plays` — play-by-play (2025+ only)
- `live_nba_odds` — current odds
- `archive_nba_odds_snapshots` — append-only odds history

---

## Macros (`macros/nba/`)

| Macro | Purpose | Example |
|-------|---------|---------|
| `safe_divide(num, denom)` | Division without zero errors | `{{ safe_divide('sum(fgm)', 'sum(fga)') }}` |
| `parse_minutes(col)` | "32:15" → 32.25 decimal | `{{ parse_minutes('min') }}` |
| `american_odds_to_implied_prob(col)` | -110 → 0.524 | `{{ american_odds_to_implied_prob('outcome_price') }}` |
| `calculate_expected_value(prob, odds)` | EV of a $1 bet | `{{ calculate_expected_value('cover_prob', 'consensus_price') }}` |

---

## Variables (`dbt_project.yml`)

```yaml
vars:
  nba_current_season: '2024-25'    # Update each October
  nba_rolling_window: 10           # L10 rolling average window
```

---

## Incremental Strategy

All incremental models use `merge` strategy with `game_date` as the partition filter:

```sql
{% if is_incremental() %}
    where game_date > (select max(game_date) from {{ this }})
{% endif %}
```

First run requires `--full-refresh`. Subsequent daily runs only process new dates.

**Rolling stats special case:** Pulls 30-day lookback for window function context, then filters output to only new rows.

---

## Testing Strategy

**Staging (thorough):** unique, not_null, accepted_values, dbt_expectations range checks, relationships
**Intermediate:** composite key uniqueness, range checks on advanced metrics, accepted_values on cover_result
**Marts:** key uniqueness, rate columns between 0-1
**Live (minimal):** only not_null + unique on game_id (speed matters)

**Custom data tests** in `data-tests/nba/`:
- `assert_no_negative_game_scores` — no game should have negative scores
- `assert_spread_covers_match_games` — spread outcomes = 2× game count per date

---

## Streamlit Dashboard Pages (downstream consumer)

| Page | Primary dbt Model(s) |
|------|---------------------|
| Live Scoreboard | `live_nba__scoreboard`, `live_nba__odds_current` |
| Game Detail | `live_nba__game_detail`, `live_nba__plays`, `live_nba__player_box_scores`, `live_nba__game_results`, `live_nba__game_grades`, `live_nba__player_game_grades` |
| Odds Movement | `live_nba__odds_movement` |
| Game Predictions | `mart_nba__game_predictions` |
| ATS Records | `mart_nba__team_ats_records` |
| Team Matchup | `mart_nba__team_matchup_stats` |
| Post-Game Grades (historical) | `mart_nba__game_grades`, `mart_nba__player_game_grades` |
| Game Results (historical) | `mart_nba__game_results` |

---

## Useful Commands

```powershell
# Run all NBA models
dbt run --select tag:nba --full-refresh

# Run only marts
dbt run --select tag:marts

# Run a specific model + its upstream deps
dbt run --select +mart_nba__game_results

# Test everything
dbt test --select tag:nba

# Check source freshness
dbt source freshness --select source:nba_cold

# Compile without running (check SQL)
dbt compile --select mart_nba__game_predictions
```

---

## Code Conventions

- **No `SELECT *`** — all columns explicitly listed
- **Leading commas** — per `.sqlfluff` config
- **Lowercase SQL keywords** — per `.sqlfluff` config
- **4-space indentation**
- **CTE pattern:** `with source as (...) select ... from source`
- **Column aliases:** use `as` keyword, right-aligned with padding
- **Macro usage:** prefer macros over inline math for reusable logic
- **Incremental models:** always include `{% if is_incremental() %}` filter
