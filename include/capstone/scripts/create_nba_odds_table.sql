-- ===========================================
-- NBA Odds Table DDL
-- Run this manually in Snowflake before first DAG run
-- ===========================================

-- Set context
USE ROLE ALL_USERS_ROLE;
USE DATABASE DATAEXPERT_STUDENT;
USE SCHEMA ipgross;
USE WAREHOUSE COMPUTE_WH;

-- ===========================================
-- Main odds table (normalized - one row per outcome)
-- ===========================================
CREATE TABLE IF NOT EXISTS ipgross.raw_nba_odds (
    -- Partition key (for idempotent DELETE)
    ds                      DATE NOT NULL,

    -- Event identifiers
    event_id                VARCHAR(64) NOT NULL,
    season                  VARCHAR(10) NOT NULL,

    -- Game context (denormalized for query convenience)
    home_team               VARCHAR(100) NOT NULL,
    away_team               VARCHAR(100) NOT NULL,
    commence_time_utc       TIMESTAMP_NTZ NOT NULL,
    commence_time_et        TIMESTAMP_NTZ NOT NULL,

    -- Bookmaker
    bookmaker_key           VARCHAR(50) NOT NULL,
    bookmaker_title         VARCHAR(100),
    bookmaker_last_update   TIMESTAMP_NTZ,

    -- Market & Outcome
    market_key              VARCHAR(20) NOT NULL,   -- h2h, spreads, totals
    outcome_name            VARCHAR(100) NOT NULL,  -- Team name or Over/Under
    outcome_price           INTEGER NOT NULL,       -- American odds (-110, +150)
    outcome_point           FLOAT,                  -- NULL for h2h, line for spreads/totals

    -- Lineage
    s3_path                 VARCHAR(500),
    ingested_at             TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),

    -- Primary key for idempotency
    PRIMARY KEY (ds, event_id, bookmaker_key, market_key, outcome_name)
);

-- ===========================================
-- Daily summary view
-- ===========================================
CREATE OR REPLACE VIEW ipgross.v_nba_odds_daily AS
SELECT
    ds,
    season,
    COUNT(DISTINCT event_id) AS game_count,
    COUNT(DISTINCT bookmaker_key) AS bookmaker_count,
    COUNT(*) AS total_records,
    MAX(ingested_at) AS last_ingested
FROM ipgross.raw_nba_odds
GROUP BY ds, season
ORDER BY ds DESC;

-- ===========================================
-- Spread comparison view (home team perspective)
-- ===========================================
CREATE OR REPLACE VIEW ipgross.v_nba_spreads_comparison AS
SELECT
    ds,
    event_id,
    home_team,
    away_team,
    commence_time_et,
    bookmaker_key,
    outcome_point AS spread_line,
    outcome_price AS price,
    bookmaker_last_update
FROM ipgross.raw_nba_odds
WHERE market_key = 'spreads'
  AND outcome_name = home_team
ORDER BY ds, event_id, bookmaker_key;

-- ===========================================
-- Moneyline comparison view
-- ===========================================
CREATE OR REPLACE VIEW ipgross.v_nba_moneyline_comparison AS
SELECT
    ds,
    event_id,
    home_team,
    away_team,
    commence_time_et,
    bookmaker_key,
    MAX(CASE WHEN outcome_name = home_team THEN outcome_price END) AS home_ml,
    MAX(CASE WHEN outcome_name = away_team THEN outcome_price END) AS away_ml,
    bookmaker_last_update
FROM ipgross.raw_nba_odds
WHERE market_key = 'h2h'
GROUP BY ds, event_id, home_team, away_team, commence_time_et, bookmaker_key, bookmaker_last_update
ORDER BY ds, event_id, bookmaker_key;

-- ===========================================
-- Totals comparison view
-- ===========================================
CREATE OR REPLACE VIEW ipgross.v_nba_totals_comparison AS
SELECT
    ds,
    event_id,
    home_team,
    away_team,
    commence_time_et,
    bookmaker_key,
    MAX(CASE WHEN outcome_name = 'Over' THEN outcome_point END) AS total_line,
    MAX(CASE WHEN outcome_name = 'Over' THEN outcome_price END) AS over_price,
    MAX(CASE WHEN outcome_name = 'Under' THEN outcome_price END) AS under_price,
    bookmaker_last_update
FROM ipgross.raw_nba_odds
WHERE market_key = 'totals'
GROUP BY ds, event_id, home_team, away_team, commence_time_et, bookmaker_key, bookmaker_last_update
ORDER BY ds, event_id, bookmaker_key;

-- ===========================================
-- Season summary view
-- ===========================================
CREATE OR REPLACE VIEW ipgross.v_nba_odds_season_summary AS
SELECT
    season,
    COUNT(DISTINCT ds) AS days_with_odds,
    COUNT(DISTINCT event_id) AS total_events,
    COUNT(DISTINCT bookmaker_key) AS unique_bookmakers,
    COUNT(*) AS total_records,
    MIN(ds) AS first_date,
    MAX(ds) AS last_date
FROM ipgross.raw_nba_odds
GROUP BY season
ORDER BY season;

-- ===========================================
-- Verification queries (run after DAG completes)
-- ===========================================
-- SELECT * FROM ipgross.raw_nba_odds WHERE ds = '2023-10-24' LIMIT 100;
-- SELECT * FROM ipgross.v_nba_odds_daily LIMIT 10;
-- SELECT * FROM ipgross.v_nba_spreads_comparison WHERE ds = '2023-10-24';
-- SELECT * FROM ipgross.v_nba_moneyline_comparison WHERE ds = '2023-10-24';
-- SELECT * FROM ipgross.v_nba_totals_comparison WHERE ds = '2023-10-24';
-- SELECT * FROM ipgross.v_nba_odds_season_summary;
