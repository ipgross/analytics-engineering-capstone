# CLAUDE.md - NBA Analytics Capstone Project

## Project Overview

Capstone project building an end-to-end **spread-beating analytics dashboard** for NBA betting. Ingests:
- **Betting odds** from The Odds API (h2h, spreads, totals)
- **Game results** from BallDontLie API (final scores for spread covers)
- **Player box scores** from BallDontLie API (aggregated to team level in dbt)

Stores raw JSON.gz archives in S3, loads typed Parquet to Snowflake, transforms via dbt for spread cover analysis.

**Branch:** `capstone/nba-live-analytics` (do NOT merge to main)
**Deployment:** Astronomer (DataExpert shared instance)
**Student Schema:** `ipgross`

---

## IMPORTANT: File Scope

This repo contains bootcamp files that are NOT part of the capstone. **Only read/modify these paths:**

```
dags/capstone/                    # Capstone DAGs (cold + hot path)
include/capstone/                 # Capstone utility modules
archive/old_dags/                 # Retired v1 DAGs (reference only, outside Airflow scan)
dbt_project/models/nba/           # [Future] dbt models
```

**IGNORE these paths** (bootcamp reference only):
- `dags/eczachly/` - Educational examples
- `include/eczachly/` - Educational utilities
- `dags/dbt/` - Generic dbt patterns

---

## Architecture

### Hot/Cold Path Design

```
                    ┌─────────────────────────────────────────────┐
                    │           COLD PATH (Phase 1 - Current)     │
                    │  Daily batch: historical system of record   │
                    │  Tables: hist_nba_* (via stg_nba_* staging) │
                    │  Load: Parquet → Stage → DQ → MERGE         │
                    │  Schedule: Daily (7am ET events/odds,       │
                    │           3am ET finalize)                  │
                    └─────────────────────────────────────────────┘

                    ┌─────────────────────────────────────────────┐
                    │           HOT PATH (Phase 2 - Active)       │
                    │  Live serving: 1-minute updates             │
                    │  Tables: live_nba_*                         │
                    │  Load: MERGE FROM VALUES (no S3/staging)    │
                    │  Schedule: 1 min (scores) / 5 min (odds)   │
                    └─────────────────────────────────────────────┘
```

### Data Flow (Hot Path)

```
Every 1 min (game hours only):
  BallDontLie /games ────→ Python validation → MERGE INTO live_nba_scoreboard
  BallDontLie /box_scores → Python validation → MERGE INTO live_nba_player_box_scores
  BallDontLie /plays ────→ Python validation → MERGE INTO live_nba_plays (per active game)

Every 5 min (game hours only):
  Odds API /odds ────────→ Python validation → MERGE INTO live_nba_odds
                                              → INSERT INTO archive_nba_odds_snapshots

Hourly:
  Cleanup: DELETE games older than 2 days from all live tables

Event-driven (when game goes Final):
  Scoreboard DAG detects newly-Final games (pre vs post MERGE status)
  → triggers nba_finalize_games (cold-path reconcile)
  → triggers nba_dbt_finalize (dbt WAP pipeline)
  Result: ~10-20 min from game Final to dbt tables refreshed
```

**No S3. No staging. No DQ.** Direct API → Python validation → MERGE FROM VALUES.
Speed is the priority. Cold path is the safety net.

**MERGE safety:** Empty API response = 0 changes (table intact). Games that end stay
in BDL response (status=Final). Odds that disappear from API keep their closing line
because MERGE never touches unmatched target rows.

### Data Flow (Cold Path)

```
           ┌→ raw JSON.gz → S3 archive (durable, for replay)
API fetch ─┤
           └→ Python normalizes → typed rows → Parquet → S3 bulk
                                                           ↓
                                                COPY INTO stg_nba_* (FORCE=TRUE)
                                                           ↓
                                                DQ checks on stg_nba_*
                                                           ↓
                                                MERGE INTO hist_nba_* FROM stg_nba_*
                                                           ↓
                                                DELETE FROM stg_nba_* (cleanup)
                                                           ↓
                                                INSERT INTO ops.ingestion_runs
```

One API fetch produces two outputs:
1. **Archive:** Raw JSON compressed with gzip → `ipgross/archive/{dataset}/ds=YYYY-MM-DD/{dataset}.json.gz`
2. **Bulk load:** Python normalizes fields → PyArrow Parquet → `ipgross/bulk/{dataset}/ds=YYYY-MM-DD/records.parquet` → Snowflake staging → DQ → MERGE

### Directory Structure (Capstone Only)

```
airflow-dbt-project/
├── dags/capstone/
│   ├── nba_ingest_events_dag.py         # Events schedule (The Odds API)
│   ├── nba_ingest_odds_dag.py           # Morning-line odds (The Odds API)
│   ├── nba_finalize_games_dag.py        # Final scores + box scores + postponed detection (BDL)
│   ├── nba_dbt_daily_dag.py             # dbt after events+odds ingestion (Cosmos WAP)
│   ├── nba_dbt_finalize_dag.py          # dbt after game finalization (Cosmos WAP)
│   ├── nba_ingest_upcoming_dag.py       # Events + odds for next 7 days (The Odds API)
│   ├── nba_dbt_full_refresh_dag.py      # Manual full-refresh dbt run
│   ├── nba_live_scoreboard_dag.py       # Live scores + box scores + plays (every 1 min)
│   └── nba_live_odds_dag.py             # Live odds + archive snapshots (every 5 min)
│
├── include/capstone/                     # Utility modules
│   ├── __init__.py
│   ├── config.py                         # Credentials, constants, season dates, game window
│   ├── api_client.py                     # The Odds API client (cold + live odds)
│   ├── balldontlie_client.py             # BallDontLie API client (cold + live games/box/plays)
│   ├── storage.py                        # S3: upload_archive (JSON.gz) + upload_bulk (Parquet)
│   ├── database.py                       # Snowflake: cold (stage/validate/merge) + hot (MERGE FROM VALUES)
│   ├── callbacks.py                      # Failure alerting (on_failure_callback for all DAGs)
│   └── scripts/
│       ├── rename_old_tables.sql         # Rename raw_* → old_raw_* (run manually)
│       ├── create_hist_tables.sql        # Create hist_* tables (run manually)
│       ├── create_stg_tables.sql         # Create stg_* transient tables (run manually)
│       ├── create_ops_table.sql          # Create ops_ingestion_runs (run manually)
│       ├── create_live_tables.sql        # Create live_* tables + VIEW (run manually)
│       ├── create_nba_events_table.sql   # [Legacy] original DDL
│       ├── create_nba_odds_table.sql     # [Legacy] original DDL
│       └── create_balldontlie_tables.sql # [Legacy] original DDL
│
├── archive/old_dags/                     # Retired DAGs (outside Airflow scan path)
│   ├── old_nba_events_daily_dag.py
│   ├── old_nba_odds_daily_dag.py
│   ├── old_nba_games_daily_dag.py
│   ├── old_nba_games_live_dag.py
│   ├── old_nba_player_box_scores_daily_dag.py
│   ├── old_nba_player_box_scores_live_dag.py
│   ├── old_nba_teams_dag.py
│   ├── nba_backfill_dag.py               # Retired: manual backfill
│   ├── nba_teams_load_dag.py             # Retired: team reference load
│   └── nba_live_backfill_dag.py          # Retired: live table backfill
│
└── dbt_project/models/nba/               # [Future] dbt transforms
```

### Module Responsibilities

| Module | Purpose |
|--------|---------|
| `config.py` | Credentials, table names (`HIST_*`, `STG_*`, `LIVE_*`, `OPS_TABLE`), S3 prefixes, season dates, `TEAM_NAME_MAP`, `normalize_team_name()`, `is_game_window()`, `get_live_game_dates()` |
| `api_client.py` | The Odds API client — cold: `fetch_events_for_date()`, `fetch_odds_for_date()` / hot: `fetch_live_odds()`. Normalizes team names at ingestion via `normalize_team_name()`. |
| `balldontlie_client.py` | BallDontLie client — cold: `fetch_games_for_date()`, `fetch_box_scores_for_date()` / hot: `fetch_live_games()`, `fetch_live_box_scores()`, `fetch_live_plays()` |
| `storage.py` | 2 generic S3 functions: `upload_archive()` (JSON.gz) + `upload_bulk()` (Parquet via PyArrow) — cold path only |
| `database.py` | Cold: stage/validate/merge/log per dataset, DQ runner, `mark_postponed_events()`. Hot: `merge_live_*()`, `_escape_sql()`, `_validate_*()`, `snapshot_live_odds()`, `cleanup_live_tables()` |
| `callbacks.py` | Failure alerting: `alert_on_failure()` callback for DAG default_args |

---

## Credentials Pattern

**Bootcamp constraint:** No admin access to Astronomer Variables, so we use a mix:

```python
# HARDCODED in config.py (student-specific)
STUDENT_SCHEMA = "ipgross"
SNOWFLAKE_USER = "ipgross"
SNOWFLAKE_PASSWORD = "..."
ODDS_API_KEY = "..."
SNOWFLAKE_ACCOUNT = "aab46027.us-west-2"

# AIRFLOW VARIABLES (shared infrastructure)
Variable.get("DATAEXPERT_AWS_ACCESS_KEY_ID")
Variable.get("DATAEXPERT_AWS_SECRET_ACCESS_KEY")
Variable.get("AWS_S3_BUCKET_TABULAR")
```

---

## The Odds API Documentation

### Base URL
```
https://api.the-odds-api.com/v4
```

### Sport Key
```
basketball_nba
```

### Endpoints & Costs

| Endpoint | Cost | Use Case |
|----------|------|----------|
| `GET /sports` | FREE | List available sports |
| `GET /sports/{sport}/events` | FREE | Current/upcoming games |
| `GET /sports/{sport}/odds` | 1 x markets x regions | Current odds |
| `GET /sports/{sport}/scores` | 1 (2 with daysFrom) | Game scores |
| `GET /historical/sports/{sport}/events` | 1 (FREE if empty) | Past game events |
| `GET /historical/sports/{sport}/odds` | 10 x markets x regions | Past odds snapshots |

### Historical Events Endpoint (Used for Backfill)

```
GET /v4/historical/sports/basketball_nba/events
```

**Parameters:**
- `apiKey` (required): API key
- `date` (required): ISO8601 timestamp (e.g., `2023-10-24T23:59:59Z`)
- `commenceTimeFrom`: Filter games starting after this time
- `commenceTimeTo`: Filter games starting before this time
- `dateFormat`: `iso` (default) or `unix`

**Response:**
```json
{
  "timestamp": "2023-10-25T00:00:00Z",
  "previous_timestamp": "...",
  "next_timestamp": "...",
  "data": [
    {
      "id": "abc123def456",
      "sport_key": "basketball_nba",
      "sport_title": "NBA",
      "commence_time": "2023-10-24T23:30:00Z",
      "home_team": "Los Angeles Lakers",
      "away_team": "Denver Nuggets"
    }
  ]
}
```

### Regular Events Endpoint (Used for Today/Future)

```
GET /v4/sports/basketball_nba/events
```

**Cost:** FREE (0 credits)

**Parameters:**
- `apiKey` (required)
- `commenceTimeFrom`: Filter start
- `commenceTimeTo`: Filter end

### Historical Odds Endpoint

```
GET /v4/historical/sports/basketball_nba/odds
```

**Cost:** 10 x markets x regions (e.g., 30 credits for 3 markets, 1 region)

**Parameters:**
- `apiKey` (required)
- `date` (required): ISO8601 timestamp
- `regions`: us, uk, au, eu (comma-separated)
- `markets`: h2h, spreads, totals (comma-separated)
- `oddsFormat`: american or decimal

**Response includes:**
- `timestamp`, `previous_timestamp`, `next_timestamp` for navigation
- `data`: Array of events with bookmaker odds

### Scores Endpoint

```
GET /v4/sports/basketball_nba/scores
```

**Cost:** 1 credit (2 with `daysFrom`)

**Parameters:**
- `daysFrom`: 1-3 to get completed games from past days
- `eventIds`: Filter to specific games

### Rate Limiting

- Response headers: `x-requests-remaining`, `x-requests-used`
- Implement 1 request/second rate limiting
- Retry with backoff on 429 errors: [5s, 30s, 120s]

### API Quirks / Known Issues

**Historical endpoint returns point-in-time snapshots (completed games vanish):**

The events/odds endpoints only return **in-play and pre-match** events. Once a game finishes, it's removed. Historical snapshots mirror this — a late snapshot (e.g., `T23:59:59Z` = 6:59 PM ET) misses matinee and afternoon games that already completed.

**Fix:** Use a morning snapshot (`T12:00:00Z` = 7am ET) when all games are still pre-match.

**commenceTimeFrom/To — use a wide UTC window, not a single UTC day:**

Evening ET games (7pm+) fall into the next UTC day. A single-day UTC window misses them.

```python
# BAD - single UTC day misses evening ET games
params = {
    "commenceTimeFrom": "2023-11-08T00:00:00Z",
    "commenceTimeTo": "2023-11-08T23:59:59Z",
}

# GOOD - wide UTC window covering the full Eastern date
next_day = date + timedelta(days=1)
params = {
    "date": f"{date_str}T12:00:00Z",        # Morning snapshot
    "commenceTimeFrom": f"{date_str}T10:00:00Z",  # 5am ET
    "commenceTimeTo": f"{next_day}T06:00:00Z",    # 1am ET next day
}
# Still filter client-side by Eastern date as safety net
```

### Team Name Normalization

The Odds API and BallDontLie use different names for some teams (e.g., "Los Angeles Clippers" vs "LA Clippers"). Team names are normalized **at ingestion** in `api_client.py` using `normalize_team_name()` from `config.py`, so all warehouse joins work with simple equality.

```python
# In config.py
TEAM_NAME_MAP = {
    "Los Angeles Clippers": "LA Clippers",
}

def normalize_team_name(name: str) -> str:
    return TEAM_NAME_MAP.get(name, name)
```

Raw JSON.gz archives in S3 preserve the original API names. Only the Parquet/Snowflake layer uses normalized names.

### Cost Optimization Tips

1. Use FREE `/events` endpoint for current/future games
2. Historical events costs 1 credit (FREE if no games that day)
3. Batch historical odds requests by date, not by event
4. Only request needed markets/regions
5. Off-season dates should skip API calls entirely

---

## BallDontLie API Documentation

### Base URL
```
https://api.balldontlie.io/v1
```

### Authentication
```
Authorization: {BALLDONTLIE_API_KEY}
```

Header-based authentication (not query parameter).

### Rate Limits
- GOAT tier: 600 requests/minute (current subscription)
- Sufficient for historical backfill

### Endpoints Used

| Endpoint | Purpose | Notes |
|----------|---------|-------|
| `GET /games?dates[]={ds}` | Final scores | Filter by date, returns completed games |
| `GET /box_scores?date={ds}` | Player stats | Aggregate to team in dbt |
| `GET /teams` | Team reference | One-time load, 30 NBA teams |

### Games Endpoint

```
GET /games?dates[]=2024-01-15&per_page=100
```

**Response:**
```json
{
  "data": [{
    "id": 473028,
    "date": "2024-01-15",
    "season": 2024,
    "status": "Final",
    "home_team": { "id": 1, "full_name": "Atlanta Hawks", ... },
    "visitor_team": { "id": 2, "full_name": "Boston Celtics", ... },
    "home_team_score": 108,
    "visitor_team_score": 112
  }]
}
```

**Key Logic:**
- Filter to `status="Final"` only
- Extract scores for spread cover calculation: `(home_score - visitor_score) > -spread`

### Box Scores Endpoint

```
GET /box_scores?date=2024-01-15
```

Returns player-level stats for all games on that date. We store raw player data and aggregate to team level in dbt.

**Response includes per player:**
- `pts`, `reb`, `oreb`, `dreb`, `ast`, `stl`, `blk`, `turnover`, `pf`
- `fgm`, `fga`, `fg_pct`, `fg3m`, `fg3a`, `fg3_pct`, `ftm`, `fta`, `ft_pct`
- `min` (playing time in "MM:SS" format)

### Teams Endpoint

```
GET /teams?per_page=100
```

Returns all 30 NBA teams with:
- `id`, `full_name`, `name`, `city`, `abbreviation`
- `conference` (East/West), `division`

### Why Player-Level Box Scores?

1. **Faster ingestion** - No Python aggregation, just dump raw API response
2. **Flexibility** - Can analyze player data later if needed
3. **dbt optimization** - SQL aggregation is fast and testable

### dbt Aggregation Example

```sql
-- stg_nba_team_game_stats: Aggregate player -> team
SELECT
    game_id,
    team_id,
    game_date,
    is_home,
    SUM(pts) as pts,
    SUM(reb) as reb,
    SUM(oreb) as oreb,
    SUM(dreb) as dreb,
    SUM(ast) as ast,
    SUM(turnover) as turnovers,
    SUM(stl) as steals,
    SUM(blk) as blocks,
    SUM(pf) as pf,
    SUM(fgm)::FLOAT / NULLIF(SUM(fga), 0) as fg_pct,
    SUM(fg3m)::FLOAT / NULLIF(SUM(fg3a), 0) as fg3_pct,
    SUM(ftm)::FLOAT / NULLIF(SUM(fta), 0) as ft_pct
FROM hist_nba_player_box_scores
GROUP BY game_id, team_id, game_date, is_home
```

### Advanced Metrics (Calculated in dbt)

```sql
-- Possessions formula (standard NBA)
possessions = FGA + 0.475 * FTA - OREB + TOV

-- Offensive Rating (points per 100 possessions)
off_rating = PTS / possessions * 100

-- Defensive Rating (opponent points per 100 possessions)
-- Derived by joining team with opponent
def_rating = opponent_PTS / possessions * 100
```

---

## DAG Patterns

### Standard Cold Path DAG Structure

```python
from airflow.sdk import dag
from airflow.providers.standard.operators.python import PythonOperator, ShortCircuitOperator
from datetime import datetime, timedelta

# Import from include/capstone/
from include.capstone.config import is_nba_season
from include.capstone.api_client import fetch_events_for_date
from include.capstone.storage import upload_archive, upload_bulk, build_events_archive_payload
from include.capstone.database import load_events_to_snowflake


# Task functions at module level (not inside dag)
def run_check_season(**context):
    return is_nba_season(context["ds"])

def run_fetch(**context):
    events = fetch_events_for_date(context["ds"])
    return events

def run_upload_archive(**context):
    ti = context["ti"]
    ds = context["ds"]
    events = ti.xcom_pull(task_ids="fetch_events")
    payload = build_events_archive_payload(ds, events, "historical")
    return upload_archive("events", payload, date_str=ds)

def run_upload_bulk(**context):
    ti = context["ti"]
    ds = context["ds"]
    events = ti.xcom_pull(task_ids="fetch_events")
    return upload_bulk("events", events, date_str=ds)

def run_load(**context):
    ti = context["ti"]
    ds = context["ds"]
    bulk_path = ti.xcom_pull(task_ids="upload_bulk")
    return load_events_to_snowflake(ds, bulk_path)


@dag(
    dag_id="dag_name",
    default_args={
        "owner": "capstone",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=30),
        "on_failure_callback": alert_on_failure,
    },
    start_date=datetime(2023, 10, 24),
    schedule="0 12 * * *",  # 7am ET = 12:00 UTC
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=True,
    tags=["capstone", "nba", "cold-path"],
)
def dag_name():
    check = ShortCircuitOperator(task_id="check_nba_season", python_callable=run_check_season)
    fetch = PythonOperator(task_id="fetch_events", python_callable=run_fetch)
    archive = PythonOperator(task_id="upload_archive", python_callable=run_upload_archive)
    bulk = PythonOperator(task_id="upload_bulk", python_callable=run_upload_bulk)
    load = PythonOperator(task_id="load_to_snowflake", python_callable=run_load)

    check >> fetch >> [archive, bulk] >> load

dag_name()
```

### Idempotency Pattern (Stage → DQ → MERGE)

The cold path uses a production-standard **staging + MERGE** pattern for idempotent data ingestion:

```
API fetch → S3 (archive + bulk Parquet) → COPY INTO stg_* (FORCE=TRUE)
→ DQ checks on stg_* → MERGE INTO hist_* → DELETE stg_* → log ops.ingestion_runs
```

**Why staging + MERGE:**
- **Staging** gives us a place to run DQ checks before touching production
- **MERGE** is an atomic upsert — matched rows update, unmatched rows insert, one statement
- **No data loss** — never deletes without simultaneously having replacement data
- **True idempotency** — re-running the same date produces identical results
- **FORCE=TRUE on COPY INTO** bypasses Snowflake's 64-day load history (which caused data loss with the old pattern)

**Staging tables** are TRANSIENT (no fail-safe = cheaper). Cleared per-date with `DELETE WHERE ds` at start of each load, so stale data from failed runs is automatically cleaned up.

```python
# In database.py — each dataset has 4 operations:
def stage_events(date_str, bulk_s3_path):    # COPY INTO stg_* with FORCE=TRUE
def validate_events(date_str):                # DQ checks (raises ValueError on failure)
def merge_events(date_str):                   # MERGE INTO hist_* + cleanup stg_*
def log_ingestion_run(date_str, ...):         # INSERT INTO ops.ingestion_runs
```

**DQ checks** return boolean columns — any False = ValueError raised = Airflow retry:
```sql
SELECT
    COUNT(*) > 0                           AS has_data,
    COUNT_IF(event_id IS NULL) = 0         AS event_id_not_null,
    COUNT(*) = COUNT(DISTINCT event_id)    AS no_duplicates,
    COUNT(DISTINCT ds) = 1                 AS single_date_only
FROM stg_nba_events WHERE ds = '{ds}'
```

**Games DQ** cross-references non-postponed events for expected count:
```sql
COUNT(DISTINCT game_id) = (
    SELECT COUNT(DISTINCT event_id) FROM hist_nba_events
    WHERE ds = '{ds}' AND (postponed = FALSE OR postponed IS NULL)
) AS game_count_matches_events
```

**Empty classification:** 0 records on off-days = `EMPTY_EXPECTED` (task succeeds).
Events with 0 games = `EMPTY_UNEXPECTED` (task fails + Airflow retries).

### Bulk Loading: Parquet + COPY INTO

1. Python normalizes API response into typed dicts
2. `storage.upload_bulk()` converts to PyArrow Table using typed schema, writes Parquet to S3
3. `database.stage_*()` creates external stage, runs COPY INTO stg_* with FORCE=TRUE

**Why Parquet (not JSON)?**
- Parquet embeds column types — no casting errors
- Columnar format = faster reads, smaller files
- Industry standard for data lake / warehouse loading

**Parquet Stage Setup:**
```python
# In database.py — shared helper for all stage functions
def _setup_parquet_stage(cursor, stage_name, dataset):
    format_name = f"{STUDENT_SCHEMA}.{dataset}_parquet_fmt"
    stage_url = f"s3://{bucket}/{S3_BULK_PREFIX}/{dataset}/"
    cursor.execute(f"CREATE OR REPLACE FILE FORMAT {format_name} TYPE = PARQUET")
    cursor.execute(f"""
        CREATE OR REPLACE STAGE {stage_name}
        URL = '{stage_url}'
        CREDENTIALS = (AWS_KEY_ID = '{aws_key}' AWS_SECRET_KEY = '{aws_secret}')
        FILE_FORMAT = {format_name}
    """)
```

### Ops Metadata Table

Every ingestion run is logged to `ops_ingestion_runs`:
```sql
-- Status values: SUCCESS, EMPTY_EXPECTED, EMPTY_UNEXPECTED, FAILED
SELECT ds, dataset, status, rows_merged, elapsed_sec FROM ops_ingestion_runs;
```

### Off-Season Handling

```python
# In config.py
SEASON_DATE_RANGES = {
    "2023-24": ("2023-10-24", "2024-06-17"),
    "2024-25": ("2024-10-22", "2025-06-22"),
    "2025-26": ("2025-10-21", "2026-06-21"),
}

def is_nba_season(date_str: str) -> bool:
    for start, end in SEASON_DATE_RANGES.values():
        if start <= date_str <= end:
            return True
    return False

# In DAG — ShortCircuitOperator stops downstream tasks if False
check_season = ShortCircuitOperator(
    task_id="check_nba_season",
    python_callable=lambda **ctx: is_nba_season(ctx["ds"]),
)
```

### Cross-DAG Coordination

**ExternalTaskSensors** (dbt DAGs wait for ingestion to complete):
- `nba_dbt_daily` waits for `nba_ingest_events` and `nba_ingest_odds` (2-min execution_delta)
- Uses `mode="reschedule"` to free up workers while waiting

**TriggerDagRunOperator** (finalize → dbt chain):
- `nba_finalize_games` triggers `nba_dbt_finalize` after both branches complete
- Passes `game_date` via `conf` for event-triggered runs

**Event-driven triggers** (live scoreboard → finalize):
- `nba_live_scoreboard` detects newly-Final games and calls `trigger_dag("nba_finalize_games")`
- Non-fatal — 3am scheduled run catches misses
- `max_active_runs=2` on finalize DAG naturally debounces concurrent triggers

### Failure Alerting

All DAGs use `on_failure_callback=alert_on_failure` in `default_args`. The callback in `include/capstone/callbacks.py` logs structured failure info. Future: Slack/email integration.

---

## Code Style Preferences

### General
- Simple, readable code over clever abstractions
- Each module has ONE responsibility
- Functions should be focused and short
- Use type hints for function signatures
- Docstrings for public functions

### Logging (Structured)
```python
import logging
logger = logging.getLogger(__name__)

# Structured key=value format for easy parsing
logger.info(
    f"fetch_events | ds={date_str} | events={len(events)}"
    f" | elapsed_sec={elapsed:.2f} | api_remaining={usage.get('requests_remaining')}"
)
```

### Error Handling
- Let errors propagate (Airflow will retry)
- Use try/finally for cleanup (close connections)
- Rate limit errors: retry with backoff [5s, 30s, 120s]
- Both API clients have 3-retry logic built in

### SQL in Python
```python
# Escape single quotes
home_team = (event.get("home_team") or "").replace("'", "''")

# Use f-strings for simple queries
query = f"DELETE FROM {TABLE} WHERE ds = '{date_str}'"
```

### Timezone Handling
```python
from zoneinfo import ZoneInfo
EASTERN = ZoneInfo("America/New_York")

# Convert UTC to Eastern
utc_dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
et_dt = utc_dt.astimezone(EASTERN)
game_date_et = et_dt.strftime("%Y-%m-%d")
```

---

## S3 Storage

### Path Structure
```
ipgross/
├── archive/                              # Raw JSON.gz archives (replay capability)
│   ├── events/ds=YYYY-MM-DD/events.json.gz
│   ├── odds_open/ds=YYYY-MM-DD/odds_open.json.gz
│   ├── games/ds=YYYY-MM-DD/games.json.gz
│   ├── box_scores/ds=YYYY-MM-DD/box_scores.json.gz
│   └── teams/teams.json.gz
│
├── bulk/                                 # Parquet files for Snowflake COPY INTO
│   ├── events/ds=YYYY-MM-DD/records.parquet
│   ├── odds_open/ds=YYYY-MM-DD/records.parquet
│   ├── games/ds=YYYY-MM-DD/records.parquet
│   ├── box_scores/ds=YYYY-MM-DD/records.parquet
│   └── teams/records.parquet
```

**Changes from old paths:** Season partitioning removed from S3 (redundant — season is a column). Archive/bulk separated at top level. Archives are gzipped JSON. Bulk load uses Parquet.

### Archive Format (JSON.gz with Metadata)
```json
{
  "metadata": {
    "ds": "2023-10-24",
    "event_count": 12,
    "endpoint_used": "historical",
    "ingested_at": "2025-01-31T15:00:00Z"
  },
  "events": [...]
}
```

### Bulk Load Format (Parquet)
Typed Parquet files generated by PyArrow using explicit schemas defined in `storage.py`. Each dataset has a `pa.schema()` specifying column names and types. Snowflake COPY INTO reads these directly.

---

## Snowflake Tables

### Table Naming

| Status | Prefix | Example |
|--------|--------|---------|
| **Active (cold path)** | `hist_nba_` | `ipgross.hist_nba_events` |
| **Retired (kept for reference)** | `old_raw_nba_` | `ipgross.old_raw_nba_events` |
| **Active (hot path)** | `live_nba_` | `ipgross.live_nba_scoreboard` |
| **Archive (hot path)** | `archive_nba_` | `ipgross.archive_nba_odds_snapshots` |

### hist_nba_events (The Odds API)
```sql
CREATE TABLE IF NOT EXISTS ipgross.hist_nba_events (
    ds                  DATE NOT NULL,
    event_id            VARCHAR(64) NOT NULL,
    season              VARCHAR(10) NOT NULL,
    sport_key           VARCHAR(50) NOT NULL,
    sport_title         VARCHAR(100),
    commence_time_utc   TIMESTAMP_NTZ NOT NULL,
    commence_time_et    TIMESTAMP_NTZ NOT NULL,
    home_team           VARCHAR(100) NOT NULL,
    away_team           VARCHAR(100) NOT NULL,
    postponed           BOOLEAN DEFAULT FALSE,
    s3_path             VARCHAR(500),
    ingested_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (ds, event_id)
);
```

### hist_nba_odds_open (The Odds API)
```sql
CREATE TABLE IF NOT EXISTS ipgross.hist_nba_odds_open (
    ds                      DATE NOT NULL,
    event_id                VARCHAR(64) NOT NULL,
    season                  VARCHAR(10) NOT NULL,
    home_team               VARCHAR(100) NOT NULL,
    away_team               VARCHAR(100) NOT NULL,
    commence_time_utc       TIMESTAMP_NTZ NOT NULL,
    commence_time_et        TIMESTAMP_NTZ NOT NULL,
    bookmaker_key           VARCHAR(50) NOT NULL,
    bookmaker_title         VARCHAR(100),
    bookmaker_last_update   TIMESTAMP_NTZ,
    market_key              VARCHAR(20) NOT NULL,
    outcome_name            VARCHAR(100) NOT NULL,
    outcome_price           INTEGER NOT NULL,
    outcome_point           FLOAT,
    s3_path                 VARCHAR(500),
    ingested_at             TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (ds, event_id, bookmaker_key, market_key, outcome_name)
);
```

### hist_nba_games (BallDontLie)
```sql
CREATE TABLE IF NOT EXISTS ipgross.hist_nba_games (
    ds                  DATE NOT NULL,
    game_id             INTEGER NOT NULL,
    season              VARCHAR(10) NOT NULL,
    game_date           DATE NOT NULL,
    status              VARCHAR(20) NOT NULL,
    home_team_id        INTEGER NOT NULL,
    home_team_name      VARCHAR(100) NOT NULL,
    home_team_score     INTEGER,
    visitor_team_id     INTEGER NOT NULL,
    visitor_team_name   VARCHAR(100) NOT NULL,
    visitor_team_score  INTEGER,
    postseason          BOOLEAN DEFAULT FALSE,
    s3_path             VARCHAR(500),
    ingested_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (ds, game_id)
);
```

### hist_nba_player_box_scores (BallDontLie)
```sql
CREATE TABLE IF NOT EXISTS ipgross.hist_nba_player_box_scores (
    ds                  DATE NOT NULL,
    game_id             INTEGER NOT NULL,
    player_id           INTEGER NOT NULL,
    player_name         VARCHAR(100) NOT NULL,
    team_id             INTEGER NOT NULL,
    team_name           VARCHAR(100) NOT NULL,
    season              INTEGER NOT NULL,
    game_date           DATE NOT NULL,
    is_home             BOOLEAN NOT NULL,
    min                 VARCHAR(10),
    pts                 INTEGER,
    reb                 INTEGER,
    oreb                INTEGER,
    dreb                INTEGER,
    ast                 INTEGER,
    stl                 INTEGER,
    blk                 INTEGER,
    turnover            INTEGER,
    pf                  INTEGER,
    fgm                 INTEGER,
    fga                 INTEGER,
    fg_pct              FLOAT,
    fg3m                INTEGER,
    fg3a                INTEGER,
    fg3_pct             FLOAT,
    ftm                 INTEGER,
    fta                 INTEGER,
    ft_pct              FLOAT,
    s3_path             VARCHAR(500),
    ingested_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (ds, game_id, player_id)
);
```

### hist_nba_teams (BallDontLie)
```sql
CREATE TABLE IF NOT EXISTS ipgross.hist_nba_teams (
    team_id             INTEGER NOT NULL,
    full_name           VARCHAR(100) NOT NULL,
    name                VARCHAR(50) NOT NULL,
    city                VARCHAR(50) NOT NULL,
    abbreviation        VARCHAR(10) NOT NULL,
    conference          VARCHAR(10) NOT NULL,
    division            VARCHAR(20) NOT NULL,
    ingested_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (team_id)
);
```

---

## Current DAGs (Cold Path)

| DAG | Schedule | Source | Purpose |
|-----|----------|--------|---------|
| `nba_ingest_events` | 7am ET (12:00 UTC) | The Odds API | Game schedule/events for ds |
| `nba_ingest_odds` | 7am ET (12:00 UTC) | The Odds API | Morning-line odds for ds |
| `nba_finalize_games` | 3am ET (08:00 UTC) + event-triggered | BallDontLie | Final scores + box scores for ds-1 + postponed detection |
| `nba_dbt_daily` | 7:02am ET (12:02 UTC) | dbt (Cosmos) | dbt WAP after events+odds ingestion |
| `nba_dbt_finalize` | 3:02am ET (08:02 UTC) + event-triggered | dbt (Cosmos) | dbt WAP after game finalization |
| `nba_ingest_upcoming` | 8am ET (13:00 UTC) | The Odds API | Events + odds for next 7 days, then dbt rebuild |
| `nba_dbt_full_refresh` | Manual trigger | dbt (Cosmos) | Full-refresh rebuild of all dbt models |

### DAG Details

**`nba_ingest_events`** — `check >> fetch >> [archive, bulk] >> stage >> dq_check >> merge >> log_ingestion`
- Smart endpoint selection: historical (past), scores (today after 10am), regular (future)
- Uses `ds` as game_date
- Empty events on off-days → EMPTY_EXPECTED (logged, task succeeds)

**`nba_ingest_odds`** — `check >> fetch >> [archive, bulk] >> stage >> dq_check >> merge >> log_ingestion`
- Captures "morning line" — opening odds before games start
- Uses `ds` as game_date
- Regular endpoint (3 credits) in steady state; historical (30 credits) for manual past triggers

**`nba_finalize_games`** — Most complex DAG
```
check >> wait_for_events >> [fetch_games, fetch_box_scores]
fetch_games >> [games_archive, games_bulk] >> stage_games >> dq_games >> merge_games >> mark_postponed >> log_games
fetch_box >> [box_archive, box_bulk] >> stage_box >> dq_box >> merge_box >> log_box
[log_games, log_box] >> trigger_dbt_finalize
```
- Runs at 3am ET (08:00 UTC) — after all games are Final (safety net)
- Also event-triggered by `nba_live_scoreboard` when a game goes Final
- Accepts `game_date` via `dag_run.conf` (event-triggered) or uses `ds - 1` (scheduled)
- `wait_for_events` checks events for game_date, loaded ~20h prior by events DAG
- Games and box scores fetch in parallel, each with stage → DQ → MERGE
- Games DQ cross-references events table for expected game count
- `mark_postponed` always runs after merge (compares events vs games, resets on re-run)
- Triggers `nba_dbt_finalize` after both branches complete

**`nba_dbt_daily`** — `check >> [wait_for_events, wait_for_odds] >> dbt_tasks >> post`
- Uses ExternalTaskSensor to wait for `nba_ingest_events` and `nba_ingest_odds`
- Cosmos DbtTaskGroup runs `stg_nba__events+`, `stg_nba__odds_open+`
- Excludes live models (`path:models/nba/live`)
- TestBehavior.AFTER_EACH enforces WAP quality gate

**`nba_dbt_finalize`** — `check >> dbt_tasks >> post`
- Triggered by `nba_finalize_games` or runs on schedule (3:02am safety net)
- Cosmos DbtTaskGroup runs `stg_nba__games+`, `stg_nba__player_box_scores+`, `stg_nba__teams+`
- Excludes events/odds models (those run in `nba_dbt_daily`) and live models
- Accepts `game_date` via `dag_run.conf` from trigger

**`nba_ingest_upcoming`** — `check >> ingest_upcoming_events >> ingest_upcoming_odds >> dbt_nba_upcoming >> post`
- Ingests events + odds for ds+1 through ds+7 (7-day lookahead)
- Events: FREE (regular /events endpoint for future dates)
- Odds: 3 credits/date, skips dates with no events (cost optimization)
- Each date processed sequentially through full cold-path pipeline (fetch → S3 → stage → DQ → MERGE → log)
- Preserves `single_date_only` DQ constraint by processing one date at a time
- try/except per date — one date failing doesn't block others
- Cosmos DbtTaskGroup rebuilds `stg_nba__events+`, `stg_nba__odds_open+` (same as `nba_dbt_daily`)
- **Daily line updates:** Re-MERGEs latest odds each day as bookmakers adjust lines
- **Game-day handoff:** Regular events/odds DAGs at 7am ET overwrite preview data with authoritative morning line
- Cost: ≤ 21 credits/day (3 credits × up to 7 dates with games)

**`nba_dbt_full_refresh`** — Manual trigger
- Runs `dbt run --full-refresh` for all NBA models
- Use when incremental models need rebuilding

## Live DAGs (Hot Path)

| DAG | Schedule | Source | Purpose |
|-----|----------|--------|---------|
| `nba_live_scoreboard` | Every 1 min | BallDontLie | Scores + box scores + plays → MERGE |
| `nba_live_odds` | Every 5 min | The Odds API | Odds → MERGE + archive snapshot |

### Hot Path Details

**`nba_live_scoreboard`** — `check_game_window >> ingest_scores >> cleanup_old_data`
- ShortCircuit: `is_game_window() AND is_nba_season(today)` — skips outside 11am-2am ET
- Single task: fetches games + box scores + plays, MERGEs all on one connection
- Plays only fetched for in-progress games (skip scheduled + Final)
- `get_live_game_dates()` includes yesterday before 5am ET (late west coast games)
- Cleanup runs at minute :00 only — removes data older than 2 days
- **Event-driven trigger:** Detects newly-Final games (pre vs post MERGE status comparison) and triggers `nba_finalize_games` via `trigger_dag()` API call. Non-fatal — 3am safety net catches misses.
- `is_paused_upon_creation=True` — create tables first, then unpause

**`nba_live_odds`** — `check_game_window >> ingest_odds`
- Same ShortCircuit as scoreboard
- Fetches all current odds → MERGE → snapshot to archive (non-fatal)
- Cost: 3 credits/call × 12 calls/hour × ~5 hours = ~180 credits/game day
- Completed games disappear from API but rows persist (MERGE never deletes)
- Archive is append-only (never cleaned) for line movement analysis

### Live Tables

| Table | Key | Source |
|-------|-----|--------|
| `live_nba_scoreboard` | `(game_id)` | BDL /games — all statuses |
| `live_nba_player_box_scores` | `(game_id, player_id)` | BDL /box_scores — live + final |
| `live_nba_plays` | `(game_id, play_id)` | BDL /plays — in-progress only, 2025+ |
| `live_nba_odds` | `(event_id, bookmaker_key, market_key, outcome_name)` | Odds API |
| `archive_nba_odds_snapshots` | (none — append-only) | Snapshot of live_nba_odds |
| `live_nba_team_box_scores` | VIEW | Aggregates player → team |

### Live Pre-Deploy Checklist

1. Run `include/capstone/scripts/create_live_tables.sql` manually in Snowflake
2. Verify: `SHOW TABLES LIKE 'live_%' IN SCHEMA ipgross;`
3. Verify VIEW: `SELECT * FROM ipgross.live_nba_team_box_scores LIMIT 5;`
4. Unpause DAGs in Airflow UI during game hours
5. Check freshness: `SELECT MAX(updated_at) FROM ipgross.live_nba_scoreboard;`

## Retired DAGs (Archived)

| DAG | Former ID | Reason |
|-----|-----------|--------|
| `nba_backfill_dag.py` | `nba_backfill_v2` | Manual backfill; no longer needed with full history loaded |
| `nba_teams_load_dag.py` | `nba_teams_load_v1` | Team reference data; one-time load complete |
| `nba_live_backfill_dag.py` | `nba_live_backfill_v1` | Live table backfill; superseded by cold path |

---

## NBA Season Reference

| Season | Start | End |
|--------|-------|-----|
| 2023-24 | 2023-10-24 | 2024-06-17 |
| 2024-25 | 2024-10-22 | 2025-06-22 |
| 2025-26 | 2025-10-21 | 2026-06-21 |

**Markets:** h2h (moneyline), spreads (point spread), totals (over/under)
**Regions:** us (US bookmakers)
**Bookmakers:** fanduel, draftkings, betmgm, caesars, pointsbetus, betrivers

---

## Git Workflow

```bash
git checkout capstone/nba-live-analytics
git add dags/capstone/ include/capstone/ archive/old_dags/ dbt_project/models/nba/ dbt_project/macros/nba/
git commit -m "feat: description"
git push origin capstone/nba-live-analytics
# Auto-deploys to Astronomer via GitHub workflow
```

**IMPORTANT:**
- Do NOT squash and merge PRs into the airflow-dbt-project repo
- Do NOT close your PR
- Keep PR open for the duration of the capstone project

---

## Pre-Deploy Checklist

Before deploying the new cold path DAGs, run these SQL scripts manually in Snowflake:

1. **Rename old tables:** `include/capstone/scripts/rename_old_tables.sql`
   ```sql
   ALTER TABLE ipgross.raw_nba_events RENAME TO ipgross.old_raw_nba_events;
   -- (5 tables total)
   ```

2. **Create new tables:** `include/capstone/scripts/create_hist_tables.sql`
   ```sql
   CREATE TABLE IF NOT EXISTS ipgross.hist_nba_events (...);
   -- (5 tables total)
   ```

3. **Verify:** `SHOW TABLES LIKE 'hist_%' IN SCHEMA ipgross;`

---

## Verification Commands

### Snowflake
```sql
-- Events (The Odds API)
SELECT * FROM ipgross.hist_nba_events WHERE ds = '2023-10-24';

-- Odds (The Odds API)
SELECT * FROM ipgross.hist_nba_odds_open WHERE ds = '2023-10-24' LIMIT 100;

-- Games (BallDontLie)
SELECT * FROM ipgross.hist_nba_games WHERE ds = '2023-10-24';

-- Box Scores (BallDontLie)
SELECT * FROM ipgross.hist_nba_player_box_scores WHERE ds = '2023-10-24' LIMIT 100;

-- Teams (BallDontLie)
SELECT * FROM ipgross.hist_nba_teams;

-- Spread Cover Analysis (join games + odds on ds + home_team)
-- Team names normalized at ingestion so direct equality works
SELECT
    g.game_date,
    g.home_team_name,
    g.visitor_team_name,
    g.home_team_score - g.visitor_team_score AS margin,
    o.outcome_point AS spread,
    CASE WHEN (g.home_team_score - g.visitor_team_score) > -o.outcome_point
         THEN 'COVERED' ELSE 'NOT COVERED' END AS home_cover
FROM ipgross.hist_nba_games g
JOIN ipgross.hist_nba_odds_open o
    ON g.ds = o.ds
    AND g.home_team_name = o.home_team
WHERE o.market_key = 'spreads'
    AND o.outcome_name = o.home_team
    AND o.bookmaker_key = 'fanduel';

-- Postponed check (manual)
SELECT e.ds,
    COUNT(DISTINCT e.event_id) as events,
    COUNT_IF(e.postponed = TRUE) as postponed,
    COUNT(DISTINCT g.game_id) as games
FROM ipgross.hist_nba_events e
LEFT JOIN ipgross.hist_nba_games g ON e.ds = g.ds
WHERE e.ds >= DATEADD('day', -7, CURRENT_DATE())
GROUP BY e.ds
ORDER BY e.ds;

-- Freshness check
SELECT 'events' as tbl, MAX(ingested_at) as last_ingest FROM ipgross.hist_nba_events
UNION ALL SELECT 'odds', MAX(ingested_at) FROM ipgross.hist_nba_odds_open
UNION ALL SELECT 'games', MAX(ingested_at) FROM ipgross.hist_nba_games
UNION ALL SELECT 'box_scores', MAX(ingested_at) FROM ipgross.hist_nba_player_box_scores;
```

### S3
```bash
# Archive (raw JSON.gz)
aws s3 ls s3://zachwilsonsorganization-522/ipgross/archive/events/
aws s3 ls s3://zachwilsonsorganization-522/ipgross/archive/odds_open/
aws s3 ls s3://zachwilsonsorganization-522/ipgross/archive/games/
aws s3 ls s3://zachwilsonsorganization-522/ipgross/archive/box_scores/

# Bulk (Parquet)
aws s3 ls s3://zachwilsonsorganization-522/ipgross/bulk/events/
aws s3 ls s3://zachwilsonsorganization-522/ipgross/bulk/odds_open/
aws s3 ls s3://zachwilsonsorganization-522/ipgross/bulk/games/
aws s3 ls s3://zachwilsonsorganization-522/ipgross/bulk/box_scores/
```
