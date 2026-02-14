{{
    config(
        materialized='table'
    )
}}

-- WAP audit table: today's batch of game results for quality checks
-- before publishing to the incremental production table.
-- Grain: one row per (game_date, game_id).

with games as (

    select * from {{ ref('stg_nba__games') }}
    where game_date = current_date - 1

)

, spreads as (

    select *
    from {{ ref('int_nba__game_betting_results') }}
    where market_key = 'spreads'

)

, totals_over as (

    select *
    from {{ ref('int_nba__game_betting_results') }}
    where market_key = 'totals'
        and side = 'Over'

)

, h2h as (

    select *
    from {{ ref('int_nba__game_betting_results') }}
    where market_key = 'h2h'

)

select
    g.game_date
    , g.game_id
    , g.season
    , g.home_team_name
    , g.visitor_team_name
    , g.home_team_score
    , g.visitor_team_score
    , g.score_margin
    , g.total_points
    , g.is_postseason
    , case
        when g.score_margin > 0 then g.home_team_name
        when g.score_margin < 0 then g.visitor_team_name
        else 'TIE'
      end                                     as winner
    -- Spread
    , sh.consensus_line                       as home_spread
    , sh.consensus_price                      as home_spread_price
    , sh.cover_result                         as home_spread_result
    , sa.consensus_line                       as away_spread
    , sa.consensus_price                      as away_spread_price
    , sa.cover_result                         as away_spread_result
    -- Total
    , t.consensus_line                        as total_line
    , t.consensus_price                       as over_price
    , t.cover_result                          as over_result
    -- Moneyline
    , h2h_h.consensus_price                   as home_ml_price
    , h2h_h.consensus_implied_prob            as home_ml_implied_prob
    , h2h_h.cover_result                      as home_ml_result
    , h2h_a.consensus_price                   as away_ml_price
    , h2h_a.consensus_implied_prob            as away_ml_implied_prob
    , h2h_a.cover_result                      as away_ml_result
from games as g
left join spreads as sh
    on g.game_id = sh.game_id
    and g.game_date = sh.game_date
    and sh.side = g.home_team_name
left join spreads as sa
    on g.game_id = sa.game_id
    and g.game_date = sa.game_date
    and sa.side = g.visitor_team_name
left join totals_over as t
    on g.game_id = t.game_id
    and g.game_date = t.game_date
left join h2h as h2h_h
    on g.game_id = h2h_h.game_id
    and g.game_date = h2h_h.game_date
    and h2h_h.side = g.home_team_name
left join h2h as h2h_a
    on g.game_id = h2h_a.game_id
    and g.game_date = h2h_a.game_date
    and h2h_a.side = g.visitor_team_name
