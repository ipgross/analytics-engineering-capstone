{{
    config(
        materialized='table'
    )
}}

-- WAP audit table: today's batch of player game grades for quality checks
-- before publishing to the incremental production table.
-- Grain: one row per (game_date, game_id, player_id).

with rolling as (

    select * from {{ ref('int_nba__player_rolling_stats') }}
    where game_date = current_date - 1

)

, results as (

    select * from {{ ref('mart_nba__game_results') }}

)

select
    r.game_date
    , r.game_id
    , r.player_id
    , r.player_name
    , r.team_id
    , r.team_name
    , r.season
    , r.is_home
    , r.season_game_number

    -- Actuals
    , r.minutes_played
    , r.pts
    , r.reb
    , r.ast
    , r.stl
    , r.blk
    , r.turnovers
    , r.pf
    , r.fg_pct
    , r.fg3_pct
    , r.ft_pct
    , r.game_score

    -- Game result context
    , res.home_spread
    , case
        when r.is_home then res.home_spread_result
        else res.away_spread_result
      end                                     as spread_result

    -- Deltas vs L10 rolling average
    , r.pts - r.l10_avg_pts                   as pts_delta_l10
    , r.reb - r.l10_avg_reb                   as reb_delta_l10
    , r.ast - r.l10_avg_ast                   as ast_delta_l10
    , r.stl - r.l10_avg_stl                   as stl_delta_l10
    , r.blk - r.l10_avg_blk                   as blk_delta_l10
    , r.turnovers - r.l10_avg_turnovers       as turnovers_delta_l10
    , r.pf - r.l10_avg_pf                    as pf_delta_l10
    , r.fg_pct - r.l10_avg_fg_pct             as fg_pct_delta_l10
    , r.fg3_pct - r.l10_avg_fg3_pct           as fg3_pct_delta_l10
    , r.ft_pct - r.l10_avg_ft_pct             as ft_pct_delta_l10
    , r.game_score - r.l10_avg_game_score     as game_score_delta_l10
    , r.minutes_played - r.l10_avg_minutes_played
                                              as minutes_delta_l10

    -- Deltas vs season average
    , r.pts - r.season_avg_pts                as pts_delta_season
    , r.reb - r.season_avg_reb                as reb_delta_season
    , r.ast - r.season_avg_ast                as ast_delta_season
    , r.stl - r.season_avg_stl                as stl_delta_season
    , r.blk - r.season_avg_blk                as blk_delta_season
    , r.turnovers - r.season_avg_turnovers    as turnovers_delta_season
    , r.pf - r.season_avg_pf                 as pf_delta_season
    , r.fg_pct - r.season_avg_fg_pct          as fg_pct_delta_season
    , r.fg3_pct - r.season_avg_fg3_pct        as fg3_pct_delta_season
    , r.ft_pct - r.season_avg_ft_pct          as ft_pct_delta_season
    , r.game_score - r.season_avg_game_score  as game_score_delta_season
    , r.minutes_played - r.season_avg_minutes_played
                                              as minutes_delta_season

    -- L10 averages for reference
    , r.l10_avg_pts
    , r.l10_avg_reb
    , r.l10_avg_ast
    , r.l10_avg_stl
    , r.l10_avg_blk
    , r.l10_avg_game_score
    , r.l10_avg_fg_pct
    , r.l10_avg_fg3_pct
    , r.l10_avg_minutes_played

    -- Season averages for reference
    , r.season_avg_pts
    , r.season_avg_reb
    , r.season_avg_ast
    , r.season_avg_stl
    , r.season_avg_blk
    , r.season_avg_game_score
    , r.season_avg_fg_pct
    , r.season_avg_fg3_pct
    , r.season_avg_minutes_played

    -- Overall grade: Hollinger Game Score delta vs L10
    , {{ performance_grade('r.game_score - r.l10_avg_game_score') }}
                                              as performance_grade

from rolling as r
left join results as res
    on r.game_id = res.game_id
    and r.game_date = res.game_date
where r.l10_avg_game_score is not null
    and r.minutes_played > 0
