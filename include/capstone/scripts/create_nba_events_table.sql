-- ===========================================
-- NBA Events Table DDL
-- Run this manually in Snowflake before first DAG run
-- ===========================================

-- Set context
USE ROLE ALL_USERS_ROLE;
USE DATABASE DATAEXPERT_STUDENT;
USE SCHEMA ipgross;
USE WAREHOUSE COMPUTE_WH;

-- ===========================================
-- Main events table
-- ===========================================
CREATE TABLE IF NOT EXISTS ipgross.raw_nba_events (
    -- Partition key (for idempotent DELETE)
    ds                  DATE NOT NULL,

    -- Event identifiers
    event_id            VARCHAR(64) NOT NULL,
    season              VARCHAR(10) NOT NULL,

    -- Game details
    sport_key           VARCHAR(50) NOT NULL,
    sport_title         VARCHAR(100),
    commence_time_utc   TIMESTAMP_NTZ NOT NULL,
    commence_time_et    TIMESTAMP_NTZ NOT NULL,
    home_team           VARCHAR(100) NOT NULL,
    away_team           VARCHAR(100) NOT NULL,

    -- Lineage
    s3_path             VARCHAR(500),
    ingested_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),

    -- Primary key for idempotency
    PRIMARY KEY (ds, event_id)
);

-- ===========================================
-- Daily summary view
-- ===========================================
CREATE OR REPLACE VIEW ipgross.v_nba_events_daily AS
SELECT
    ds,
    season,
    COUNT(*) as game_count,
    MIN(commence_time_et) as first_tip,
    MAX(commence_time_et) as last_tip,
    MAX(ingested_at) as last_ingested
FROM ipgross.raw_nba_events
GROUP BY ds, season
ORDER BY ds DESC;

-- ===========================================
-- Season summary view
-- ===========================================
CREATE OR REPLACE VIEW ipgross.v_nba_events_season_summary AS
SELECT
    season,
    COUNT(DISTINCT ds) AS days_with_games,
    COUNT(*) AS total_events,
    MIN(ds) AS first_game_date,
    MAX(ds) AS last_game_date
FROM ipgross.raw_nba_events
GROUP BY season
ORDER BY season;

-- ===========================================
-- Verification queries (run after DAG completes)
-- ===========================================
-- SELECT * FROM ipgross.raw_nba_events WHERE ds = '2023-10-24' ORDER BY commence_time_et;
-- SELECT * FROM ipgross.v_nba_events_daily LIMIT 10;
-- SELECT * FROM ipgross.v_nba_events_season_summary;
