-- ===========================================
-- NBA Live Tables DDL (Hot Path - Phase 2)
-- Run manually in Snowflake before unpausing live DAGs.
-- ===========================================

-- Live Scoreboard: all games (scheduled, live, final)
-- DROP TABLE IF EXISTS ipgross.live_nba_scoreboard;  -- uncomment to recreate
CREATE TABLE IF NOT EXISTS ipgross.live_nba_scoreboard (
    game_id                     INTEGER NOT NULL,
    game_date                   DATE NOT NULL,
    season                      INTEGER,
    status                      VARCHAR(30) NOT NULL,
    period                      INTEGER,
    clock                       VARCHAR(10),
    game_datetime               TIMESTAMP_NTZ,          -- tip-off time from API
    home_team_id                INTEGER NOT NULL,
    home_team_name              VARCHAR(100) NOT NULL,
    home_team_score             INTEGER NOT NULL DEFAULT 0,
    home_q1                     INTEGER,
    home_q2                     INTEGER,
    home_q3                     INTEGER,
    home_q4                     INTEGER,
    home_ot1                    INTEGER,                 -- 1st overtime
    home_ot2                    INTEGER,                 -- 2nd overtime
    home_ot3                    INTEGER,                 -- 3rd overtime
    home_timeouts_remaining     INTEGER,
    home_in_bonus               BOOLEAN,
    visitor_team_id             INTEGER NOT NULL,
    visitor_team_name           VARCHAR(100) NOT NULL,
    visitor_team_score          INTEGER NOT NULL DEFAULT 0,
    visitor_q1                  INTEGER,
    visitor_q2                  INTEGER,
    visitor_q3                  INTEGER,
    visitor_q4                  INTEGER,
    visitor_ot1                 INTEGER,
    visitor_ot2                 INTEGER,
    visitor_ot3                 INTEGER,
    visitor_timeouts_remaining  INTEGER,
    visitor_in_bonus            BOOLEAN,
    postseason                  BOOLEAN DEFAULT FALSE,
    postponed                   BOOLEAN DEFAULT FALSE,
    updated_at                  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (game_id)
);

-- Live Player Box Scores: stats update in real-time during games
CREATE TABLE IF NOT EXISTS ipgross.live_nba_player_box_scores (
    game_id             INTEGER NOT NULL,
    player_id           INTEGER NOT NULL,
    player_name         VARCHAR(100) NOT NULL,
    team_id             INTEGER NOT NULL,
    team_name           VARCHAR(100) NOT NULL,
    is_home             BOOLEAN NOT NULL,
    game_date           DATE NOT NULL,
    season              INTEGER,
    status              VARCHAR(30) NOT NULL,
    min                 VARCHAR(10),
    pts                 INTEGER DEFAULT 0,
    reb                 INTEGER DEFAULT 0,
    oreb                INTEGER DEFAULT 0,
    dreb                INTEGER DEFAULT 0,
    ast                 INTEGER DEFAULT 0,
    stl                 INTEGER DEFAULT 0,
    blk                 INTEGER DEFAULT 0,
    turnover            INTEGER DEFAULT 0,
    pf                  INTEGER DEFAULT 0,
    fgm                 INTEGER DEFAULT 0,
    fga                 INTEGER DEFAULT 0,
    fg_pct              FLOAT,
    fg3m                INTEGER DEFAULT 0,
    fg3a                INTEGER DEFAULT 0,
    fg3_pct             FLOAT,
    ftm                 INTEGER DEFAULT 0,
    fta                 INTEGER DEFAULT 0,
    ft_pct              FLOAT,
    updated_at          TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (game_id, player_id)
);

-- Live Odds: current lines from The Odds API
-- Completed games disappear from API but rows persist (MERGE never deletes)
CREATE TABLE IF NOT EXISTS ipgross.live_nba_odds (
    event_id                VARCHAR(64) NOT NULL,
    game_date               DATE,
    home_team               VARCHAR(100) NOT NULL,
    away_team               VARCHAR(100) NOT NULL,
    commence_time_utc       TIMESTAMP_NTZ NOT NULL,
    bookmaker_key           VARCHAR(50) NOT NULL,
    bookmaker_title         VARCHAR(100),
    bookmaker_last_update   TIMESTAMP_NTZ,
    market_key              VARCHAR(20) NOT NULL,
    outcome_name            VARCHAR(100) NOT NULL,
    outcome_price           INTEGER NOT NULL,
    outcome_point           FLOAT,
    updated_at              TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (event_id, bookmaker_key, market_key, outcome_name)
);

-- Live Play-by-Play: individual play events (2025 season onward)
-- DROP TABLE IF EXISTS ipgross.live_nba_plays;  -- uncomment to recreate
CREATE TABLE IF NOT EXISTS ipgross.live_nba_plays (
    game_id             INTEGER NOT NULL,
    play_id             INTEGER NOT NULL,
    period              INTEGER,
    period_display      VARCHAR(30),                 -- "1st Quarter", "Halftime", etc.
    clock               VARCHAR(10),
    action_type         VARCHAR(50),
    description         VARCHAR(500),
    team_id             INTEGER,
    team_name           VARCHAR(100),
    scoring_play        BOOLEAN DEFAULT FALSE,
    shooting_play       BOOLEAN DEFAULT FALSE,
    score_value         INTEGER,                     -- points scored on this play (null if not scoring)
    home_score          INTEGER DEFAULT 0,
    away_score          INTEGER DEFAULT 0,
    coordinate_x        INTEGER,                     -- shot chart x coordinate
    coordinate_y        INTEGER,                     -- shot chart y coordinate
    updated_at          TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (game_id, play_id)
);

-- Archive: append-only odds snapshots for line movement history
-- No primary key, no MERGE — just INSERT after every odds refresh
CREATE TABLE IF NOT EXISTS ipgross.archive_nba_odds_snapshots (
    snapshot_time           TIMESTAMP_NTZ NOT NULL,
    event_id                VARCHAR(64) NOT NULL,
    game_date               DATE,
    home_team               VARCHAR(100),
    away_team               VARCHAR(100),
    commence_time_utc       TIMESTAMP_NTZ,
    bookmaker_key           VARCHAR(50) NOT NULL,
    bookmaker_title         VARCHAR(100),
    bookmaker_last_update   TIMESTAMP_NTZ,
    market_key              VARCHAR(20) NOT NULL,
    outcome_name            VARCHAR(100) NOT NULL,
    outcome_price           INTEGER,
    outcome_point           FLOAT,
    updated_at              TIMESTAMP_NTZ
);

-- Team Box Scores VIEW: aggregates player stats to team level automatically
CREATE OR REPLACE VIEW ipgross.live_nba_team_box_scores AS
SELECT
    bs.game_id, bs.team_id, bs.team_name, bs.is_home,
    bs.game_date, bs.season, bs.status,
    COUNT(bs.player_id)                              AS players,
    SUM(bs.pts) AS pts, SUM(bs.reb) AS reb,
    SUM(bs.oreb) AS oreb, SUM(bs.dreb) AS dreb,
    SUM(bs.ast) AS ast, SUM(bs.stl) AS stl,
    SUM(bs.blk) AS blk, SUM(bs.turnover) AS turnovers, SUM(bs.pf) AS pf,
    SUM(bs.fgm) AS fgm, SUM(bs.fga) AS fga,
    SUM(bs.fgm)::FLOAT / NULLIF(SUM(bs.fga), 0)    AS fg_pct,
    SUM(bs.fg3m) AS fg3m, SUM(bs.fg3a) AS fg3a,
    SUM(bs.fg3m)::FLOAT / NULLIF(SUM(bs.fg3a), 0)   AS fg3_pct,
    SUM(bs.ftm) AS ftm, SUM(bs.fta) AS fta,
    SUM(bs.ftm)::FLOAT / NULLIF(SUM(bs.fta), 0)     AS ft_pct,
    SUM(bs.fga) + 0.475 * SUM(bs.fta) - SUM(bs.oreb) + SUM(bs.turnover) AS est_possessions,
    MAX(bs.updated_at) AS updated_at
FROM ipgross.live_nba_player_box_scores bs
GROUP BY bs.game_id, bs.team_id, bs.team_name, bs.is_home,
         bs.game_date, bs.season, bs.status;
