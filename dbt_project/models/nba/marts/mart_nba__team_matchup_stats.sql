{{ config(materialized='table') }}

-- Season averages per team for head-to-head matchup comparison.
-- Grain: one row per (season, team_id).
-- Rebuilt daily (~90 rows across 3 seasons).

with team_stats as (

    select * from {{ ref('int_nba__team_game_stats') }}

)

, teams as (

    select * from {{ ref('stg_nba__teams') }}

)

, season_avgs as (

    select
        season
        , team_id
        , team_name
        , count(*)                            as games_played
        -- Scoring
        , avg(pts)                            as avg_pts
        , avg(opp_pts)                        as avg_opp_pts
        , avg(pts) - avg(opp_pts)             as avg_point_diff
        -- Shooting
        , avg(fgm)                            as avg_fgm
        , avg(fga)                            as avg_fga
        , avg(fg_pct)                         as avg_fg_pct
        , avg(fg3m)                           as avg_fg3m
        , avg(fg3a)                           as avg_fg3a
        , avg(fg3_pct)                        as avg_fg3_pct
        , avg(ftm)                            as avg_ftm
        , avg(fta)                            as avg_fta
        , avg(ft_pct)                         as avg_ft_pct
        -- Rebounding
        , avg(reb)                            as avg_reb
        , avg(oreb)                           as avg_oreb
        , avg(dreb)                           as avg_dreb
        -- Playmaking / defense
        , avg(ast)                            as avg_ast
        , avg(turnovers)                      as avg_turnovers
        , avg(stl)                            as avg_stl
        , avg(blk)                            as avg_blk
        , avg(pf)                             as avg_pf
        -- Advanced
        , avg(est_possessions)                as avg_possessions
        , avg(off_rating)                     as avg_off_rating
        , avg(def_rating)                     as avg_def_rating
        -- Home/away splits
        , avg(case when is_home then pts end)
                                              as home_avg_pts
        , avg(case when not is_home then pts end)
                                              as away_avg_pts
        , avg(case when is_home then off_rating end)
                                              as home_avg_off_rating
        , avg(case when not is_home then off_rating end)
                                              as away_avg_off_rating
        , avg(case when is_home then def_rating end)
                                              as home_avg_def_rating
        , avg(case when not is_home then def_rating end)
                                              as away_avg_def_rating
    from team_stats
    group by season, team_id, team_name

)

select
    sa.season
    , sa.team_id
    , sa.team_name
    , t.abbreviation
    , t.conference
    , t.division
    , sa.games_played
    , sa.avg_pts
    , sa.avg_opp_pts
    , sa.avg_point_diff
    , sa.avg_fgm
    , sa.avg_fga
    , sa.avg_fg_pct
    , sa.avg_fg3m
    , sa.avg_fg3a
    , sa.avg_fg3_pct
    , sa.avg_ftm
    , sa.avg_fta
    , sa.avg_ft_pct
    , sa.avg_reb
    , sa.avg_oreb
    , sa.avg_dreb
    , sa.avg_ast
    , sa.avg_turnovers
    , sa.avg_stl
    , sa.avg_blk
    , sa.avg_pf
    , sa.avg_possessions
    , sa.avg_off_rating
    , sa.avg_def_rating
    , sa.home_avg_pts
    , sa.away_avg_pts
    , sa.home_avg_off_rating
    , sa.away_avg_off_rating
    , sa.home_avg_def_rating
    , sa.away_avg_def_rating
    , rank() over (
        partition by sa.season
        order by sa.avg_off_rating desc
    )                                         as off_rating_rank
    , rank() over (
        partition by sa.season
        order by sa.avg_def_rating asc
    )                                         as def_rating_rank
    , rank() over (
        partition by sa.season
        order by sa.avg_point_diff desc
    )                                         as point_diff_rank
from season_avgs as sa
left join teams as t
    on sa.team_id = t.team_id
