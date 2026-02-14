-- ================================================
-- BallDontLie API Tables for NBA Analytics
-- Run this script in Snowflake to create tables
-- ================================================

USE SCHEMA DATAEXPERT_STUDENT.ipgross;

-- ================================================
-- 1. raw_nba_games
-- Game results with final scores
-- Used to calculate if spread was covered
-- ================================================
CREATE TABLE IF NOT EXISTS ipgross.raw_nba_games (
    ds                  DATE NOT NULL,           -- Partition key (execution date)
    game_id             INTEGER NOT NULL,        -- BallDontLie game ID
    season              VARCHAR(10) NOT NULL,    -- e.g., "2023-24"
    game_date           DATE NOT NULL,           -- Actual game date
    status              VARCHAR(20) NOT NULL,    -- "Final", "In Progress", etc.

    -- Home team
    home_team_id        INTEGER NOT NULL,
    home_team_name      VARCHAR(100) NOT NULL,
    home_team_score     INTEGER,

    -- Visitor team
    visitor_team_id     INTEGER NOT NULL,
    visitor_team_name   VARCHAR(100) NOT NULL,
    visitor_team_score  INTEGER,

    -- Metadata
    postseason          BOOLEAN DEFAULT FALSE,
    s3_path             VARCHAR(500),
    ingested_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),

    PRIMARY KEY (ds, game_id)
);

-- ================================================
-- 2. raw_nba_player_box_scores
-- Raw player-level stats
-- Aggregated to team level in dbt for fast ingestion
-- ================================================
CREATE TABLE IF NOT EXISTS ipgross.raw_nba_player_box_scores (
    ds                  DATE NOT NULL,           -- Partition key (execution date)
    game_id             INTEGER NOT NULL,
    player_id           INTEGER NOT NULL,
    player_name         VARCHAR(100) NOT NULL,
    team_id             INTEGER NOT NULL,
    team_name           VARCHAR(100) NOT NULL,
    season              INTEGER NOT NULL,
    game_date           DATE NOT NULL,
    is_home             BOOLEAN NOT NULL,

    -- Raw player stats (NOT aggregated - dbt does that)
    min                 VARCHAR(10),             -- "32:15" format
    pts                 INTEGER,
    reb                 INTEGER,
    oreb                INTEGER,
    dreb                INTEGER,
    ast                 INTEGER,
    stl                 INTEGER,
    blk                 INTEGER,
    turnover            INTEGER,
    pf                  INTEGER,                 -- Personal fouls
    fgm                 INTEGER,
    fga                 INTEGER,
    fg_pct              FLOAT,
    fg3m                INTEGER,
    fg3a                INTEGER,
    fg3_pct             FLOAT,
    ftm                 INTEGER,
    fta                 INTEGER,
    ft_pct              FLOAT,

    -- Metadata
    s3_path             VARCHAR(500),
    ingested_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),

    PRIMARY KEY (ds, game_id, player_id)
);

-- ================================================
-- 3. raw_nba_teams
-- Reference table for team info
-- Loaded once, updated rarely
-- ================================================
CREATE TABLE IF NOT EXISTS ipgross.raw_nba_teams (
    team_id             INTEGER NOT NULL,
    full_name           VARCHAR(100) NOT NULL,
    name                VARCHAR(50) NOT NULL,     -- e.g., "Lakers"
    city                VARCHAR(50) NOT NULL,     -- e.g., "Los Angeles"
    abbreviation        VARCHAR(10) NOT NULL,     -- e.g., "LAL"
    conference          VARCHAR(10) NOT NULL,     -- "East" or "West"
    division            VARCHAR(20) NOT NULL,     -- e.g., "Pacific"
    ingested_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),

    PRIMARY KEY (team_id)
);

-- ================================================
-- Verification queries
-- ================================================

-- Check tables exist
-- SELECT * FROM ipgross.raw_nba_games LIMIT 5;
-- SELECT * FROM ipgross.raw_nba_player_box_scores LIMIT 5;
-- SELECT * FROM ipgross.raw_nba_teams LIMIT 5;
