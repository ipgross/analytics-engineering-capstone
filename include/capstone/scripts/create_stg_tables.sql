-- ================================================
-- Staging (Transient) Tables DDL
-- Run this AFTER create_hist_tables.sql
-- These are TRANSIENT: no fail-safe, cheaper storage.
-- Staging data is temporary — loaded, checked, merged, then deleted.
-- ================================================

USE ROLE ALL_USERS_ROLE;
USE DATABASE DATAEXPERT_STUDENT;
USE SCHEMA ipgross;
USE WAREHOUSE COMPUTE_WH;

-- ================================================
-- stg_nba_events
-- Identical schema to hist_nba_events
-- ================================================
CREATE TRANSIENT TABLE IF NOT EXISTS ipgross.stg_nba_events (
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
    ingested_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- ================================================
-- stg_nba_odds_open
-- Identical schema to hist_nba_odds_open
-- ================================================
CREATE TRANSIENT TABLE IF NOT EXISTS ipgross.stg_nba_odds_open (
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
    ingested_at             TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- ================================================
-- stg_nba_games
-- Identical schema to hist_nba_games
-- ================================================
CREATE TRANSIENT TABLE IF NOT EXISTS ipgross.stg_nba_games (
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
    ingested_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- ================================================
-- stg_nba_player_box_scores
-- Identical schema to hist_nba_player_box_scores
-- ================================================
CREATE TRANSIENT TABLE IF NOT EXISTS ipgross.stg_nba_player_box_scores (
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
    ingested_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Verify tables created
SHOW TABLES LIKE 'stg_%' IN SCHEMA ipgross;
