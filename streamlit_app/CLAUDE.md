# CLAUDE.md — Streamlit NBA Live Analytics Dashboard

## Overview

Multi-page Streamlit app for NBA live analytics. Dark-themed, NBA.com-inspired game card design.
Pulls live data from Snowflake every 60s via `@st.fragment(run_every="60s")`.

**Run:** `cd streamlit_app && venv\Scripts\streamlit run app.py`
**Venv:** `streamlit_app\venv\` (Python, all deps installed)

---

## File Structure

```
streamlit_app/
├── .streamlit/
│   ├── config.toml            # Dark theme (base=dark, NBA blue primary)
│   └── secrets.toml           # Snowflake creds (git-ignored)
├── app.py                     # Multipage entrypoint (st.navigation + st.Page)
├── app_pages/
│   └── games.py               # Games page — LIVE/FINAL/UPCOMING sections
├── queries/
│   └── games.py               # SQL + cached fetch functions (Snowflake)
├── components/
│   └── game_card.py           # HTML card renderer per game
├── data/
│   └── teams.py               # Team name → abbreviation + ESPN logo URL
├── styles/
│   └── theme.py               # CSS injection for cards, sections, layout
└── requirements.txt           # streamlit>=1.36, snowflake-connector, plotly, pandas
```

**IMPORTANT:** Pages directory is `app_pages/` (NOT `pages/`). Using `pages/` conflicts with Streamlit's old auto-discovery API.

---

## Architecture Decisions

### Multipage
- Uses `st.navigation()` + `st.Page()` (modern Streamlit 1.36+ API)
- `app.py` is the entrypoint; each page is a separate file in `app_pages/`
- Future pages: predictions, odds, grades, matchups

### Data Layer (`queries/games.py`)
- **Scoreboard**: `ipgross.live_nba_scoreboard` — live scores, period, clock, game_datetime
  - Cached with `conn.query(sql, ttl=60)` (60s, matches Airflow DAG cadence)
- **Predictions**: `ipgross.mart_nba__game_predictions` — consensus lines, projected scores, EV, star ratings
  - Cached with `conn.query(sql, ttl=3600)` (1h, daily dbt rebuild)
  - Grain: one row per (event_id, market_key, side)
  - Pivoted in SQL: home_side + away_side per game
- **Join**: `game_date + home_team_name = home_team` (safe: NBA teams play max once/day at home)
- **Merge**: pandas `.merge()` with `how="left"` — games without predictions get NaN in odds columns

### Auto-Refresh
- Uses `@st.fragment(run_every="60s")` (built-in, no external dependency)
- The `games_board()` fragment wraps the game card rendering
- Market filter (`st.segmented_control`) is OUTSIDE the fragment — changing it triggers full rerun
- Cache TTLs: 60s for scoreboard, 3600s for predictions

### Game Categorization (Python, after fetch)
- **Live**: `period > 0 AND status != 'Final'`
- **Final**: `status = 'Final'`
- **Upcoming**: `period == 0 AND status != 'Final'`
- Render order: LIVE → UPCOMING → FINAL

### Snowflake Connection
- `st.connection("snowflake")` reads from `.streamlit/secrets.toml`
- Schema: `ipgross` in `DATAEXPERT_STUDENT` database
- All Snowflake column names are UPPERCASE in DataFrames (e.g., `df["STATUS"]`)

---

## Data Sources (Snowflake Tables)

### `ipgross.live_nba_scoreboard` (hot path, every 1 min)
Key columns: `GAME_ID, GAME_DATE, SEASON, STATUS, PERIOD, CLOCK, GAME_DATETIME,
HOME_TEAM_ID, HOME_TEAM_NAME, HOME_TEAM_SCORE, VISITOR_TEAM_ID, VISITOR_TEAM_NAME,
VISITOR_TEAM_SCORE, HOME_Q1-Q4, VISITOR_Q1-Q4, POSTSEASON, POSTPONED, UPDATED_AT`

- Status values from BallDontLie: "Final", "1st Qtr", "2nd Qtr", "Halftime", etc.
- Period: 0=not started, 1-4=quarters, 5+=OT
- Clock: time remaining in period (e.g., "4:28") — BUT may have "Q4 4:28" format with quarter prefix
- game_datetime: TIMESTAMP_NTZ of scheduled tip-off (stored as UTC from BDL)

### `ipgross.mart_nba__game_predictions` (cold path, daily dbt)
Key columns per row: `GAME_DATE, HOME_TEAM, AWAY_TEAM, MARKET_KEY, SIDE,
CONSENSUS_LINE, CONSENSUS_PRICE, PROJECTED_HOME_SCORE, PROJECTED_AWAY_SCORE,
PROJECTED_TOTAL, COVER_PROBABILITY, EXPECTED_VALUE, BET_RATING`

- market_key: 'spreads', 'h2h', 'totals'
- For spreads/h2h: side = team name (home or away)
- For totals: side = 'Over' or 'Under'
- consensus_price: American odds (e.g., -110, +150)
- consensus_line: spread or total number (NULL for h2h)
- bet_rating: 1-5 stars based on EV thresholds

### Pivoted Predictions Query
The SQL in `queries/games.py` pivots 2 rows per game per market into a single row:
- `HOME_CONSENSUS_LINE, HOME_CONSENSUS_PRICE, HOME_COVER_PROB, HOME_EV, HOME_BET_RATING`
- `AWAY_CONSENSUS_LINE, AWAY_CONSENSUS_PRICE, AWAY_COVER_PROB, AWAY_EV, AWAY_BET_RATING`
- `PROJECTED_HOME_SCORE, PROJECTED_AWAY_SCORE, PROJECTED_TOTAL`

For totals: HOME_ columns = Over side, AWAY_ columns = Under side.

---

## Game Card Component (`components/game_card.py`)

Each card shows:
- Away team row: logo (ESPN CDN), abbreviation, full name, score
- Home team row: same layout
- Status line: live=pulsing red dot + period/clock, final="FINAL", upcoming=tip-off time + countdown
- Odds line (based on market filter): spreads/h2h/totals
- Star rating (1-5) + projected score

### Known Issues / Fixes Needed

1. **NaN handling in `_fmt_price()` and `_fmt_spread()`**: LEFT JOIN produces NaN (not None) for games without predictions. Need `pd.isna()` or `math.isnan()` check before `int()` cast. This crashes the UPCOMING section.

2. **Live status redundancy**: BDL `status` = "4th Qtr", `clock` = "Q4 4:28". Current logic shows "4th Qtr Q4 4:28" — quarter stated twice. Fix: when status already has quarter info, strip the "Q4" prefix from clock and just show the time portion.

3. **Team logo URLs**: ESPN CDN `/nba/100/` path returns 404. Fix: use `/nba/500/` for all sizes and let CSS scale down (28px). The `/500/` path is verified working.

4. **Windows strftime**: `%-I` doesn't work on Windows. Already fixed to use `%I` with `.lstrip("0")`.

---

## Team Mapping (`data/teams.py`)

Maps BallDontLie `full_name` → (display abbreviation, ESPN CDN slug).

ESPN logo URL: `https://a.espncdn.com/i/teamlogos/nba/500/{slug}.png`
ESPN CDN slug quirks: GS (not GSW), NY (not NYK), SA (not SAS), NO (not NOP), WSH (not WAS)

All 30 NBA teams mapped. Team names are normalized at ingestion (e.g., "LA Clippers" not "Los Angeles Clippers").

---

## CSS Theme (`styles/theme.py`)

Injected via `st.html(inject_css())` at top of each page.

Key classes:
- `.game-card` / `.game-card.live` — card container with dark background, red left border for live
- `.team-row` / `.team-info` / `.team-abbrev` / `.team-score` — team row layout
- `.game-status` / `.game-status.live` — status line with optional pulsing dot
- `.odds-line` / `.odds-value` — betting line display
- `.star-rating` — 1-5 star bet rating
- `.section-header` / `.section-header.live` — LIVE/UPCOMING/FINAL headers
- `.page-header` / `.freshness` — top header with data staleness indicator

Color palette: BG_DARK=#0C0C0C, BG_CARD=#1A1A2E, ACCENT_LIVE=#C8102E (NBA red),
ACCENT_NBA=#1d428a (NBA blue), ODDS_ACCENT=#8EC5FC, STAR_COLOR=#F59E0B

---

## Config (`config.toml`)

```toml
[theme]
base = "dark"
primaryColor = "#1d428a"
backgroundColor = "#0C0C0C"
secondaryBackgroundColor = "#1A1A2E"
textColor = "#FFFFFF"
```

Font: Inter (Google Fonts). Border radius: 12px. No widget borders.

---

## Future Pages (Planned)

Per dbt exposures in `dbt_project/models/nba/_nba__exposures.yml`:
- **Predictions** — `mart_nba__game_predictions` (projected scores, consensus lines, star ratings)
- **Odds** — `live_nba__odds_current` + `live_nba__odds_movement` (per-bookmaker + line movement charts)
- **Game Detail** — `live_nba__game_detail` + box scores + plays (drill-down from game card)
- **ATS Records** — `mart_nba__team_ats_records` (team ATS/SU/O/U records with splits)
- **Matchup** — `mart_nba__team_matchup_stats` (head-to-head comparison)
- **Grades** — `mart_nba__game_grades` + `mart_nba__player_game_grades` (post-game grades A+ to F)

---

## Git

Branch: `capstone/nba-live-analytics`
Only modify files under `streamlit_app/`. The `.streamlit/secrets.toml` is git-ignored.
