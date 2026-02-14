-- ================================================================
-- NBA Analytics Pipeline — Data Quality Validation
-- Run after backfill or periodically to catch issues.
--
-- Each query returns rows only when something is WRONG.
-- No rows = all checks pass for that section.
-- ================================================================


-- ================================================================
-- 1. TABLE SUMMARY (informational — always returns rows)
-- ================================================================

SELECT '1. TABLE SUMMARY' AS section;

SELECT
    'hist_nba_events' AS table_name,
    COUNT(*) AS total_rows,
    COUNT(DISTINCT ds) AS distinct_dates,
    MIN(ds) AS min_ds,
    MAX(ds) AS max_ds
FROM ipgross.hist_nba_events
UNION ALL
SELECT
    'hist_nba_odds_open',
    COUNT(*),
    COUNT(DISTINCT ds),
    MIN(ds),
    MAX(ds)
FROM ipgross.hist_nba_odds_open
UNION ALL
SELECT
    'hist_nba_games',
    COUNT(*),
    COUNT(DISTINCT ds),
    MIN(ds),
    MAX(ds)
FROM ipgross.hist_nba_games
UNION ALL
SELECT
    'hist_nba_player_box_scores',
    COUNT(*),
    COUNT(DISTINCT ds),
    MIN(ds),
    MAX(ds)
FROM ipgross.hist_nba_player_box_scores
UNION ALL
SELECT
    'hist_nba_teams',
    COUNT(*),
    NULL,
    NULL,
    NULL
FROM ipgross.hist_nba_teams
ORDER BY table_name;


-- ================================================================
-- 2. DATE COVERAGE GAPS
--    Dates that exist in one table but not another.
--    Events is the "schedule of truth" — every date with events
--    should eventually have games and box scores.
-- ================================================================

SELECT '2a. DATES WITH EVENTS BUT NO GAMES' AS section;

SELECT
    e.ds,
    e.event_count,
    'Missing games for this date' AS issue
FROM (
    SELECT ds, COUNT(*) AS event_count
    FROM ipgross.hist_nba_events
    GROUP BY ds
) e
LEFT JOIN (
    SELECT DISTINCT ds FROM ipgross.hist_nba_games
) g ON e.ds = g.ds
WHERE g.ds IS NULL
ORDER BY e.ds;


SELECT '2b. DATES WITH EVENTS BUT NO ODDS' AS section;

SELECT
    e.ds,
    e.event_count,
    'Missing odds for this date' AS issue
FROM (
    SELECT ds, COUNT(*) AS event_count
    FROM ipgross.hist_nba_events
    GROUP BY ds
) e
LEFT JOIN (
    SELECT DISTINCT ds FROM ipgross.hist_nba_odds_open
) o ON e.ds = o.ds
WHERE o.ds IS NULL
ORDER BY e.ds;


SELECT '2c. DATES WITH GAMES BUT NO BOX SCORES' AS section;

SELECT
    g.ds,
    g.game_count,
    'Missing box scores for this date' AS issue
FROM (
    SELECT ds, COUNT(*) AS game_count
    FROM ipgross.hist_nba_games
    GROUP BY ds
) g
LEFT JOIN (
    SELECT DISTINCT ds FROM ipgross.hist_nba_player_box_scores
) b ON g.ds = b.ds
WHERE b.ds IS NULL
ORDER BY g.ds;


-- ================================================================
-- 3. GAME COUNT MISMATCHES PER DATE
--    Events (Odds API) and games (BDL) should show the same
--    number of games per date. Small differences are OK
--    (postponements, API timing), but large gaps signal a bug.
-- ================================================================

SELECT '3. GAME COUNT MISMATCH: EVENTS vs GAMES' AS section;

SELECT
    COALESCE(e.ds, g.ds) AS ds,
    e.event_count,
    g.game_count,
    ABS(COALESCE(e.event_count, 0) - COALESCE(g.game_count, 0)) AS difference,
    CASE
        WHEN e.event_count IS NULL THEN 'Games exist but no events'
        WHEN g.game_count IS NULL THEN 'Events exist but no games'
        WHEN e.event_count > g.game_count THEN 'More events than games (possible postponement)'
        WHEN g.game_count > e.event_count THEN 'More games than events (possible API gap)'
    END AS issue
FROM (
    SELECT ds, COUNT(*) AS event_count
    FROM ipgross.hist_nba_events
    GROUP BY ds
) e
FULL OUTER JOIN (
    SELECT ds, COUNT(*) AS game_count
    FROM ipgross.hist_nba_games
    GROUP BY ds
) g ON e.ds = g.ds
WHERE COALESCE(e.event_count, 0) != COALESCE(g.game_count, 0)
ORDER BY COALESCE(e.ds, g.ds);


-- ================================================================
-- 4. BOX SCORE COMPLETENESS
--    Each game must have players from BOTH teams.
--    NBA rosters have 15 players; usually 10-13 play per game.
--    Minimum 5 per team (the starters). Flag games with < 5
--    players on either side.
-- ================================================================

SELECT '4a. GAMES WITH TOO FEW PLAYERS (< 5 per team)' AS section;

SELECT
    ds,
    game_id,
    team_name,
    is_home,
    player_count,
    'Fewer than 5 players — incomplete box score' AS issue
FROM (
    SELECT
        ds,
        game_id,
        team_name,
        is_home,
        COUNT(DISTINCT player_id) AS player_count
    FROM ipgross.hist_nba_player_box_scores
    GROUP BY ds, game_id, team_name, is_home
) team_counts
WHERE player_count < 5
ORDER BY ds, game_id;


SELECT '4b. GAMES MISSING A TEAM (only home or only away)' AS section;

SELECT
    ds,
    game_id,
    COUNT(DISTINCT CASE WHEN is_home THEN team_id END) AS home_teams,
    COUNT(DISTINCT CASE WHEN NOT is_home THEN team_id END) AS away_teams,
    'Game missing home or away team box score' AS issue
FROM ipgross.hist_nba_player_box_scores
GROUP BY ds, game_id
HAVING home_teams = 0 OR away_teams = 0
ORDER BY ds, game_id;


SELECT '4c. BOX SCORE GAME COUNT vs GAMES TABLE' AS section;

SELECT
    COALESCE(g.ds, b.ds) AS ds,
    g.game_count AS games_table_count,
    b.box_score_game_count,
    CASE
        WHEN g.game_count IS NULL THEN 'Box scores exist but no games record'
        WHEN b.box_score_game_count IS NULL THEN 'Games exist but no box scores'
        WHEN g.game_count != b.box_score_game_count THEN 'Game count mismatch'
    END AS issue
FROM (
    SELECT ds, COUNT(*) AS game_count
    FROM ipgross.hist_nba_games
    GROUP BY ds
) g
FULL OUTER JOIN (
    SELECT ds, COUNT(DISTINCT game_id) AS box_score_game_count
    FROM ipgross.hist_nba_player_box_scores
    GROUP BY ds
) b ON g.ds = b.ds
WHERE COALESCE(g.game_count, 0) != COALESCE(b.box_score_game_count, 0)
ORDER BY COALESCE(g.ds, b.ds);


-- ================================================================
-- 5. ODDS COMPLETENESS
--    Each event on a date should have odds from at least 1
--    bookmaker across all 3 markets (h2h, spreads, totals).
-- ================================================================

SELECT '5a. EVENTS WITH NO ODDS' AS section;

SELECT
    e.ds,
    e.event_id,
    e.home_team,
    e.away_team,
    'Event has no odds records' AS issue
FROM ipgross.hist_nba_events e
LEFT JOIN (
    SELECT DISTINCT ds, event_id FROM ipgross.hist_nba_odds_open
) o ON e.ds = o.ds AND e.event_id = o.event_id
WHERE o.event_id IS NULL
ORDER BY e.ds, e.home_team;


SELECT '5b. EVENTS MISSING MARKET COVERAGE' AS section;

SELECT
    ds,
    event_id,
    home_team,
    away_team,
    LISTAGG(DISTINCT market_key, ', ') AS markets_present,
    3 - COUNT(DISTINCT market_key) AS markets_missing
FROM ipgross.hist_nba_odds_open
GROUP BY ds, event_id, home_team, away_team
HAVING COUNT(DISTINCT market_key) < 3
ORDER BY ds, home_team;


-- ================================================================
-- 6. SCORE SANITY CHECKS
--    Final games should have non-null, non-zero scores.
--    NBA scores are typically 80-150.
-- ================================================================

SELECT '6a. GAMES WITH NULL OR ZERO SCORES' AS section;

SELECT
    ds,
    game_id,
    home_team_name,
    visitor_team_name,
    home_team_score,
    visitor_team_score,
    status,
    'Null or zero score for Final game' AS issue
FROM ipgross.hist_nba_games
WHERE status = 'Final'
  AND (
    home_team_score IS NULL OR home_team_score = 0
    OR visitor_team_score IS NULL OR visitor_team_score = 0
  )
ORDER BY ds;


SELECT '6b. GAMES WITH SUSPICIOUS SCORES (< 70 or > 200)' AS section;

SELECT
    ds,
    game_id,
    home_team_name,
    visitor_team_name,
    home_team_score,
    visitor_team_score,
    'Score outside normal NBA range' AS issue
FROM ipgross.hist_nba_games
WHERE status = 'Final'
  AND (
    home_team_score < 70 OR home_team_score > 200
    OR visitor_team_score < 70 OR visitor_team_score > 200
  )
ORDER BY ds;


-- ================================================================
-- 7. BOX SCORE STAT SANITY
--    Check for impossible stat values.
-- ================================================================

SELECT '7a. PLAYERS WITH NEGATIVE STATS' AS section;

SELECT
    ds,
    game_id,
    player_name,
    team_name,
    pts, reb, ast, stl, blk, turnover,
    'Negative stat value' AS issue
FROM ipgross.hist_nba_player_box_scores
WHERE pts < 0 OR reb < 0 OR ast < 0 OR stl < 0 OR blk < 0 OR turnover < 0
  OR fgm < 0 OR fga < 0 OR fg3m < 0 OR fg3a < 0 OR ftm < 0 OR fta < 0
ORDER BY ds, game_id
LIMIT 20;


SELECT '7b. PLAYERS WITH MORE MAKES THAN ATTEMPTS' AS section;

SELECT
    ds,
    game_id,
    player_name,
    team_name,
    fgm, fga, fg3m, fg3a, ftm, fta,
    'More makes than attempts' AS issue
FROM ipgross.hist_nba_player_box_scores
WHERE fgm > fga OR fg3m > fg3a OR ftm > fta
ORDER BY ds, game_id
LIMIT 20;


SELECT '7c. TEAM POINTS MISMATCH (sum of player pts vs game score)' AS section;

SELECT
    b.ds,
    b.game_id,
    b.team_name,
    b.is_home,
    b.sum_player_pts,
    CASE
        WHEN b.is_home THEN g.home_team_score
        ELSE g.visitor_team_score
    END AS game_score,
    b.sum_player_pts - CASE
        WHEN b.is_home THEN g.home_team_score
        ELSE g.visitor_team_score
    END AS pts_difference,
    'Player pts total does not match game score' AS issue
FROM (
    SELECT
        ds,
        game_id,
        team_name,
        is_home,
        SUM(pts) AS sum_player_pts
    FROM ipgross.hist_nba_player_box_scores
    GROUP BY ds, game_id, team_name, is_home
) b
JOIN ipgross.hist_nba_games g
    ON b.ds = g.ds AND b.game_id = g.game_id
WHERE b.sum_player_pts != CASE
    WHEN b.is_home THEN g.home_team_score
    ELSE g.visitor_team_score
END
ORDER BY b.ds, b.game_id;


-- ================================================================
-- 8. DUPLICATE DETECTION
--    Primary key violations shouldn't be possible, but check
--    for logical duplicates anyway.
-- ================================================================

SELECT '8a. DUPLICATE EVENTS (same ds + event_id)' AS section;

SELECT ds, event_id, COUNT(*) AS cnt
FROM ipgross.hist_nba_events
GROUP BY ds, event_id
HAVING COUNT(*) > 1
ORDER BY ds;


SELECT '8b. DUPLICATE GAMES (same ds + game_id)' AS section;

SELECT ds, game_id, COUNT(*) AS cnt
FROM ipgross.hist_nba_games
GROUP BY ds, game_id
HAVING COUNT(*) > 1
ORDER BY ds;


SELECT '8c. DUPLICATE BOX SCORES (same ds + game_id + player_id)' AS section;

SELECT ds, game_id, player_id, player_name, COUNT(*) AS cnt
FROM ipgross.hist_nba_player_box_scores
GROUP BY ds, game_id, player_id, player_name
HAVING COUNT(*) > 1
ORDER BY ds;


-- ================================================================
-- 9. REFERENTIAL INTEGRITY
--    Teams in games/box_scores should exist in teams table.
-- ================================================================

SELECT '9a. UNKNOWN HOME TEAMS IN GAMES' AS section;

SELECT DISTINCT
    g.home_team_id,
    g.home_team_name,
    'Home team not in hist_nba_teams' AS issue
FROM ipgross.hist_nba_games g
LEFT JOIN ipgross.hist_nba_teams t ON g.home_team_id = t.team_id
WHERE t.team_id IS NULL
ORDER BY g.home_team_name;


SELECT '9b. UNKNOWN TEAMS IN BOX SCORES' AS section;

SELECT DISTINCT
    b.team_id,
    b.team_name,
    'Team not in hist_nba_teams' AS issue
FROM ipgross.hist_nba_player_box_scores b
LEFT JOIN ipgross.hist_nba_teams t ON b.team_id = t.team_id
WHERE t.team_id IS NULL
ORDER BY b.team_name;


-- ================================================================
-- 10. TEAMS TABLE CHECKS
-- ================================================================

SELECT '10. TEAMS TABLE VALIDATION' AS section;

SELECT
    COUNT(*) AS total_teams,
    COUNT(DISTINCT conference) AS conferences,
    COUNT(CASE WHEN conference = 'East' THEN 1 END) AS east_teams,
    COUNT(CASE WHEN conference = 'West' THEN 1 END) AS west_teams,
    COUNT(CASE WHEN conference NOT IN ('East', 'West') THEN 1 END) AS other_teams,
    CASE
        WHEN COUNT(*) != 30 THEN 'Expected 30 NBA teams, got ' || COUNT(*)
        WHEN COUNT(CASE WHEN conference = 'East' THEN 1 END) != 15 THEN 'Expected 15 East teams'
        WHEN COUNT(CASE WHEN conference = 'West' THEN 1 END) != 15 THEN 'Expected 15 West teams'
        ELSE 'OK'
    END AS validation
FROM ipgross.hist_nba_teams;


-- ================================================================
-- 11. SEASON COLUMN CONSISTENCY
--     All records for a given date should have the same season.
-- ================================================================

SELECT '11. DATES WITH MULTIPLE SEASONS' AS section;

SELECT ds, LISTAGG(DISTINCT season, ', ') AS seasons, COUNT(DISTINCT season) AS season_count
FROM (
    SELECT ds, season FROM ipgross.hist_nba_events
    UNION ALL
    SELECT ds, season FROM ipgross.hist_nba_games
)
GROUP BY ds
HAVING COUNT(DISTINCT season) > 1
ORDER BY ds;
