-- ================================================
-- Historical (Cold Path) Tables DDL
-- Run this AFTER rename_old_tables.sql
-- ================================================

USE ROLE ALL_USERS_ROLE;
USE DATABASE DATAEXPERT_STUDENT;
USE SCHEMA ipgross;
USE WAREHOUSE COMPUTE_WH;

-- ================================================
-- hist_nba_events
-- Source: The Odds API (events endpoint)
-- Schedule: nba_daily_events DAG
-- ================================================
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

-- ================================================
-- hist_nba_odds_open
-- Source: The Odds API (odds endpoint)
-- Schedule: nba_daily_odds_snapshot DAG
-- Morning line snapshot (training feature for modeling)
-- ================================================
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

-- ================================================
-- hist_nba_games
-- Source: BallDontLie API (games endpoint)
-- Schedule: nba_daily_reconcile DAG
-- ================================================
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

-- ================================================
-- hist_nba_player_box_scores
-- Source: BallDontLie API (box_scores endpoint)
-- Schedule: nba_daily_reconcile DAG
-- Player-level stats; team aggregation in dbt
-- ================================================
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

-- ================================================
-- hist_nba_teams
-- Source: BallDontLie API (teams endpoint)
-- Schedule: nba_teams_load DAG (manual)
-- ================================================
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

-- Verify tables created
SHOW TABLES LIKE 'hist_%' IN SCHEMA ipgross;
