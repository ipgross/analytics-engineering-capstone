-- Live post-game team performance grades comparing actual stats to
-- L10 rolling averages and season averages from cold-path data.
-- Mirrors mart_nba__game_grades using live box scores + cold-path rolling stats.
-- Grain: one row per (game_id, team_id) — two rows per game (home + away).
-- Rolling stats may be ~1 game stale; cold path produces exact grades at 3 AM.

with team_box as (

    select * from {{ ref('live_nba__team_box_scores') }}
    where status = 'Final'

)

, scoreboard as (

    select
        game_id
        , home_team_score - visitor_team_score       as score_margin
        , home_team_score + visitor_team_score       as total_points
    from {{ ref('live_nba__scoreboard') }}
    where status = 'Final'

)

-- Self-join to get opponent stats + compute off/def rating
, with_opponent as (

    select
        t.game_date
        , t.game_id
        , t.team_id
        , t.team_name
        , t.season
        , t.is_home
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
        , {{ safe_divide('t.pts', 't.est_possessions') }} * 100
                                                     as off_rating
        , {{ safe_divide('opp.pts', 't.est_possessions') }} * 100
                                                     as def_rating
        , opp.team_id                                as opp_team_id
        , opp.team_name                              as opp_team_name
        , opp.pts                                    as opp_pts
        , sb.score_margin
        , sb.total_points
    from team_box as t
    inner join team_box as opp
        on t.game_id = opp.game_id
        and t.team_id != opp.team_id
    inner join scoreboard as sb
        on t.game_id = sb.game_id

)

-- Most recent cold-path rolling stats per team (best available baseline)
, latest_rolling as (

    select *
    from {{ ref('int_nba__team_rolling_stats') }}
    qualify row_number() over (
        partition by team_id
        order by game_date desc, game_id desc
    ) = 1

)

, results as (

    select * from {{ ref('live_nba__game_results') }}

)

select
    wo.game_date
    , wo.game_id
    , wo.team_id
    , wo.team_name
    , wo.season
    , wo.is_home
    , wo.opp_team_name
    , lr.season_game_number

    -- Actuals
    , wo.pts
    , wo.opp_pts
    , wo.reb
    , wo.ast
    , wo.turnovers
    , wo.stl
    , wo.blk
    , wo.pf
    , wo.fg_pct
    , wo.fg3_pct
    , wo.ft_pct
    , wo.est_possessions
    , wo.off_rating
    , wo.def_rating
    , wo.score_margin
    , wo.total_points

    -- Game result context
    , res.home_spread
    , case
        when wo.is_home then res.home_spread_result
        else res.away_spread_result
      end                                            as spread_result
    , case
        when wo.is_home then res.home_ml_result
        else res.away_ml_result
      end                                            as ml_result
    , res.over_result

    -- Deltas vs L10 rolling average (positive = better than expected)
    , wo.pts - lr.l10_avg_pts                        as pts_delta_l10
    , wo.opp_pts - lr.l10_avg_opp_pts                as opp_pts_delta_l10
    , wo.reb - lr.l10_avg_reb                        as reb_delta_l10
    , wo.ast - lr.l10_avg_ast                        as ast_delta_l10
    , wo.turnovers - lr.l10_avg_turnovers            as turnovers_delta_l10
    , wo.stl - lr.l10_avg_stl                        as stl_delta_l10
    , wo.blk - lr.l10_avg_blk                        as blk_delta_l10
    , wo.fg_pct - lr.l10_avg_fg_pct                  as fg_pct_delta_l10
    , wo.fg3_pct - lr.l10_avg_fg3_pct                as fg3_pct_delta_l10
    , wo.ft_pct - lr.l10_avg_ft_pct                  as ft_pct_delta_l10
    , wo.off_rating - lr.l10_avg_off_rating          as off_rating_delta_l10
    , wo.def_rating - lr.l10_avg_def_rating          as def_rating_delta_l10
    , wo.est_possessions - lr.l10_avg_possessions    as possessions_delta_l10
    , wo.pf - lr.l10_avg_pf                          as pf_delta_l10

    -- Deltas vs season average
    , wo.pts - lr.season_avg_pts                     as pts_delta_season
    , wo.opp_pts - lr.season_avg_opp_pts             as opp_pts_delta_season
    , wo.reb - lr.season_avg_reb                     as reb_delta_season
    , wo.ast - lr.season_avg_ast                     as ast_delta_season
    , wo.turnovers - lr.season_avg_turnovers         as turnovers_delta_season
    , wo.stl - lr.season_avg_stl                     as stl_delta_season
    , wo.blk - lr.season_avg_blk                     as blk_delta_season
    , wo.fg_pct - lr.season_avg_fg_pct               as fg_pct_delta_season
    , wo.fg3_pct - lr.season_avg_fg3_pct             as fg3_pct_delta_season
    , wo.ft_pct - lr.season_avg_ft_pct               as ft_pct_delta_season
    , wo.off_rating - lr.season_avg_off_rating       as off_rating_delta_season
    , wo.def_rating - lr.season_avg_def_rating       as def_rating_delta_season
    , wo.est_possessions - lr.season_avg_possessions as possessions_delta_season
    , wo.pf - lr.season_avg_pf                       as pf_delta_season

    -- L10 averages for reference
    , lr.l10_avg_pts
    , lr.l10_avg_opp_pts
    , lr.l10_avg_fg_pct
    , lr.l10_avg_fg3_pct
    , lr.l10_avg_off_rating
    , lr.l10_avg_def_rating

    -- Season averages for reference
    , lr.season_avg_pts
    , lr.season_avg_opp_pts
    , lr.season_avg_fg_pct
    , lr.season_avg_fg3_pct
    , lr.season_avg_off_rating
    , lr.season_avg_def_rating

    -- Offensive grade: off_rating delta vs L10 (higher = better offense)
    , {{ performance_grade('wo.off_rating - lr.l10_avg_off_rating') }}
                                                     as off_performance_grade

    -- Defensive grade: INVERTED delta (lower def_rating = better defense)
    , {{ performance_grade('lr.l10_avg_def_rating - wo.def_rating') }}
                                                     as def_performance_grade

    -- Hybrid: average of off delta + inverted def delta
    , {{ performance_grade('((wo.off_rating - lr.l10_avg_off_rating) + (lr.l10_avg_def_rating - wo.def_rating)) / 2.0') }}
                                                     as performance_grade

from with_opponent as wo
left join latest_rolling as lr
    on wo.team_id = lr.team_id
left join results as res
    on wo.game_id = res.game_id
    and wo.game_date = res.game_date
where lr.l10_avg_pts is not null
