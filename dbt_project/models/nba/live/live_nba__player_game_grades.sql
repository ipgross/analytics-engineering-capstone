-- Live post-game player performance grades comparing actual stats to
-- L10 rolling averages and season averages from cold-path data.
-- Uses Hollinger's Game Score for the overall grade.
-- Mirrors mart_nba__player_game_grades using live box scores + cold-path rolling stats.
-- Grain: one row per (game_id, player_id) — Final games only.
-- Rolling stats may be ~1 game stale; cold path produces exact grades at 3 AM.

with player_box as (

    select
        game_id
        , player_id
        , player_name
        , team_id
        , team_name
        , is_home
        , game_date
        , season
        , {{ parse_minutes('min') }}                 as minutes_played
        , coalesce(pts, 0)                           as pts
        , coalesce(reb, 0)                           as reb
        , coalesce(oreb, 0)                          as oreb
        , coalesce(dreb, 0)                          as dreb
        , coalesce(ast, 0)                           as ast
        , coalesce(stl, 0)                           as stl
        , coalesce(blk, 0)                           as blk
        , coalesce(turnovers, 0)                     as turnovers
        , coalesce(pf, 0)                            as pf
        , coalesce(fgm, 0)                           as fgm
        , coalesce(fga, 0)                           as fga
        , coalesce(fg3m, 0)                          as fg3m
        , coalesce(fg3a, 0)                          as fg3a
        , coalesce(ftm, 0)                           as ftm
        , coalesce(fta, 0)                           as fta
    from {{ ref('live_nba__player_box_scores') }}
    where status = 'Final'

)

, with_game_score as (

    select
        *
        , {{ safe_divide('fgm', 'fga') }}           as fg_pct
        , {{ safe_divide('fg3m', 'fg3a') }}          as fg3_pct
        , {{ safe_divide('ftm', 'fta') }}            as ft_pct
        -- Hollinger's Game Score
        , pts + 0.4 * fgm - 0.7 * fga
          - 0.4 * (fta - ftm)
          + 0.7 * oreb + 0.3 * dreb
          + stl + 0.7 * ast + 0.7 * blk
          - 0.4 * pf - turnovers
                                                     as game_score
    from player_box
    where minutes_played > 0

)

-- Most recent cold-path rolling stats per player (best available baseline)
, latest_rolling as (

    select *
    from {{ ref('int_nba__player_rolling_stats') }}
    qualify row_number() over (
        partition by player_id
        order by game_date desc, game_id desc
    ) = 1

)

, results as (

    select * from {{ ref('live_nba__game_results') }}

)

select
    gs.game_date
    , gs.game_id
    , gs.player_id
    , gs.player_name
    , gs.team_id
    , gs.team_name
    , gs.season
    , gs.is_home
    , lr.season_game_number

    -- Actuals
    , gs.minutes_played
    , gs.pts
    , gs.reb
    , gs.ast
    , gs.stl
    , gs.blk
    , gs.turnovers
    , gs.pf
    , gs.fg_pct
    , gs.fg3_pct
    , gs.ft_pct
    , gs.game_score

    -- Game result context
    , res.home_spread
    , case
        when gs.is_home then res.home_spread_result
        else res.away_spread_result
      end                                            as spread_result

    -- Deltas vs L10 rolling average
    , gs.pts - lr.l10_avg_pts                        as pts_delta_l10
    , gs.reb - lr.l10_avg_reb                        as reb_delta_l10
    , gs.ast - lr.l10_avg_ast                        as ast_delta_l10
    , gs.stl - lr.l10_avg_stl                        as stl_delta_l10
    , gs.blk - lr.l10_avg_blk                        as blk_delta_l10
    , gs.turnovers - lr.l10_avg_turnovers            as turnovers_delta_l10
    , gs.pf - lr.l10_avg_pf                          as pf_delta_l10
    , gs.fg_pct - lr.l10_avg_fg_pct                  as fg_pct_delta_l10
    , gs.fg3_pct - lr.l10_avg_fg3_pct                as fg3_pct_delta_l10
    , gs.ft_pct - lr.l10_avg_ft_pct                  as ft_pct_delta_l10
    , gs.game_score - lr.l10_avg_game_score          as game_score_delta_l10
    , gs.minutes_played - lr.l10_avg_minutes_played  as minutes_delta_l10

    -- Deltas vs season average
    , gs.pts - lr.season_avg_pts                     as pts_delta_season
    , gs.reb - lr.season_avg_reb                     as reb_delta_season
    , gs.ast - lr.season_avg_ast                     as ast_delta_season
    , gs.stl - lr.season_avg_stl                     as stl_delta_season
    , gs.blk - lr.season_avg_blk                     as blk_delta_season
    , gs.turnovers - lr.season_avg_turnovers         as turnovers_delta_season
    , gs.pf - lr.season_avg_pf                       as pf_delta_season
    , gs.fg_pct - lr.season_avg_fg_pct               as fg_pct_delta_season
    , gs.fg3_pct - lr.season_avg_fg3_pct             as fg3_pct_delta_season
    , gs.ft_pct - lr.season_avg_ft_pct               as ft_pct_delta_season
    , gs.game_score - lr.season_avg_game_score       as game_score_delta_season
    , gs.minutes_played - lr.season_avg_minutes_played
                                                     as minutes_delta_season

    -- L10 averages for reference
    , lr.l10_avg_pts
    , lr.l10_avg_reb
    , lr.l10_avg_ast
    , lr.l10_avg_stl
    , lr.l10_avg_blk
    , lr.l10_avg_game_score
    , lr.l10_avg_fg_pct
    , lr.l10_avg_fg3_pct
    , lr.l10_avg_minutes_played

    -- Season averages for reference
    , lr.season_avg_pts
    , lr.season_avg_reb
    , lr.season_avg_ast
    , lr.season_avg_stl
    , lr.season_avg_blk
    , lr.season_avg_game_score
    , lr.season_avg_fg_pct
    , lr.season_avg_fg3_pct
    , lr.season_avg_minutes_played

    -- Overall grade: Hollinger Game Score delta vs L10
    , {{ performance_grade('gs.game_score - lr.l10_avg_game_score') }}
                                                     as performance_grade

from with_game_score as gs
left join latest_rolling as lr
    on gs.player_id = lr.player_id
left join results as res
    on gs.game_id = res.game_id
    and gs.game_date = res.game_date
where lr.l10_avg_game_score is not null
    and gs.minutes_played > 0
