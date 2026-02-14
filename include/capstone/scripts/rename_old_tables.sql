-- ================================================
-- Migration: Rename old raw_* tables to old_raw_*
-- Run this BEFORE deploying new DAGs
-- Tables remain accessible for data comparison
-- ================================================

USE ROLE ALL_USERS_ROLE;
USE DATABASE DATAEXPERT_STUDENT;
USE SCHEMA ipgross;

ALTER TABLE ipgross.raw_nba_events RENAME TO ipgross.old_raw_nba_events;
ALTER TABLE ipgross.raw_nba_odds RENAME TO ipgross.old_raw_nba_odds;
ALTER TABLE ipgross.raw_nba_games RENAME TO ipgross.old_raw_nba_games;
ALTER TABLE ipgross.raw_nba_player_box_scores RENAME TO ipgross.old_raw_nba_player_box_scores;
ALTER TABLE ipgross.raw_nba_teams RENAME TO ipgross.old_raw_nba_teams;

-- Verify renames
SHOW TABLES LIKE 'old_%' IN SCHEMA ipgross;
