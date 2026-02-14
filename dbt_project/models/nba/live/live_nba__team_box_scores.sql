-- Aggregates live player box scores to team level.
-- Mirrors the existing Snowflake VIEW (live_nba_team_box_scores)
-- but managed in dbt for documentation and testing.

with player_stats as (

    select * from {{ source('nba_live', 'live_nba_player_box_scores') }}

)

select
    game_id
    , team_id
    , team_name
    , is_home
    , game_date
    , season
    , status
    , count(player_id)                        as players
    , sum(pts)                                as pts
    , sum(reb)                                as reb
    , sum(oreb)                               as oreb
    , sum(dreb)                               as dreb
    , sum(ast)                                as ast
    , sum(stl)                                as stl
    , sum(blk)                                as blk
    , sum(turnover)                           as turnovers
    , sum(pf)                                 as pf
    , sum(fgm)                                as fgm
    , sum(fga)                                as fga
    , {{ safe_divide('sum(fgm)', 'sum(fga)') }}
                                              as fg_pct
    , sum(fg3m)                               as fg3m
    , sum(fg3a)                               as fg3a
    , {{ safe_divide('sum(fg3m)', 'sum(fg3a)') }}
                                              as fg3_pct
    , sum(ftm)                                as ftm
    , sum(fta)                                as fta
    , {{ safe_divide('sum(ftm)', 'sum(fta)') }}
                                              as ft_pct
    , sum(fga) + 0.475 * sum(fta) - sum(oreb) + sum(turnover)
                                              as est_possessions
    , max(updated_at)                         as updated_at
from player_stats
group by
    game_id
    , team_id
    , team_name
    , is_home
    , game_date
    , season
    , status
