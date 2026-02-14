-- depends_on: {{ ref('audit_int_nba__team_game_stats') }}

{{
    config(
        materialized='incremental',
        unique_key=['game_date', 'game_id', 'team_id'],
        incremental_strategy='merge'
    )
}}

-- Aggregates player box scores to team-game level with advanced metrics.
-- Grain: one row per (game_date, game_id, team_id) — two rows per game.
-- WAP: incremental runs publish from audit table; full refresh rebuilds from source.

{% if is_incremental() %}

select * from {{ ref('audit_int_nba__team_game_stats') }}

{% else %}

with player_stats as (

    select * from {{ ref('stg_nba__player_box_scores') }}

)

, games as (

    select * from {{ ref('stg_nba__games') }}

)

, team_agg as (

    select
        ps.game_date
        , ps.game_id
        , ps.team_id
        , ps.team_name
        , ps.season
        , ps.is_home
        , count(ps.player_id)                 as players_used
        , sum(ps.minutes_played)              as total_minutes
        , sum(ps.pts)                         as pts
        , sum(ps.reb)                         as reb
        , sum(ps.oreb)                        as oreb
        , sum(ps.dreb)                        as dreb
        , sum(ps.ast)                         as ast
        , sum(ps.stl)                         as stl
        , sum(ps.blk)                         as blk
        , sum(ps.turnovers)                   as turnovers
        , sum(ps.pf)                          as pf
        , sum(ps.fgm)                         as fgm
        , sum(ps.fga)                         as fga
        , {{ safe_divide('sum(ps.fgm)', 'sum(ps.fga)') }}
                                              as fg_pct
        , sum(ps.fg3m)                        as fg3m
        , sum(ps.fg3a)                        as fg3a
        , {{ safe_divide('sum(ps.fg3m)', 'sum(ps.fg3a)') }}
                                              as fg3_pct
        , sum(ps.ftm)                         as ftm
        , sum(ps.fta)                         as fta
        , {{ safe_divide('sum(ps.ftm)', 'sum(ps.fta)') }}
                                              as ft_pct
        , sum(ps.fga) + 0.475 * sum(ps.fta)
          - sum(ps.oreb) + sum(ps.turnovers)
                                              as est_possessions
        -- Dean Oliver's Four Factors
        , {{ safe_divide('sum(ps.fgm) + 0.5 * sum(ps.fg3m)', 'sum(ps.fga)') }}
                                              as efg_pct
        , {{ safe_divide('sum(ps.turnovers)',
            'sum(ps.fga) + 0.475 * sum(ps.fta) - sum(ps.oreb) + sum(ps.turnovers)') }}
                                              as tov_pct
        , {{ safe_divide('sum(ps.fta)', 'sum(ps.fga)') }}
                                              as ftr
    from player_stats as ps
    group by
        ps.game_date
        , ps.game_id
        , ps.team_id
        , ps.team_name
        , ps.season
        , ps.is_home

)

, with_opponent as (

    select
        t.game_date
        , t.game_id
        , t.team_id
        , t.team_name
        , t.season
        , t.is_home
        , g.home_team_score
        , g.visitor_team_score
        , g.score_margin
        , g.total_points
        , g.is_postseason
        , t.players_used
        , t.total_minutes
        , t.pts
        , t.reb
        , t.oreb
        , t.dreb
        , t.ast
        , t.stl
        , t.blk
        , t.turnovers
        , t.pf
        , t.fgm
        , t.fga
        , t.fg_pct
        , t.fg3m
        , t.fg3a
        , t.fg3_pct
        , t.ftm
        , t.fta
        , t.ft_pct
        , t.est_possessions
        , t.efg_pct
        , t.tov_pct
        , t.ftr
        , {{ safe_divide('t.oreb', 't.oreb + opp.dreb') }}
                                              as orb_pct
        , {{ safe_divide('t.pts', 't.est_possessions') }} * 100
                                              as off_rating
        , {{ safe_divide('opp.pts', 't.est_possessions') }} * 100
                                              as def_rating
        -- Opponent Four Factors (what opponents do against this team's defense)
        , opp.efg_pct                         as opp_efg_pct
        , opp.tov_pct                         as opp_tov_pct
        , opp.ftr                             as opp_ftr
        , {{ safe_divide('opp.oreb', 'opp.oreb + t.dreb') }}
                                              as opp_orb_pct
        , opp.team_id                         as opp_team_id
        , opp.team_name                       as opp_team_name
        , opp.pts                             as opp_pts
    from team_agg as t
    inner join team_agg as opp
        on t.game_id = opp.game_id
        and t.team_id != opp.team_id
    inner join games as g
        on t.game_id = g.game_id
        and t.game_date = g.game_date

)

select * from with_opponent

{% endif %}
