{{
    config(
        materialized='table'
    )
}}

-- WAP audit table: today's batch of player rolling stats for quality checks
-- before publishing to the incremental production table.
-- Reads from stg_nba__player_box_scores with 30-day lookback
-- for window function context, outputs only yesterday's rows.
-- Grain: one row per (game_date, game_id, player_id).
-- Only includes players who logged minutes (DNP excluded).

with player_stats as (

    select * from {{ ref('stg_nba__player_box_scores') }}
    where minutes_played > 0
        and game_date >= current_date - 31

)

, with_game_score as (

    select
        *
        -- Hollinger's Game Score
        , pts + 0.4 * fgm - 0.7 * fga
          - 0.4 * (fta - ftm)
          + 0.7 * oreb + 0.3 * dreb
          + stl + 0.7 * ast + 0.7 * blk
          - 0.4 * pf - turnovers
                                              as game_score
        , row_number() over (
            partition by player_id, season
            order by game_date, game_id
        )                                     as season_game_number
    from player_stats

)

, rolling as (

    select
        game_date
        , game_id
        , player_id
        , player_name
        , team_id
        , team_name
        , season
        , is_home
        , season_game_number

        -- Current game actuals
        , minutes_played
        , pts
        , reb
        , oreb
        , dreb
        , ast
        , stl
        , blk
        , turnovers
        , pf
        , fgm
        , fga
        , fg3m
        , fg3a
        , ftm
        , fta
        , game_score

        -- Shooting pcts (computed here to avoid div-by-zero in averages)
        , {{ safe_divide('fgm', 'fga') }}    as fg_pct
        , {{ safe_divide('fg3m', 'fg3a') }}   as fg3_pct
        , {{ safe_divide('ftm', 'fta') }}     as ft_pct

        -- L10 rolling averages (last 10 games BEFORE this game)
        , avg(game_score) over (
            partition by player_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_game_score
        , avg(pts) over (
            partition by player_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_pts
        , avg(reb) over (
            partition by player_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_reb
        , avg(ast) over (
            partition by player_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_ast
        , avg(stl) over (
            partition by player_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_stl
        , avg(blk) over (
            partition by player_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_blk
        , avg(turnovers) over (
            partition by player_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_turnovers
        , avg(pf) over (
            partition by player_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_pf
        , avg({{ safe_divide('fgm', 'fga') }}) over (
            partition by player_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_fg_pct
        , avg({{ safe_divide('fg3m', 'fg3a') }}) over (
            partition by player_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_fg3_pct
        , avg({{ safe_divide('ftm', 'fta') }}) over (
            partition by player_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_ft_pct
        , avg(minutes_played) over (
            partition by player_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_minutes_played

        -- Season-to-date averages (all games BEFORE this game)
        , avg(game_score) over (
            partition by player_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_game_score
        , avg(pts) over (
            partition by player_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_pts
        , avg(reb) over (
            partition by player_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_reb
        , avg(ast) over (
            partition by player_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_ast
        , avg(stl) over (
            partition by player_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_stl
        , avg(blk) over (
            partition by player_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_blk
        , avg(turnovers) over (
            partition by player_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_turnovers
        , avg(pf) over (
            partition by player_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_pf
        , avg({{ safe_divide('fgm', 'fga') }}) over (
            partition by player_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_fg_pct
        , avg({{ safe_divide('fg3m', 'fg3a') }}) over (
            partition by player_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_fg3_pct
        , avg({{ safe_divide('ftm', 'fta') }}) over (
            partition by player_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_ft_pct
        , avg(minutes_played) over (
            partition by player_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_minutes_played

    from with_game_score

)

select *
from rolling
where game_date = current_date - 1
