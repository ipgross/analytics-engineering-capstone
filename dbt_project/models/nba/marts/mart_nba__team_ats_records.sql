{{ config(materialized='table') }}

-- Team ATS (Against the Spread), SU (Straight Up), and O/U records
-- with home/away splits and rankings.
-- Grain: one row per (season, team_name).
-- Rebuilt daily (~90 rows across 3 seasons).

with spread_results as (

    select *
    from {{ ref('int_nba__game_betting_results') }}
    where market_key = 'spreads'

)

, ml_results as (

    select *
    from {{ ref('int_nba__game_betting_results') }}
    where market_key = 'h2h'

)

, total_results as (

    select *
    from {{ ref('int_nba__game_betting_results') }}
    where market_key = 'totals'
        and side = 'Over'

)

, games as (

    select * from {{ ref('stg_nba__games') }}

)

-- Build team-centric view: each game appears twice (home + away)
, team_games as (

    select
        g.season
        , g.home_team_name                    as team_name
        , 'home'                              as venue
        , g.game_id
        , g.game_date
        , case when g.score_margin > 0 then 1 else 0 end
                                              as su_win
        , case when g.score_margin < 0 then 1 else 0 end
                                              as su_loss
    from games as g

    union all

    select
        g.season
        , g.visitor_team_name                 as team_name
        , 'away'                              as venue
        , g.game_id
        , g.game_date
        , case when g.score_margin < 0 then 1 else 0 end
                                              as su_win
        , case when g.score_margin > 0 then 1 else 0 end
                                              as su_loss
    from games as g

)

, with_spreads as (

    select
        tg.*
        , sr.cover_result                     as ats_result
    from team_games as tg
    left join spread_results as sr
        on tg.game_id = sr.game_id
        and tg.game_date = sr.game_date
        and tg.team_name = sr.side

)

, with_totals as (

    select
        ws.*
        , tr.cover_result                     as ou_result
    from with_spreads as ws
    left join total_results as tr
        on ws.game_id = tr.game_id
        and ws.game_date = tr.game_date

)

, team_records as (

    select
        season
        , team_name
        -- Games played
        , count(*)                                as games_played
        -- Overall SU
        , sum(su_win)                             as su_wins
        , sum(su_loss)                            as su_losses
        , {{ safe_divide('sum(su_win)', 'count(*)') }}
                                                  as su_pct
        -- Home SU
        , sum(case when venue = 'home' then su_win end)
                                                  as home_su_wins
        , sum(case when venue = 'home' then su_loss end)
                                                  as home_su_losses
        -- Away SU
        , sum(case when venue = 'away' then su_win end)
                                                  as away_su_wins
        , sum(case when venue = 'away' then su_loss end)
                                                  as away_su_losses
        -- Overall ATS
        , count_if(ats_result = 'COVERED')        as ats_wins
        , count_if(ats_result = 'MISSED')         as ats_losses
        , count_if(ats_result = 'PUSH')           as ats_pushes
        , {{ safe_divide(
            "count_if(ats_result = 'COVERED')",
            "count_if(ats_result in ('COVERED', 'MISSED'))"
        ) }}                                      as ats_pct
        -- Home ATS
        , count_if(venue = 'home' and ats_result = 'COVERED')
                                                  as home_ats_wins
        , count_if(venue = 'home' and ats_result = 'MISSED')
                                                  as home_ats_losses
        , count_if(venue = 'home' and ats_result = 'PUSH')
                                                  as home_ats_pushes
        -- Away ATS
        , count_if(venue = 'away' and ats_result = 'COVERED')
                                                  as away_ats_wins
        , count_if(venue = 'away' and ats_result = 'MISSED')
                                                  as away_ats_losses
        , count_if(venue = 'away' and ats_result = 'PUSH')
                                                  as away_ats_pushes
        -- Overall O/U
        , count_if(ou_result = 'COVERED')         as over_wins
        , count_if(ou_result = 'MISSED')          as under_wins
        , count_if(ou_result = 'PUSH')            as ou_pushes
    from with_totals
    group by season, team_name

)

select
    *
    , rank() over (
        partition by season order by ats_pct desc
    )                                         as ats_rank
    , rank() over (
        partition by season order by su_pct desc
    )                                         as su_rank
from team_records
