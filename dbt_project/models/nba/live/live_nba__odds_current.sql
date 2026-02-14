-- Current live odds: per-bookmaker detail + consensus (median) aggregation.
-- Two CTEs so Streamlit can query either level.

with bookmaker_odds as (

    select
        event_id
        , game_date
        , home_team
        , away_team
        , commence_time_utc
        , bookmaker_key
        , bookmaker_title
        , bookmaker_last_update
        , market_key
        , outcome_name                        as side
        , outcome_price
        , outcome_point
        , {{ american_odds_to_implied_prob('outcome_price') }}
                                              as implied_probability
        , updated_at
    from {{ source('nba_live', 'live_nba_odds') }}

)

, consensus as (

    select
        event_id
        , game_date
        , home_team
        , away_team
        , commence_time_utc
        , market_key
        , side
        , count(distinct bookmaker_key)       as num_bookmakers
        , median(outcome_price)               as consensus_price
        , median(outcome_point)               as consensus_line
        , {{ american_odds_to_implied_prob('median(outcome_price)') }}
                                              as consensus_implied_prob
        , min(outcome_price)                  as best_price
        , max(outcome_price)                  as worst_price
    from bookmaker_odds
    group by
        event_id
        , game_date
        , home_team
        , away_team
        , commence_time_utc
        , market_key
        , side

)

-- Return per-bookmaker rows enriched with the consensus for that market
select
    bo.event_id
    , bo.game_date
    , bo.home_team
    , bo.away_team
    , bo.commence_time_utc
    , bo.bookmaker_key
    , bo.bookmaker_title
    , bo.bookmaker_last_update
    , bo.market_key
    , bo.side
    , bo.outcome_price
    , bo.outcome_point
    , bo.implied_probability
    , c.consensus_price
    , c.consensus_line
    , c.consensus_implied_prob
    , c.num_bookmakers
    , c.best_price
    , c.worst_price
    , bo.updated_at
from bookmaker_odds as bo
inner join consensus as c
    on bo.event_id = c.event_id
    and bo.market_key = c.market_key
    and bo.side = c.side
