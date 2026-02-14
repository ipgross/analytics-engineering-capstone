-- depends_on: {{ ref('audit_mart_nba__game_grades') }}

{{
    config(
        materialized='incremental',
        unique_key=['game_date', 'game_id', 'team_id'],
        incremental_strategy='merge'
    )
}}

-- Post-game performance grades comparing actual stats to L10 rolling
-- averages and season averages. Surfaces the key factors that drove
-- a cover or miss.
-- Grain: one row per (game_date, game_id, team_id) — two rows per game.
-- WAP: incremental runs publish from audit table; full refresh rebuilds from source.

{% if is_incremental() %}

select * from {{ ref('audit_mart_nba__game_grades') }}

{% else %}

with rolling as (

    select * from {{ ref('int_nba__team_rolling_stats') }}

)

, results as (

    select * from {{ ref('mart_nba__game_results') }}

)

select
    r.game_date
    , r.game_id
    , r.team_id
    , r.team_name
    , r.season
    , r.is_home
    , r.opp_team_name
    , r.season_game_number

    -- Actuals
    , r.pts
    , r.opp_pts
    , r.reb
    , r.ast
    , r.turnovers
    , r.stl
    , r.blk
    , r.pf
    , r.fg_pct
    , r.fg3_pct
    , r.ft_pct
    , r.est_possessions
    , r.off_rating
    , r.def_rating
    , r.score_margin
    , r.total_points

    -- Game result context
    , res.home_spread
    , case
        when r.is_home then res.home_spread_result
        else res.away_spread_result
      end                                     as spread_result
    , case
        when r.is_home then res.home_ml_result
        else res.away_ml_result
      end                                     as ml_result
    , res.over_result

    -- Deltas vs L10 rolling average (positive = better than expected)
    , r.pts - r.l10_avg_pts                   as pts_delta_l10
    , r.opp_pts - r.l10_avg_opp_pts           as opp_pts_delta_l10
    , r.reb - r.l10_avg_reb                   as reb_delta_l10
    , r.ast - r.l10_avg_ast                   as ast_delta_l10
    , r.turnovers - r.l10_avg_turnovers       as turnovers_delta_l10
    , r.stl - r.l10_avg_stl                   as stl_delta_l10
    , r.blk - r.l10_avg_blk                   as blk_delta_l10
    , r.fg_pct - r.l10_avg_fg_pct             as fg_pct_delta_l10
    , r.fg3_pct - r.l10_avg_fg3_pct           as fg3_pct_delta_l10
    , r.ft_pct - r.l10_avg_ft_pct             as ft_pct_delta_l10
    , r.off_rating - r.l10_avg_off_rating     as off_rating_delta_l10
    , r.def_rating - r.l10_avg_def_rating     as def_rating_delta_l10
    , r.est_possessions - r.l10_avg_possessions
                                              as possessions_delta_l10
    , r.pf - r.l10_avg_pf                    as pf_delta_l10

    -- Deltas vs season average
    , r.pts - r.season_avg_pts                as pts_delta_season
    , r.opp_pts - r.season_avg_opp_pts        as opp_pts_delta_season
    , r.reb - r.season_avg_reb                as reb_delta_season
    , r.ast - r.season_avg_ast                as ast_delta_season
    , r.turnovers - r.season_avg_turnovers    as turnovers_delta_season
    , r.stl - r.season_avg_stl                as stl_delta_season
    , r.blk - r.season_avg_blk                as blk_delta_season
    , r.fg_pct - r.season_avg_fg_pct          as fg_pct_delta_season
    , r.fg3_pct - r.season_avg_fg3_pct        as fg3_pct_delta_season
    , r.ft_pct - r.season_avg_ft_pct          as ft_pct_delta_season
    , r.off_rating - r.season_avg_off_rating  as off_rating_delta_season
    , r.def_rating - r.season_avg_def_rating  as def_rating_delta_season
    , r.est_possessions - r.season_avg_possessions
                                              as possessions_delta_season
    , r.pf - r.season_avg_pf                 as pf_delta_season

    -- L10 averages for reference
    , r.l10_avg_pts
    , r.l10_avg_opp_pts
    , r.l10_avg_fg_pct
    , r.l10_avg_fg3_pct
    , r.l10_avg_off_rating
    , r.l10_avg_def_rating

    -- Season averages for reference
    , r.season_avg_pts
    , r.season_avg_opp_pts
    , r.season_avg_fg_pct
    , r.season_avg_fg3_pct
    , r.season_avg_off_rating
    , r.season_avg_def_rating

    -- Offensive grade: off_rating delta vs L10 (higher = better offense)
    , {{ performance_grade('r.off_rating - r.l10_avg_off_rating') }}
                                              as off_performance_grade

    -- Defensive grade: INVERTED delta (lower def_rating = better defense)
    , {{ performance_grade('r.l10_avg_def_rating - r.def_rating') }}
                                              as def_performance_grade

    -- Hybrid: average of off delta + inverted def delta (net rating delta / 2)
    , {{ performance_grade('((r.off_rating - r.l10_avg_off_rating) + (r.l10_avg_def_rating - r.def_rating)) / 2.0') }}
                                              as performance_grade

from rolling as r
left join results as res
    on r.game_id = res.game_id
    and r.game_date = res.game_date
where r.l10_avg_pts is not null

{% endif %}
