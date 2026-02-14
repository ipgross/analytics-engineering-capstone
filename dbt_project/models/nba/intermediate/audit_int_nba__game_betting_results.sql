{{
    config(
        materialized='table'
    )
}}

-- WAP audit table: today's batch of game betting results for quality checks
-- before publishing to the incremental production table.
-- Grain: one row per (game_date, game_id, market_key, side).
-- Links Odds API to BDL via (game_date, home_team) natural key.

with games as (

    select * from {{ ref('stg_nba__games') }}
    where game_date = current_date - 1

)

, events as (

    select * from {{ ref('stg_nba__events') }}
    where not is_postponed

)

, consensus as (

    select * from {{ ref('int_nba__consensus_lines') }}

)

, games_with_event as (

    select
        g.game_date
        , g.game_id
        , e.event_id
        , g.season
        , g.home_team_name
        , g.visitor_team_name
        , g.home_team_score
        , g.visitor_team_score
        , g.score_margin
        , g.total_points
        , g.is_postseason
    from games as g
    inner join events as e
        on g.game_date = e.game_date
        and g.home_team_name = e.home_team

)

, with_odds as (

    select
        gwe.game_date
        , gwe.game_id
        , gwe.event_id
        , gwe.season
        , gwe.home_team_name
        , gwe.visitor_team_name
        , gwe.home_team_score
        , gwe.visitor_team_score
        , gwe.score_margin
        , gwe.total_points
        , gwe.is_postseason
        , cl.market_key
        , cl.side
        , cl.consensus_line
        , cl.consensus_price
        , cl.consensus_implied_prob
        , cl.num_bookmakers
        , cl.best_price
        , case
            -- SPREAD: team covers if actual margin from their perspective
            -- beats the line
            when cl.market_key = 'spreads'
                and cl.side = gwe.home_team_name
                then case
                    when gwe.score_margin + cl.consensus_line > 0
                        then 'COVERED'
                    when gwe.score_margin + cl.consensus_line = 0
                        then 'PUSH'
                    else 'MISSED'
                end
            when cl.market_key = 'spreads'
                and cl.side = gwe.visitor_team_name
                then case
                    when -gwe.score_margin + cl.consensus_line > 0
                        then 'COVERED'
                    when -gwe.score_margin + cl.consensus_line = 0
                        then 'PUSH'
                    else 'MISSED'
                end
            -- MONEYLINE (h2h): team covers if they win
            when cl.market_key = 'h2h'
                and cl.side = gwe.home_team_name
                then case
                    when gwe.score_margin > 0 then 'COVERED'
                    else 'MISSED'
                end
            when cl.market_key = 'h2h'
                and cl.side = gwe.visitor_team_name
                then case
                    when gwe.score_margin < 0 then 'COVERED'
                    else 'MISSED'
                end
            -- TOTALS: Over covers if total > line
            when cl.market_key = 'totals'
                and cl.side = 'Over'
                then case
                    when gwe.total_points > cl.consensus_line
                        then 'COVERED'
                    when gwe.total_points = cl.consensus_line
                        then 'PUSH'
                    else 'MISSED'
                end
            when cl.market_key = 'totals'
                and cl.side = 'Under'
                then case
                    when gwe.total_points < cl.consensus_line
                        then 'COVERED'
                    when gwe.total_points = cl.consensus_line
                        then 'PUSH'
                    else 'MISSED'
                end
        end                                   as cover_result
    from games_with_event as gwe
    inner join consensus as cl
        on gwe.event_id = cl.event_id
        and gwe.game_date = cl.game_date

)

select * from with_odds
