-- depends_on: {{ ref('audit_int_nba__consensus_lines') }}

{{
    config(
        materialized='incremental',
        unique_key=['game_date', 'event_id', 'market_key', 'side'],
        incremental_strategy='merge'
    )
}}

-- Computes consensus (median) line across all bookmakers per game/market/side.
-- Grain: one row per (game_date, event_id, market_key, side).
-- "side" is: team name (h2h/spreads) or Over/Under (totals).
-- WAP: incremental runs publish from audit table; full refresh rebuilds from source.

{% if is_incremental() %}

select * from {{ ref('audit_int_nba__consensus_lines') }}

{% else %}

with odds as (

    select * from {{ ref('stg_nba__odds_open') }}

)

select
    game_date
    , event_id
    , max(season)                             as season
    , max(home_team)                          as home_team
    , max(away_team)                          as away_team
    , max(commence_time_utc)                  as commence_time_utc
    , max(commence_time_et)                   as commence_time_et
    , market_key
    , outcome_name                            as side
    , count(distinct bookmaker_key)           as num_bookmakers
    , median(outcome_price)                   as consensus_price
    , median(outcome_point)                   as consensus_line
    , min(outcome_price)                      as best_price
    , max(outcome_price)                      as worst_price
    , min(outcome_point)                      as min_line
    , max(outcome_point)                      as max_line
    , median(implied_probability)             as consensus_implied_prob
from odds
group by
    game_date
    , event_id
    , market_key
    , outcome_name

{% endif %}
