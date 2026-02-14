# NBA Spread-Beating Analytics Platform
## Capstone Project Proposal

---

## 1. Project Description & Scope

### Problem Statement

Sports bettors lack access to comprehensive analytics that explain **why teams cover (or don't cover) the spread**. Most tools focus on final game outcomes, but fail to provide:

- Historical spread cover patterns by team and matchup
- Team performance trends that correlate with spread coverage
- Post-game analysis explaining cover/non-cover results using statistical outliers
- Expected value calculations based on cover probability and payout

### Proposed Solution

Build an **end-to-end spread-beating analytics platform** that:

1. **Ingests** historical and live betting odds, game results, and player box scores
2. **Transforms** raw data into analytics-ready models using dbt
3. **Analyzes** spread cover patterns, team performance trends, and matchup history
4. **Visualizes** insights through an interactive dashboard with:
   - Pre-game predictions (cover probability, expected value)
   - Live game tracking during game hours
   - Post-game analysis explaining why a team did/didn't cover

### Scope

| In Scope | Out of Scope |
|----------|--------------|
| Historical odds backfill (2+ NBA seasons) | Play-by-play analytics |
| Game results ingestion (final scores) | Real-time WebSocket streaming |
| Player box scores (aggregated to team) | Injury/lineup data |
| Spread cover analysis & predictions | Player-level betting analysis |
| Live game result tracking (30-min intervals) | Prop bet analysis |
| User bet input & tracking | Automated betting integration |
| Interactive analytics dashboard | Mobile application |

### Stretch Goals

- **Live Score Tracking**: Display all NBA games as they happen with score updates every 30 minutes during game hours
- **User Bet Input**: Allow users to log their bets and see post-game analysis explaining why they won/lost

---

## 2. Conceptual Data Model & Diagram

### Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              RAW LAYER (Sources)                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────────────┐   │
│  │  raw_nba_events  │    │   raw_nba_odds   │    │ raw_nba_player_box_scores│   │
│  ├──────────────────┤    ├──────────────────┤    ├──────────────────────────┤   │
│  │ event_id (PK)    │    │ event_id (FK)    │    │ game_id (PK)             │   │
│  │ ds               │    │ ds               │    │ player_id (PK)           │   │
│  │ commence_time    │    │ bookmaker_key    │    │ team_id                  │   │
│  │ home_team        │    │ market_key       │    │ pts, reb, ast, etc.      │   │
│  │ away_team        │    │ outcome_name     │    │ fg_pct, fg3_pct, ft_pct  │   │
│  │ season           │    │ outcome_price    │    │ is_home                  │   │
│  └────────┬─────────┘    │ outcome_point    │    └────────────┬─────────────┘   │
│           │              └────────┬─────────┘                 │                 │
│           │                       │                           │                 │
│  ┌────────┴─────────┐    ┌────────┴─────────┐    ┌────────────┴─────────────┐   │
│  │  raw_nba_games   │    │  raw_nba_teams   │    │    (aggregated in dbt)   │   │
│  ├──────────────────┤    ├──────────────────┤    └──────────────────────────┘   │
│  │ game_id (PK)     │    │ team_id (PK)     │                                   │
│  │ ds               │    │ full_name        │                                   │
│  │ home_team_score  │    │ abbreviation     │                                   │
│  │ visitor_team_score│   │ conference       │                                   │
│  │ status           │    │ division         │                                   │
│  └──────────────────┘    └──────────────────┘                                   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           STAGING LAYER (dbt)                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌────────────────────────┐    ┌────────────────────────┐                       │
│  │   stg_nba_games        │    │  stg_nba_team_stats    │                       │
│  ├────────────────────────┤    ├────────────────────────┤                       │
│  │ game_id                │    │ game_id                │                       │
│  │ game_date              │    │ team_id                │                       │
│  │ home_team_id           │    │ pts, reb, ast, etc.    │                       │
│  │ away_team_id           │    │ fg_pct, fg3_pct        │                       │
│  │ home_score             │    │ possessions            │                       │
│  │ away_score             │    │ off_rating             │                       │
│  │ margin                 │    │ is_home                │                       │
│  └────────────────────────┘    └────────────────────────┘                       │
│                                                                                 │
│  ┌────────────────────────┐    ┌────────────────────────┐                       │
│  │   stg_nba_odds         │    │   stg_nba_spreads      │                       │
│  ├────────────────────────┤    ├────────────────────────┤                       │
│  │ game_id                │    │ game_id                │                       │
│  │ bookmaker              │    │ home_spread            │                       │
│  │ market (h2h/spread/ou) │    │ away_spread            │                       │
│  │ home_odds              │    │ total                  │                       │
│  │ away_odds              │    │ bookmaker              │                       │
│  │ spread / total         │    │ consensus_spread       │                       │
│  └────────────────────────┘    └────────────────────────┘                       │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            MARTS LAYER (dbt)                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                        fct_game_spread_results                          │    │
│  ├─────────────────────────────────────────────────────────────────────────┤    │
│  │ game_id, game_date, season                                              │    │
│  │ home_team_id, away_team_id                                              │    │
│  │ home_score, away_score, margin                                          │    │
│  │ spread, total                                                           │    │
│  │ home_covered (BOOLEAN), away_covered (BOOLEAN)                          │    │
│  │ over_hit (BOOLEAN)                                                      │    │
│  │ home_ats_result (+1 / -1 / 0 for push)                                  │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                        fct_team_rolling_stats                           │    │
│  ├─────────────────────────────────────────────────────────────────────────┤    │
│  │ team_id, game_date                                                      │    │
│  │ pts_avg_10, reb_avg_10, ast_avg_10 (10-game rolling averages)           │    │
│  │ off_rating_avg_10, def_rating_avg_10                                    │    │
│  │ ats_record_last_10, ats_record_season                                   │    │
│  │ cover_rate_last_10, cover_rate_season                                   │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                        dim_teams                                        │    │
│  ├─────────────────────────────────────────────────────────────────────────┤    │
│  │ team_id, full_name, abbreviation, city                                  │    │
│  │ conference, division                                                    │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                     fct_matchup_history (future)                        │    │
│  ├─────────────────────────────────────────────────────────────────────────┤    │
│  │ team_id, opponent_id                                                    │    │
│  │ games_played, wins, losses                                              │    │
│  │ ats_wins, ats_losses, ats_pushes                                        │    │
│  │ avg_margin, avg_spread, cover_rate                                      │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Data Dictionary

| Table | Column | Type | Description |
|-------|--------|------|-------------|
| **fct_game_spread_results** | game_id | INTEGER | Unique game identifier |
| | home_covered | BOOLEAN | True if home team covered the spread |
| | margin | INTEGER | home_score - away_score |
| | spread | FLOAT | Point spread (negative = home favored) |
| | home_ats_result | INTEGER | +1 (cover), -1 (loss), 0 (push) |
| **fct_team_rolling_stats** | cover_rate_last_10 | FLOAT | % of last 10 games team covered |
| | off_rating_avg_10 | FLOAT | Points per 100 possessions (10-game avg) |
| | ats_record_season | VARCHAR | e.g., "25-18-2" (W-L-P) |
| **dim_teams** | conference | VARCHAR | "East" or "West" |
| | division | VARCHAR | e.g., "Atlantic", "Pacific" |

---

## 3. Tools, Data Sources & Formats

### Data Sources

| Source | Data Type | Format | Volume | Update Frequency |
|--------|-----------|--------|--------|------------------|
| **The Odds API** | Betting odds | JSON (REST) | ~600 rows/day | Daily + Live |
| **The Odds API** | Game events | JSON (REST) | ~15 rows/day | Daily |
| **BallDontLie API** | Game results | JSON (REST) | ~15 rows/day | Daily + Live (30min) |
| **BallDontLie API** | Box scores | JSON (REST) | ~300 rows/day | Daily + Live (30min) |
| **BallDontLie API** | Teams | JSON (REST) | 30 rows | One-time |

### Volume Calculation (>1M Rows)

```
Odds Data (per season):
- 82 games/team × 30 teams ÷ 2 = 1,230 games/season
- 1,230 games × 6 bookmakers × 3 markets × 2 outcomes = 44,280 rows/season
- 2 completed seasons = 88,560 rows

Box Score Data (per season):
- 1,230 games × ~25 players/game = 30,750 rows/season
- 2 completed seasons = 61,500 rows

With snapshot sampling (8 snapshots/game for odds):
- 88,560 × 8 = 708,480 odds snapshots
- Plus games + events + teams = **>1,000,000 total rows**
```

### Tech Stack

| Layer | Tool | Purpose |
|-------|------|---------|
| **Orchestration** | Apache Airflow (Astronomer) | DAG scheduling, backfill, retries |
| **Storage** | AWS S3 | Append-only raw JSON archive |
| **Catalog** | AWS Glue | Schema discovery, metadata management |
| **Warehouse** | Snowflake | Analytical queries, dbt transformations |
| **Transform** | dbt | Data modeling, testing, documentation |
| **Visualization** | Power BI / Streamlit | Interactive dashboards |
| **Version Control** | GitHub | Code versioning, CI/CD |

### Why This Stack?

| Choice | Justification |
|--------|---------------|
| **Airflow** | Industry-standard orchestrator; handles rate limiting, retries, catchup |
| **S3** | Cheap, durable, append-only storage for raw JSON audit trail |
| **Snowflake** | Scales for analytical workloads; native JSON support; dbt integration |
| **dbt** | SQL-based transforms are testable, version-controlled, documented |
| **Power BI** | Widely used in enterprises; rich visualizations; scheduled refresh |

---

## 4. Ingestion Strategy & Data Quality Checks

### Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DAILY PIPELINES                                    │
│                          (10am EST, Historical + Catchup)                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐       │
│   │ Check   │───▶│ Fetch   │───▶│ Upload  │───▶│ Load to │───▶│ dbt     │       │
│   │ Season  │    │ API     │    │ to S3   │    │Snowflake│    │Transform│       │
│   └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘       │
│       │                                                                         │
│       ▼                                                                         │
│   Off-season? → Skip                                                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              LIVE PIPELINES                                     │
│                    (Every 30min, 7pm-2am EST during games)                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐                      │
│   │ Check   │───▶│ Fetch   │───▶│ Filter  │───▶│ Upsert  │                      │
│   │ Is Game │    │ Games   │    │ Final   │    │Snowflake│                      │
│   │ Hours   │    │ Today   │    │ Only    │    │         │                      │
│   └─────────┘    └─────────┘    └─────────┘    └─────────┘                      │
│       │                                                                         │
│       ▼                                                                         │
│   Not game hours? → Skip                                                        │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### DAG Inventory

| DAG | Schedule | Purpose | Catchup |
|-----|----------|---------|---------|
| `nba_events_daily` | 10am EST | Game schedule ingestion | Yes |
| `nba_odds_daily` | 10am EST | Betting odds ingestion | Yes |
| `nba_games_daily` | 10am EST | Game results (backfill) | Yes |
| `nba_box_scores_daily` | 10am EST | Player stats (backfill) | Yes |
| `nba_games_live` | */30 19-2 EST | Live game results | No |
| `nba_box_scores_live` | */30 19-2 EST | Live box scores | No |
| `nba_teams` | Manual | Team reference data | No |
| `nba_dbt_transform` | After loads | dbt model runs | No |

### Idempotency Pattern

All pipelines use **DELETE + INSERT** to ensure reruns produce identical results:

```sql
-- Step 1: Delete existing rows for this date
DELETE FROM raw_nba_odds WHERE ds = '2024-01-15';

-- Step 2: Insert fresh data
INSERT INTO raw_nba_odds (ds, event_id, ...) VALUES (...);
```

### Data Quality Checks

| Layer | Check Type | Implementation |
|-------|------------|----------------|
| **Source** | API response validation | Python assertions (status codes, JSON schema) |
| **Raw** | Not null constraints | dbt tests: `not_null` on primary keys |
| **Raw** | Unique constraints | dbt tests: `unique` on composite keys |
| **Raw** | Referential integrity | dbt tests: `relationships` between tables |
| **Staging** | Value ranges | dbt tests: `accepted_values` for status, markets |
| **Staging** | Numeric bounds | dbt tests: custom tests for valid score ranges |
| **Marts** | Derived logic | dbt tests: cover calculation consistency |

### Sample dbt Tests

```yaml
# models/nba/staging/stg_nba_games.yml
version: 2
models:
  - name: stg_nba_games
    columns:
      - name: game_id
        tests:
          - not_null
          - unique
      - name: status
        tests:
          - accepted_values:
              values: ['Final', 'In Progress', 'Scheduled']
      - name: home_score
        tests:
          - dbt_utils.expression_is_true:
              expression: ">= 0 AND <= 200"
```

### Freshness Checks

```yaml
# models/nba/sources.yml
sources:
  - name: raw
    freshness:
      warn_after: {count: 24, period: hour}
      error_after: {count: 48, period: hour}
    tables:
      - name: raw_nba_games
      - name: raw_nba_odds
```

---

## 5. Success Metrics & Stakeholder Value

### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Data Volume** | >1,000,000 raw rows | `SELECT COUNT(*) FROM all_raw_tables` |
| **Pipeline Reliability** | >95% success rate | Airflow task success % |
| **Data Freshness** | <24 hours for daily, <1 hour for live | dbt freshness checks |
| **Data Quality** | 100% dbt test pass rate | dbt test results |
| **Query Performance** | <5 seconds for dashboard queries | Snowflake query history |
| **Model Coverage** | 100% of raw tables transformed | dbt docs coverage |

### Stakeholder Value

#### For Sports Bettors
| Value | Description |
|-------|-------------|
| **Informed Decisions** | See cover probability and expected value before placing bets |
| **Post-Game Analysis** | Understand why a team didn't cover (stat outliers vs averages) |
| **Historical Patterns** | Access team ATS records by opponent, home/away, conference |
| **Live Tracking** | Monitor games in progress during live hours |

#### For Data Engineers (Portfolio)
| Value | Description |
|-------|-------------|
| **Production Pipeline** | Demonstrates Airflow, dbt, Snowflake proficiency |
| **Multiple Data Sources** | Shows ability to integrate 2+ APIs with different schemas |
| **Data Quality** | Showcases testing strategy and idempotency patterns |
| **Documentation** | Well-documented code, data dictionary, ERD |

### Dashboard Deliverables

1. **Pre-Game View**
   - Today's games with spreads and totals
   - Cover probability based on rolling stats
   - Expected value calculation
   - Matchup history (ATS record head-to-head)

2. **Live Game View** (Stretch Goal)
   - Games in progress with current scores
   - Time remaining / quarter
   - Live cover status (currently covering spread?)

3. **Post-Game Analysis**
   - Game result with spread cover outcome
   - Stat comparison (actual vs 10-game rolling average)
   - Key stat outliers that explain cover/non-cover

4. **User Bet Tracker** (Stretch Goal)
   - Input bets with team, spread, stake
   - Post-game P&L calculation
   - Historical bet performance

---

## 6. Project Timeline

| Phase | Milestone | Status |
|-------|-----------|--------|
| **Phase 1** | Historical data ingestion (events, odds) | ✅ Complete |
| **Phase 2** | Game results + box scores ingestion | ✅ Complete |
| **Phase 3** | Live DAGs (games, box scores) | ✅ Complete |
| **Phase 4** | dbt transformations + testing | 🔄 In Progress |
| **Phase 5** | Dashboard MVP (pre-game + post-game) | ⏳ Planned |
| **Phase 6** | Live game tracking (stretch) | ⏳ Stretch |
| **Phase 7** | User bet tracker (stretch) | ⏳ Stretch |

---

## 7. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| API rate limits | Pipeline failures | Implement retry logic with exponential backoff |
| API quota exhaustion | No new data | Monitor usage; cache historical data |
| Schema changes | Pipeline breaks | Version raw JSON; decouple storage from parsing |
| Snowflake costs | Budget overrun | Use transient tables; warehouse auto-suspend |
| Off-season gaps | Stale dashboard | Display "off-season" messaging; historical analysis |

---

## Appendix: Sample Queries

### Spread Cover Analysis
```sql
SELECT
    t.full_name,
    COUNT(*) AS games,
    SUM(CASE WHEN f.home_covered THEN 1 ELSE 0 END) AS covers,
    ROUND(100.0 * SUM(CASE WHEN f.home_covered THEN 1 ELSE 0 END) / COUNT(*), 1) AS cover_pct
FROM fct_game_spread_results f
JOIN dim_teams t ON f.home_team_id = t.team_id
WHERE f.season = '2024-25'
GROUP BY t.full_name
ORDER BY cover_pct DESC;
```

### Rolling Performance vs Spread Cover
```sql
SELECT
    f.game_date,
    t.full_name,
    r.off_rating_avg_10,
    r.def_rating_avg_10,
    f.spread,
    f.home_covered,
    f.margin
FROM fct_game_spread_results f
JOIN dim_teams t ON f.home_team_id = t.team_id
JOIN fct_team_rolling_stats r ON f.home_team_id = r.team_id AND f.game_date = r.game_date
WHERE f.season = '2024-25'
ORDER BY f.game_date DESC
LIMIT 100;
```


Zach Wilson's Feedback
Hi! This is a strong, well-structured proposal that clearly states the bettor pain point, articulates scope, and connects it to a credible end-to-end data stack. You’ve done a great job laying out entities, DAGs, dbt layers, data quality strategy, and success metrics. This reads like a production-ready plan and would make an excellent portfolio project.

What’s working especially well

Clear problem-solution fit: pre-game, live, and post-game analytics tied to ATS outcomes and EV.
Sensible scoping: ambitious but realistic, with thoughtful stretch goals.
Thoughtful architecture: Airflow + S3 + Snowflake + dbt with testing, freshness, idempotency.
ERD and marts: fct_game_spread_results and rolling team stats are the right foundation.
DQ approach: constraints, relationships, accepted values, freshness SLAs.
Key clarifications and improvements to tighten the plan

Definitions that drive correctness
Spread sign convention: You state “negative = home favored.” Make this a contract and test it. Add dbt tests ensuring home_spread = -away_spread and that the chosen spread is the closing consensus.
Cover logic: Document the exact formula you’ll use. For home favorite, a common definition:
margin = home_score - away_score
home_covered = (margin + home_spread) > 0
push when (margin + home_spread) = 0 Add tests to guarantee pushes are handled consistently and that only one side can cover.
Which line is used: Be explicit: “We use the consensus closing spread, defined as the median across bookmakers at the last odds snapshot before tip.” Document tie-breaking and outlier handling.
EV math and odds: Specify American odds conversion and vigorish handling. Recommended:
Convert American odds to implied probability, remove vig across both sides, then use your model p to compute EV: EV = p * payout - (1 - p) where payout uses decimal odds
Track and report break-even probability and CLV (closing line value) as core metrics.
Data integration edges
Event ID vs game ID: Odds API event_id won’t match BallDontLie game_id. You’ll need a deterministic mapping table (dim_event_game_xwalk) keyed on date, home, away, and tipoff time with fuzzy safeguards. Add a uniqueness test here.
Timezones and seasonality: Normalize all source times to UTC, store local tipoff, and define season boundaries (e.g., 2024-25) deterministically. DST will affect “game hours” scheduling—handle conversion in Airflow.
Market keys: The Odds API uses 'h2h', 'spreads', 'totals' (not 'ou'). Update accepted_values and staging logic.
Status values: BallDontLie can return values beyond just “Final”, “In Progress”, “Scheduled” (e.g., “Postponed”). Expand accepted_values or add a soft-fail pattern.
Snapshotting and “closing” logic
Snapshots: 8 snapshots/game is good, but define the unique key for odds rows: event_id + bookmaker + market + outcome_name + snapshot_ts. Consider Type 2 logic with valid_from/valid_to to retrieve the final pre-tip (closing) price.
Idempotency: DELETE by ds is risky for high-frequency odds. Prefer MERGE using the unique key + snapshot_ts. Partition large deletes by event or window.
Consensus: Define consensus_close_spread per game as of just before commence_time. Store both per-bookmaker closing line and consensus; you’ll need both for analysis and CLV.
dbt modeling and tests
Rolling windows: Ensure no leakage. In SQL, use rows between 10 preceding and 1 preceding, and a strict predicate game_datetime < tipoff_datetime for pre-game features. Add a test that current game is excluded from rolling aggregates.
ATS record column: Storing "25-18-2" as a string is presentation-oriented. Store ats_wins, ats_losses, ats_pushes as integers; derive display strings in the dashboard.
Score bounds: Individual team scores rarely exceed 200, but keep a safe upper bound (e.g., <= 200) and add a soft alert for anomalies rather than a hard fail.
Additional tests to add:
home_spread = -away_spread
totals > 0 and reasonable upper bounds
Only one of home_covered/away_covered true unless push
Relationships: fct rows must map to dim_teams and crosswalk table.
Orchestration details
Cron and timezone: “/30 19-2 EST” isn’t a full cron expression and won’t reflect DST. In UTC, that’s roughly 00-07. Use an explicit UTC schedule like “/30 0-7 * * *” and document DST implications, or implement a timetable that checks “is game hours” dynamically based on schedule.
Rate limits: Implement central backoff/jitter and per-API concurrency caps. Cache static and historical data to preserve quotas.
Secrets: Store API keys in Airflow connections/variables or a secrets manager; don’t commit to Git.
Analytics and evaluation
Modeling approach: Even if you keep it SQL-first, outline a baseline logistic model for cover probability using rolling ratings, home/away, back-to-back, rest days, pace, simple matchup deltas. Time-split backtest (train on prior seasons, test on most recent).
Metrics to report: Brier score, calibration curve, AUC, ROI vs baseline (e.g., picking every favorite or implied probs), and CLV distribution. Calibration is essential if you’re computing EV.
Feature leakage: For pre-game predictions, ensure box score aggregates only include games strictly before the current tipoff. Exclude any in-game stats from predictions.
Dashboard UX considerations
Live view: Power BI is not ideal for near real-time. If you need 30-minute refresh reliably, Streamlit or a lightweight web app may be better. If you keep Power BI, consider DirectQuery and note the trade-offs.
Explanations: For post-game explanations, highlight stat deviations from 10-game rolling averages and relative importance (e.g., via simple SHAP from a tree model or rule-based deltas). Keep explanations readable and consistent.
Ops, cost, and governance
Snowflake costs: Use auto-suspend, small warehouses, task scheduling windows, and consider clustering keys on game_date to speed dashboard queries.
S3 hygiene: Enable lifecycle policies, SSE encryption, and a partitioning scheme (ds=YYYY-MM-DD) for raw.
Documentation: Use dbt docs and exposures to document lineage from raw to BI.
Potential mistakes or mismatches to fix

Market key values: Use 'h2h', 'spreads', 'totals' instead of 'ou'.
Cron format/timezone: Provide complete cron expressions in UTC and note DST handling.
Event-to-game mapping: Add a plan for crosswalking IDs.
Consensus closing definition: Specify precisely how and when you compute it.
EV and odds conversion: Document American-to-decimal conversion, vig removal, and EV formula.
Avoid string storage for ats_record; store numeric components.
Questions and information you can provide to remedy gaps

How will you compute the consensus closing spread and at what exact cutoff relative to tipoff?
What’s your event_id to game_id crosswalk logic? Provide the schema and matching rules.
Confirm your market keys and sample raw payloads for odds, games, and box scores.
Provide the exact SQL for home_covered/away_covered and push determination.
Show your rolling-window SQL ensuring exclusion of the current game and no leakage.
Specify your Airflow cron expressions in UTC and the plan for DST/game-hours logic.
Share the odds snapshot unique key and MERGE statement for idempotent loads.
Clarify the initial modeling approach and the backtest protocol and metrics you’ll report.
Suggested next steps (actionable)

Finalize spread/cover/EV definitions and add dbt tests for sign and push logic.
Implement the odds snapshot table with valid_from/valid_to and a consensus closing model.
Build the event-game crosswalk with strong constraints and tests.
Lock in UTC scheduling and add a “is_game_hours” task that reads the day’s schedule.
Add baseline model and backtest; report calibration, Brier, and CLV.
Start with Streamlit for live and post-game views; consider Power BI for historical analysis.
Overall, this is an excellent proposal with a few definitional and integration details to button up. Addressing these will make your platform credible to both bettors and engineers reviewing your portfolio.