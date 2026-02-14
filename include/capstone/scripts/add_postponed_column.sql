-- ===========================================
-- Postponed column migration: DROP + RECREATE
-- Run manually in Snowflake before deploying code changes.
-- PAUSE ALL DAGS FIRST. Backfill will repopulate data.
--
-- After running this, also run:
--   create_hist_tables.sql  (recreates hist_nba_events with postponed)
--   create_stg_tables.sql   (recreates stg_nba_events with postponed)
--   create_live_tables.sql  (recreates all live tables + view)
-- ===========================================

USE ROLE ALL_USERS_ROLE;
USE DATABASE DATAEXPERT_STUDENT;
USE SCHEMA ipgross;
USE WAREHOUSE COMPUTE_WH;

-- ===========================================
-- Cold path events: drop + recreate via DDL scripts
-- ===========================================
DROP TABLE IF EXISTS ipgross.stg_nba_events;
DROP TABLE IF EXISTS ipgross.hist_nba_events;

-- ===========================================
-- Live tables: drop all + recreate via DDL script
-- View must be dropped first (depends on table)
-- ===========================================
DROP VIEW IF EXISTS ipgross.live_nba_team_box_scores;
DROP TABLE IF EXISTS ipgross.archive_nba_odds_snapshots;
DROP TABLE IF EXISTS ipgross.live_nba_plays;
DROP TABLE IF EXISTS ipgross.live_nba_odds;
DROP TABLE IF EXISTS ipgross.live_nba_player_box_scores;
DROP TABLE IF EXISTS ipgross.live_nba_scoreboard;

-- ===========================================
-- Cold path games: drop postponed if it was added previously
-- ===========================================
ALTER TABLE ipgross.hist_nba_games DROP COLUMN IF EXISTS postponed;
ALTER TABLE ipgross.stg_nba_games DROP COLUMN IF EXISTS postponed;

-- ===========================================
-- Now run the DDL scripts to recreate:
--   create_hist_tables.sql
--   create_stg_tables.sql
--   create_live_tables.sql
-- ===========================================
