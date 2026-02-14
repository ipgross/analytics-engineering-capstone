-- depends_on: {{ ref('audit_int_nba__team_rolling_stats') }}

{{
    config(
        materialized='incremental',
        unique_key=['game_date', 'game_id', 'team_id'],
        incremental_strategy='merge'
    )
}}

-- Rolling averages per team: L10 (last 10 games) and season-to-date.
-- Window frames use "1 PRECEDING" to exclude the current game — these
-- represent what was known BEFORE the game was played.
-- Grain: one row per (game_date, game_id, team_id).
-- WAP: incremental runs publish from audit table; full refresh rebuilds from source.

{% if is_incremental() %}

select * from {{ ref('audit_int_nba__team_rolling_stats') }}

{% else %}

with team_stats as (

    select * from {{ ref('int_nba__team_game_stats') }}

)

, with_game_number as (

    select
        *
        , row_number() over (
            partition by team_id, season
            order by game_date, game_id
        )                                     as season_game_number
        , datediff('day',
            lag(game_date) over (
                partition by team_id, season
                order by game_date, game_id
            ),
            game_date
        )                                     as rest_days
    from team_stats

)

, rolling as (

    select
        game_date
        , game_id
        , team_id
        , team_name
        , season
        , is_home
        , opp_team_id
        , opp_team_name
        , season_game_number

        -- Current game actuals
        , pts
        , opp_pts
        , reb
        , oreb
        , dreb
        , ast
        , turnovers
        , stl
        , blk
        , pf
        , fgm
        , fga
        , fg_pct
        , fg3m
        , fg3a
        , fg3_pct
        , ftm
        , fta
        , ft_pct
        , est_possessions
        , efg_pct
        , tov_pct
        , orb_pct
        , ftr
        , off_rating
        , def_rating
        , opp_efg_pct
        , opp_tov_pct
        , opp_orb_pct
        , opp_ftr
        , score_margin
        , total_points
        , rest_days

        -- L10 rolling averages (last 10 games BEFORE this game)
        , avg(pts) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_pts
        , avg(opp_pts) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_opp_pts
        , avg(reb) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_reb
        , avg(ast) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_ast
        , avg(turnovers) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_turnovers
        , avg(stl) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_stl
        , avg(blk) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_blk
        , avg(fg_pct) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_fg_pct
        , avg(fg3_pct) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_fg3_pct
        , avg(ft_pct) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_ft_pct
        , avg(est_possessions) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_possessions
        , avg(off_rating) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_off_rating
        , avg(def_rating) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_def_rating
        , avg(pf) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_pf

        -- Four Factors L10 rolling
        , avg(efg_pct) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_efg_pct
        , avg(tov_pct) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_tov_pct
        , avg(orb_pct) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_orb_pct
        , avg(ftr) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_ftr

        -- Opponent Four Factors L10 (what opponents shoot against this team's defense)
        , avg(opp_efg_pct) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_opp_efg_pct
        , avg(opp_tov_pct) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_opp_tov_pct
        , avg(opp_orb_pct) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_opp_orb_pct
        , avg(opp_ftr) over (
            partition by team_id, season
            order by game_date, game_id
            rows between {{ var('nba_rolling_window') }} preceding
                and 1 preceding
        )                                     as l10_avg_opp_ftr

        -- Season-to-date averages (all games BEFORE this game)
        , avg(pts) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_pts
        , avg(opp_pts) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_opp_pts
        , avg(reb) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_reb
        , avg(ast) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_ast
        , avg(turnovers) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_turnovers
        , avg(stl) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_stl
        , avg(blk) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_blk
        , avg(fg_pct) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_fg_pct
        , avg(fg3_pct) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_fg3_pct
        , avg(ft_pct) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_ft_pct
        , avg(est_possessions) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_possessions
        , avg(off_rating) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_off_rating
        , avg(def_rating) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_def_rating
        , avg(pf) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_pf

        -- Four Factors season averages
        , avg(efg_pct) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_efg_pct
        , avg(tov_pct) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_tov_pct
        , avg(orb_pct) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_orb_pct
        , avg(ftr) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_ftr

        -- Opponent Four Factors season averages
        , avg(opp_efg_pct) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_opp_efg_pct
        , avg(opp_tov_pct) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_opp_tov_pct
        , avg(opp_orb_pct) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_opp_orb_pct
        , avg(opp_ftr) over (
            partition by team_id, season
            order by game_date, game_id
            rows between unbounded preceding and 1 preceding
        )                                     as season_avg_opp_ftr

    from with_game_number

)

select * from rolling

{% endif %}
