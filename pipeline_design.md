# NBA Spread-Beating Analytics Pipeline
### Capstone Presentation — Pipeline Design & Architecture

---

## Slide 1: The Problem

**Can we beat the sportsbooks?**

NBA betting is a $10B+ market where sportsbooks set lines using proprietary models.
Most bettors rely on gut feel. What if we applied data engineering rigor instead?

**The Challenge:**
- Ingest betting odds from 6 bookmakers across 3 markets (spread, moneyline, over/under)
- Ingest game results, player stats, and play-by-play from a second API
- Transform raw data into actionable spread cover analysis — in near real-time
- Answer the question: which teams consistently beat the spread, and why?

**Two APIs. Different schemas. Different team names. One unified analytics layer.**

---

## Slide 2: What I Built

| Metric | Value |
|--------|-------|
| External APIs integrated | 2 (The Odds API + BallDontLie) |
| Airflow DAGs | 9 (7 cold path + 2 hot path) |
| dbt models | 35 (4-layer transformation) |
| dbt tests | 100+ (WAP quality gate) |
| Custom dbt macros | 5 (domain-specific calculations) |
| Snowflake tables | 17 (5 namespaces) |
| Python modules | 7 (config, API clients, storage, database, callbacks) |
| Live refresh rate | 1 minute (scores) / 5 minutes (odds) |
| Historical backfill | 2 full NBA seasons (2023-present) |
| Deployment | Astronomer (managed Airflow) |

**Stack:** Apache Airflow (Cosmos) | dbt | Snowflake | AWS S3 | Python | PyArrow

---

## Slide 3: Architecture Overview

```
                    ┌─────────────────────────────────────────────────────────┐
                    │               EXTERNAL DATA SOURCES                    │
                    │                                                         │
                    │   The Odds API              BallDontLie API             │
                    │   ├─ Events (game schedule)  ├─ Games (final scores)    │
                    │   ├─ Odds (6 books × 3 mkts) ├─ Box Scores (player)    │
                    │   └─ Scores (live)           ├─ Plays (play-by-play)   │
                    │                              └─ Teams (reference)      │
                    └────────────────────┬────────────────────────────────────┘
                                        │
                    ┌───────────────────▼───────────────────┐
                    │         APACHE AIRFLOW (9 DAGs)        │
                    │    Astronomer · Cosmos dbt integration  │
                    ├───────────────────┬───────────────────-─┤
                    │   COLD PATH       │     HOT PATH        │
                    │   Daily batch     │     Every 1-5 min   │
                    │   7 DAGs          │     2 DAGs          │
                    └───────┬───────────┴──────────┬──────────┘
                            │                      │
                    ┌───────▼───────┐      ┌───────▼───────┐
                    │    AWS S3      │      │  Direct MERGE  │
                    │  JSON.gz arch  │      │  FROM VALUES   │
                    │  Parquet bulk  │      │  (no S3 hop)   │
                    └───────┬───────┘      └───────┬───────┘
                            │                      │
                    ┌───────▼──────────────────────▼───────┐
                    │            SNOWFLAKE                   │
                    │                                         │
                    │   hist_nba_*    live_nba_*              │
                    │   stg_nba_*     archive_nba_*           │
                    │   ops_*         dbt models (35)         │
                    └───────────────────┬─────────────────────┘
                                        │
                    ┌───────────────────▼───────────────────┐
                    │        ANALYTICS DASHBOARD             │
                    │   Spread covers · Game grades ·         │
                    │   Predictions · Live scores             │
                    └────────────────────────────────────────┘
```

---

## Slide 4: The Hot/Cold Dual-Path Architecture

### Why Two Paths?

| | Cold Path (Batch) | Hot Path (Live) |
|--|---|---|
| **Priority** | Durability + data quality | Speed + freshness |
| **Schedule** | Daily (7am + 3am ET) | Every 1-5 minutes |
| **Storage** | S3 → Staging → DQ → MERGE | Direct MERGE FROM VALUES |
| **Latency** | Hours | Sub-minute |
| **Safety** | Full audit trail, replay from S3 | Cold path as safety net |
| **Tables** | `hist_nba_*` (system of record) | `live_nba_*` (serving layer) |

### The Convergence Pattern

When a live game goes **Final**, the hot path triggers the cold path:

```
Live Scoreboard (1 min)
  └─ detects newly-Final game (pre vs post MERGE status)
      └─ TriggerDagRunOperator → nba_finalize_games
          └─ S3 → Stage → DQ → MERGE hist_nba_*
              └─ TriggerDagRunOperator → nba_dbt_finalize
                  └─ dbt rebuilds all downstream models
```

**Result:** ~10-20 minutes from game Final to fully refreshed dbt models.
The hot path gives you instant results; the cold path gives you the official record.

---

## Slide 5: Cold Path — Ingestion Pipeline

### Stage → DQ → MERGE (Production-Standard Idempotency)

```
API Fetch ─┬─► JSON.gz archive → S3 (raw replay capability)
           │
           └─► Python normalize → PyArrow Parquet → S3 bulk
                                                      │
                                            COPY INTO stg_nba_* (FORCE=TRUE)
                                                      │
                                            DQ checks (raise on failure)
                                                      │
                                            MERGE INTO hist_nba_* (atomic upsert)
                                                      │
                                            DELETE stg_nba_* (cleanup)
                                                      │
                                            INSERT ops_ingestion_runs (metadata)
```

### Why This Pattern Matters

- **Staging tables** let us validate data before touching production
- **MERGE** is atomic — matched rows update, unmatched rows insert, one statement
- **FORCE=TRUE** bypasses Snowflake's 64-day load history (which caused silent data loss)
- **Re-running** the same date produces identical results (true idempotency)
- **Parquet over JSON** — embeds types, columnar reads, no casting errors

### Data Quality Checks (Per-Dataset)

```sql
-- Every dataset validates before MERGE
SELECT
    COUNT(*) > 0                           AS has_data,
    COUNT_IF(event_id IS NULL) = 0         AS event_id_not_null,
    COUNT(*) = COUNT(DISTINCT event_id)    AS no_duplicates,
    COUNT(DISTINCT ds) = 1                 AS single_date_only
FROM stg_nba_events WHERE ds = '{ds}'
```

Games DQ cross-references the events table for expected count:
```sql
COUNT(DISTINCT game_id) = (
    SELECT COUNT(DISTINCT event_id) FROM hist_nba_events
    WHERE ds = '{ds}' AND (postponed = FALSE OR postponed IS NULL)
) AS game_count_matches_events
```

Empty responses on off-days → `EMPTY_EXPECTED` (task succeeds, logged).
Missing games on game days → `EMPTY_UNEXPECTED` (task fails, Airflow retries).

---

## Slide 6: Hot Path — Sub-Minute Live Updates

### Direct API → MERGE FROM VALUES

No S3. No staging. No DQ. Speed is the priority.

```
BallDontLie API ──► Python validation ──► MERGE INTO live_nba_scoreboard
                                      ──► MERGE INTO live_nba_player_box_scores
                                      ──► MERGE INTO live_nba_plays (active games only)

The Odds API ────► Python validation ──► MERGE INTO live_nba_odds
                                      ──► INSERT INTO archive_nba_odds_snapshots
```

### Safety Guarantees

| Scenario | Behavior |
|----------|----------|
| Empty API response | 0 changes (table intact — MERGE never deletes) |
| Game ends | Status stays in API response (Final persists) |
| Odds disappear (game over) | Closing line preserved (MERGE only updates matches) |
| Stale data | Cleanup at minute :00 removes data > 2 days old |
| Hot path misses a game | Cold path catches it at 3am ET (safety net) |

### Game Window Gating

Hot path DAGs are ShortCircuited to only run during game hours:
- `is_game_window()`: 11am - 2am ET (covers pre-game through late west coast)
- `is_nba_season()`: October - June (skips offseason entirely)
- `get_live_game_dates()`: includes yesterday before 5am ET (late finishes)

---

## Slide 7: DAG Orchestration — 9 DAGs, 3 Coordination Patterns

### Coordination Mechanisms

| Pattern | Use Case | Example |
|---------|----------|---------|
| **ExternalTaskSensor** | Wait for upstream DAG | dbt_daily waits for events + odds |
| **TriggerDagRunOperator** | Fire downstream DAG | finalize_games triggers dbt_finalize |
| **ShortCircuitOperator** | Gate execution | All DAGs check `is_nba_season()` |

### DAG Schedule Matrix

| DAG | Schedule | Trigger | Path |
|-----|----------|---------|------|
| `nba_ingest_events` | 7am ET | schedule | Cold |
| `nba_ingest_odds` | 7am ET | schedule | Cold |
| `nba_ingest_upcoming` | 8am ET | schedule | Cold |
| `nba_finalize_games` | 3am ET | schedule + event | Cold |
| `nba_dbt_daily` | 7:02am ET | sensor wait | Cold |
| `nba_dbt_finalize` | 3:02am ET | trigger + schedule | Cold |
| `nba_dbt_full_refresh` | manual | manual | Cold |
| `nba_live_scoreboard` | every 1 min | schedule | Hot |
| `nba_live_odds` | every 5 min | schedule | Hot |

### Cross-DAG Event Flow

```
nba_live_scoreboard ──(game goes Final)──► nba_finalize_games
                                                    │
                                           ┌────────┴────────┐
                                           ▼                  ▼
                                      fetch_games       fetch_box_scores
                                           │                  │
                                      S3 → stage         S3 → stage
                                      DQ → merge         DQ → merge
                                           │                  │
                                           └────────┬─────────┘
                                                    ▼
                                           nba_dbt_finalize
                                           (WAP build all models)
```

---

## Slide 8: dbt Transformation — 4-Layer Architecture

### Model Inventory: 35 Models Across 4 Layers

| Layer | Models | Materialization | Purpose |
|-------|--------|-----------------|---------|
| **Staging** | 5 | views | Clean, rename, type-cast raw data |
| **Intermediate** | 5 + 5 audit | incremental (WAP) | Business logic: aggregation, rolling stats, betting results |
| **Marts** | 6 + 4 audit | incremental (WAP) / table | Consumer-ready analytics: game results, ATS records, predictions |
| **Live** | 10 | views | Real-time: scoreboard, odds, game grades |

### Key Transformations

**Player → Team Aggregation** (`int_nba__team_game_stats`)
- Aggregates individual box scores to team-level stats
- Computes Dean Oliver's Four Factors: eFG%, TOV%, ORB%, FTR
- Calculates offensive/defensive ratings (points per 100 possessions)
- Joins opponent stats for matchup analysis

**Consensus Lines** (`int_nba__consensus_lines`)
- Median price/line across 6 bookmakers per market
- Tracks best/worst price and line range for shopping value

**Rolling Stats** (`int_nba__team_rolling_stats`)
- L10 (last 10 games) and season-to-date averages
- Window frames exclude current game (pre-game expectations)
- 40+ statistical columns including Four Factors
- Powers predictions and post-game grading

**Game Predictions** (`mart_nba__game_predictions`)
- Composite cover probability from research-backed signals:
  - Projected edge vs spread (L10 rolling averages)
  - Dean Oliver's Four Factors matchup
  - Rest days advantage
  - Historical ATS track record
- Expected value calculation per bet
- 1-5 star bet rating based on EV thresholds

---

## Slide 9: The WAP Pattern — Write-Audit-Publish

### How It Works

Every incremental model has a paired **audit table** that acts as a quality gate:

```
1. WRITE:   dbt materializes batch into audit_* table (current day only)
2. AUDIT:   dbt tests validate audit table (100+ tests)
3. PUBLISH: Production incremental model reads from audit table
```

### Why WAP Over Standard Incremental?

| Standard Incremental | WAP Pattern |
|---------------------|-------------|
| Bad data goes straight to production | Bad data caught in audit table |
| Tests run after data is published | Tests run before publication |
| Rollback requires manual intervention | Production never sees bad data |
| One bad run corrupts downstream models | Failed audit = pipeline stops cleanly |

### Test Coverage by Layer

| Layer | Test Types | Examples |
|-------|-----------|----------|
| Staging | not_null, unique, accepted_values, relationships, between | `market_key IN ('h2h', 'spreads', 'totals')`, `score BETWEEN 50 AND 200` |
| Intermediate audit | unique_combination, between (advanced metrics) | `off_rating BETWEEN 60 AND 170`, `efg_pct BETWEEN 0.15 AND 0.85` |
| Marts audit | accepted_values (enum results), between (projections) | `spread_result IN ('COVERED', 'MISSED', 'PUSH')`, `grade IN ('A+'..'F')` |
| Live | unique, not_null, unique_combination, accepted_values | `market_key` validation, primary key enforcement |

### Airflow Integration (Cosmos)

```python
# TestBehavior.AFTER_EACH = WAP enforcement
# Each model's tests must pass before downstream models run
DbtTaskGroup(
    test_behavior=TestBehavior.AFTER_EACH,
    exclude=["path:models/nba/live"],  # Live views skip WAP
)
```

---

## Slide 10: Cross-API Data Integration

### The Problem: Two APIs, Different Schemas

| Field | The Odds API | BallDontLie |
|-------|-------------|-------------|
| Team name | "Los Angeles Clippers" | "LA Clippers" |
| Game ID | `"abc123def456"` (string) | `473028` (integer) |
| Date format | ISO8601 UTC | `YYYY-MM-DD` |
| Score data | None (odds only) | Final scores |
| Grain | event × bookmaker × market × outcome | game × player |

### Solution: Normalize at Ingestion, Join in dbt

**Step 1 — Team Name Normalization** (Python, at API ingestion):
```python
TEAM_NAME_MAP = {"Los Angeles Clippers": "LA Clippers"}

def normalize_team_name(name: str) -> str:
    return TEAM_NAME_MAP.get(name, name)
```

Applied to every API response before it touches S3 or Snowflake.
Raw JSON.gz archives preserve original names for replay.

**Step 2 — Natural Key Join** (dbt, in `int_nba__game_betting_results`):
```sql
-- Cross-API join via normalized team names
hist_nba_games JOIN hist_nba_odds_open
    ON games.ds = odds.ds
    AND games.home_team_name = odds.home_team
```

No fuzzy matching. No lookup tables. Simple equality because normalization happened upstream.

**Step 3 — UTC → Eastern Time** (Python, at ingestion):
```python
utc_dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
et_dt = utc_dt.astimezone(ZoneInfo("America/New_York"))
game_date_et = et_dt.strftime("%Y-%m-%d")
```

Evening ET games fall into the next UTC day — wide UTC windows prevent data loss.

---

## Slide 11: Custom dbt Macros — Domain-Specific Calculations

### 5 Reusable Macros for Sports Analytics

**1. `american_odds_to_implied_prob()`** — Convert American odds to probability
```sql
-- -150 → 60%, +200 → 33.3%
CASE WHEN odds < 0 THEN ABS(odds) / (ABS(odds) + 100.0)
     WHEN odds > 0 THEN 100.0 / (odds + 100.0) END
```

**2. `calculate_expected_value()`** — EV of a $1 bet
```sql
-- EV = (win_prob × payout) - (1 - win_prob)
-- Positive EV = favorable bet
```

**3. `performance_grade()`** — Letter grade from stat delta
```sql
-- Parameterized thresholds: A+ (≥15), A (≥8), B (≥3), C (≥-3), D (≥-8), F
-- Used for offensive, defensive, and overall game grades
```

**4. `parse_minutes()`** — Convert "MM:SS" string to decimal minutes

**5. `safe_divide()`** — Division with NULL protection (avoids divide-by-zero)

---

## Slide 12: Snowflake Schema Design

### 5 Table Namespaces, Clear Separation of Concerns

```
┌──────────────────────────────────────────────────────────────────┐
│                        SNOWFLAKE SCHEMA: ipgross                 │
│                                                                   │
│   ┌─────────────────┐   ┌─────────────────┐   ┌──────────────┐  │
│   │  hist_nba_*      │   │  live_nba_*      │   │  stg_nba_*   │  │
│   │  (Cold Production)│  │  (Hot Serving)   │   │  (Transient) │  │
│   │                   │   │                  │   │              │  │
│   │  events           │   │  scoreboard      │   │  Cleared per │  │
│   │  odds_open        │   │  player_box_scores│  │  date before │  │
│   │  games            │   │  plays           │   │  each load   │  │
│   │  player_box_scores│   │  odds            │   │              │  │
│   │  teams            │   │  team_box_scores  │  └──────────────┘  │
│   │                   │   │   (VIEW)          │                     │
│   └─────────────────┘   └─────────────────┘                     │
│                                                                   │
│   ┌─────────────────┐   ┌─────────────────┐                     │
│   │  archive_nba_*   │   │  ops_*           │                     │
│   │  (Append-Only)   │   │  (Metadata)      │                     │
│   │                   │   │                  │                     │
│   │  odds_snapshots   │   │  ingestion_runs  │                     │
│   │  (line movement)  │   │  (status, rows,  │                     │
│   │                   │   │   elapsed time)  │                     │
│   └─────────────────┘   └─────────────────┘                     │
└──────────────────────────────────────────────────────────────────┘
```

### Key Design Choices

| Choice | Why |
|--------|-----|
| `hist_*` + `live_*` separation | Different SLAs: daily accuracy vs sub-minute freshness |
| `stg_*` as TRANSIENT | No fail-safe = cheaper; disposable after MERGE |
| `archive_*` append-only | Odds snapshots for line movement charts; never deleted |
| `ops_*` metadata | Track ingestion status, row counts, and timing per run |
| Composite primary keys | `(ds, event_id)`, `(ds, game_id, player_id)` — date-partitioned for efficient MERGEs |

---

## Slide 13: Engineering Decisions & Trade-offs

### Decisions That Demonstrate Senior-Level Thinking

| Decision | Trade-off | Why I Chose This |
|----------|-----------|------------------|
| **Parquet over JSON** for bulk load | Slightly more complex Python (PyArrow schemas) | Eliminates casting errors, columnar reads are faster, industry standard |
| **Player-level box scores** (aggregate in dbt) | More rows in warehouse (~500/day vs ~60) | Faster ingestion (no Python agg), flexible for player analysis, SQL agg is testable in dbt |
| **MERGE FROM VALUES** for hot path | No S3 backup for live data | Sub-minute latency; cold path is the backup |
| **FORCE=TRUE on COPY INTO** | Bypasses Snowflake dedup optimization | Prevents silent data loss from 64-day load history bug |
| **WAP pattern** for incrementals | 2x the model count (audit + production) | Bad data never reaches production marts |
| **Team name normalization at ingestion** | Raw archives differ from warehouse | All downstream joins work with simple equality |
| **Event-driven finalize** (hot → cold trigger) | Added complexity in scoreboard DAG | ~10 min from game Final to dbt rebuild vs waiting for 3am |
| **Date-windowed UTC queries** with ET filtering | Slightly wider API calls | Never miss evening ET games that fall into next UTC day |

---

## Slide 14: Advanced Analytics — What the Pipeline Produces

### Spread Cover Analysis

For every completed NBA game, the pipeline determines:
- Did the home/away team **cover the spread**? (COVERED / MISSED / PUSH)
- Did the **over/under** hit?
- Did the **moneyline favorite** win?
- What was the **consensus line** across 6 bookmakers?

### Game Predictions (Pre-Game)

Composite model using research-backed signals:
- **Projected scores** from L10 rolling averages
- **Dean Oliver's Four Factors** matchup (eFG%, TOV%, ORB%, FTR)
- **Rest days** advantage
- **Historical ATS** track record
- **Expected value** per $1 bet → 1-5 star rating

### Performance Grading (Post-Game)

- **Team grades** (A+ through F): offensive rating, defensive rating, and combined
- **Player grades** using Hollinger's Game Score vs L10 baseline
- Delta analysis: which stats drove the cover or miss?

### Live Analytics (During Games)

- Live scoreboard with quarter-by-quarter scores
- Live odds with consensus across 6 bookmakers
- Live team box scores (aggregated from player stats)
- Odds movement tracking (append-only archive)
- Live game grades (cross-path join: hot scores + cold baselines)

---

## Slide 15: Cross-Path Join — Hot Meets Cold

### The Most Interesting Engineering Challenge

`live_nba__game_grades` joins data from **both paths simultaneously**:

```
HOT PATH (1-min refresh)              COLD PATH (daily refresh)
┌─────────────────────┐              ┌──────────────────────────┐
│ live_nba_scoreboard  │              │ int_nba__team_rolling_stats│
│ live_nba_player_box  │              │ (L10 + season averages)    │
│ (actual game stats)  │              │ (pre-game baselines)       │
└──────────┬──────────┘              └────────────┬─────────────┘
           │                                       │
           └──────────────┬────────────────────────┘
                          ▼
              live_nba__game_grades
              (actual vs baseline = letter grade)
```

**Trade-off acknowledged:** Baselines may lag by ~1 game (cold path runs at 3am ET).
Live grades appear instantly when a game ends. Official grades arrive overnight.

This pattern demonstrates understanding of **eventual consistency** in dual-path architectures.

---

## Slide 16: Operational Excellence

### Observability

| Feature | Implementation |
|---------|----------------|
| Ingestion metadata | `ops_ingestion_runs`: status, row counts, elapsed time per run |
| Failure alerting | `on_failure_callback=alert_on_failure` on all 9 DAGs |
| Empty day handling | `EMPTY_EXPECTED` vs `EMPTY_UNEXPECTED` classification |
| API usage tracking | Response headers logged: `x-requests-remaining`, `x-requests-used` |
| Structured logging | `key=value` format for every operation |

### Resilience

| Scenario | Handling |
|----------|----------|
| API rate limit (429) | Exponential backoff: 5s → 30s → 120s (3 retries built into both clients) |
| Off-season | `ShortCircuitOperator` skips all downstream tasks (zero API cost) |
| Game day with no games | DQ returns `EMPTY_EXPECTED`, task succeeds, logged to ops |
| Snowflake connection error | `try/finally` cleanup, Airflow retries (2x with 5-min delay) |
| Postponed game | `mark_postponed_events()` compares events vs games, sets flag |
| Hot path misses a game | 3am cold path is the safety net; catches everything |

### Cost Optimization

| Optimization | Savings |
|-------------|---------|
| FREE `/events` endpoint for current/future games | 0 credits vs 1 credit |
| Skip API calls on off-season days | ~150 days × 0 credits |
| `nba_ingest_upcoming` skips dates with no events | Up to 5 credits/day saved |
| Hot path only active during game window (11am-2am ET) | ~13 hours/day of zero API calls |
| Regular odds endpoint (3 credits) vs historical (30 credits) | 10x cheaper in steady state |

---

## Slide 17: Technology Choices & Why

| Technology | Why This Over Alternatives |
|-----------|---------------------------|
| **Airflow (Astronomer)** | Industry standard orchestrator; Cosmos integration for dbt; ExternalTaskSensors for cross-DAG coordination |
| **dbt (via Cosmos)** | SQL-first transformations with testing, lineage, and documentation; WAP pattern for data quality |
| **Snowflake** | MERGE for idempotent upserts; COPY INTO for bulk loads; transient tables for cost optimization |
| **AWS S3** | Durable archive (JSON.gz) + bulk staging (Parquet); replay capability for any historical date |
| **PyArrow** | Typed Parquet generation from Python dicts; schema enforcement before warehouse load |
| **Python** | API client logic, data validation, timezone handling; lightweight enough for Airflow tasks |

### Libraries & Packages

| Package | Purpose |
|---------|---------|
| `dbt-snowflake` | Snowflake adapter for dbt |
| `astronomer-cosmos` | dbt → Airflow task mapping with TestBehavior.AFTER_EACH |
| `dbt-utils` | `unique_combination_of_columns`, generic tests |
| `dbt-expectations` | `expect_column_values_to_be_between`, range validation |
| `pyarrow` | Typed Parquet file generation |
| `snowflake-connector-python` | Direct Snowflake operations (stage, DQ, MERGE) |
| `zoneinfo` | UTC → Eastern timezone conversion |

---

## Slide 18: What I'd Do Next

### Phase 3: ML-Powered Predictions

- Replace rule-based cover probability with a trained model
- Feature store from `int_nba__team_rolling_stats` (40+ features already computed)
- Backtest predictions against 2 seasons of historical data
- A/B test model vs consensus line

### Phase 4: Streaming Architecture

- Replace 1-minute polling with WebSocket connections
- Kafka for event streaming between ingestion and serving
- Sub-second latency for in-game betting signals

### Phase 5: Multi-Sport Expansion

- The Odds API supports 40+ sports with the same schema
- dbt models are parameterized — swap `basketball_nba` for `americanfootball_nfl`
- Same hot/cold architecture, different data sources

---

## Slide 19: Key Takeaways

### What This Project Demonstrates

1. **Production data engineering** — not a tutorial project
   - Hot/cold dual-path architecture with event-driven convergence
   - Stage → DQ → MERGE idempotent ingestion pattern
   - WAP quality gate preventing bad data from reaching production

2. **End-to-end ownership** — from API to analytics
   - 2 external APIs with different schemas normalized at ingestion
   - 35 dbt models with 100+ tests across 4 transformation layers
   - 9 DAGs coordinated via sensors, triggers, and short-circuits

3. **Thoughtful trade-offs** — not just making things work
   - Parquet over JSON for type safety
   - Player-level storage with SQL aggregation for flexibility
   - FORCE=TRUE to prevent a real Snowflake data loss bug
   - Cross-path joins with acknowledged eventual consistency

4. **Domain expertise applied to engineering**
   - Dean Oliver's Four Factors for basketball analytics
   - Hollinger's Game Score for player evaluation
   - American odds → implied probability → expected value pipeline
   - Consensus line calculation (median across bookmakers)

---

## Appendix A: dbt Model Lineage (Full)

### Sources → Staging → Intermediate → Marts → Live

```
SOURCES (5 Snowflake tables)
├── hist_nba_events ──────────► stg_nba__events
├── hist_nba_odds_open ───────► stg_nba__odds_open
├── hist_nba_games ───────────► stg_nba__games
├── hist_nba_player_box_scores► stg_nba__player_box_scores
└── hist_nba_teams ───────────► stg_nba__teams

INTERMEDIATE (5 models + 5 audit tables)
├── stg_box + stg_games ──────► int_nba__team_game_stats (Four Factors, ratings)
├── stg_odds ─────────────────► int_nba__consensus_lines (median across books)
├── stg_games + stg_events + consensus ► int_nba__game_betting_results (cover logic)
├── team_game_stats ──────────► int_nba__team_rolling_stats (L10 + season avgs)
└── stg_box ──────────────────► int_nba__player_rolling_stats (Game Score, L10)

MARTS (6 models + 4 audit tables)
├── game_betting_results + games ──────► mart_nba__game_results (wide-format)
├── game_betting_results + games ──────► mart_nba__team_ats_records (ATS W/L/P)
├── team_rolling_stats + teams ────────► mart_nba__team_matchup_stats (season avgs)
├── team_rolling_stats + game_results ─► mart_nba__game_grades (perf grades)
├── events + consensus + rolling + ATS ► mart_nba__game_predictions (cover prob, EV)
└── player_rolling_stats + game_results► mart_nba__player_game_grades (Hollinger)

LIVE (10 views over hot-path tables)
├── live_nba__scoreboard         (game status, quarter scores)
├── live_nba__player_box_scores  (player stats, live)
├── live_nba__team_box_scores    (aggregated player → team)
├── live_nba__plays              (play-by-play, 2025+)
├── live_nba__odds_current       (per-book + consensus)
├── live_nba__odds_movement      (snapshot history)
├── live_nba__game_detail        (combined scoreboard + box + spread)
├── live_nba__game_results       (instant results when game ends)
├── live_nba__game_grades        (CROSS-PATH: hot scores + cold baselines)
└── live_nba__player_game_grades (CROSS-PATH: hot stats + cold rolling)
```

---

## Appendix B: File Inventory

### Code Written for This Project

| Directory | Files | Purpose |
|-----------|-------|---------|
| `dags/capstone/` | 9 DAGs | Airflow orchestration (cold + hot path) |
| `include/capstone/` | 7 modules | Python utilities (API clients, storage, database, config) |
| `dbt_project/models/nba/staging/` | 5 models + 1 schema | Source staging layer |
| `dbt_project/models/nba/intermediate/` | 10 models + 2 schemas | Business logic + WAP audit |
| `dbt_project/models/nba/marts/` | 10 models + 2 schemas | Consumer analytics + WAP audit |
| `dbt_project/models/nba/live/` | 10 models + 1 schema | Real-time views |
| `dbt_project/models/nba/` | 2 configs | Sources + exposures |
| `dbt_project/macros/nba/` | 5 macros | Domain calculations |
| `include/capstone/scripts/` | 8 SQL scripts | DDL for Snowflake tables |

**Total: 9 DAGs + 35 dbt models + 5 macros + 7 Python modules + 8 SQL scripts**

---

*Built by Isaac Gross | Data Engineering Capstone | 2025*
