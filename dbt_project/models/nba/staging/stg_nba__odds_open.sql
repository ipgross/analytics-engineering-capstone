with source as (

    select * from {{ source('nba_cold', 'hist_nba_odds_open') }}

)

select
    ds                                        as game_date
    , event_id
    , season
    , home_team
    , away_team
    , max(commence_time_utc) over (partition by ds, event_id)
                                              as commence_time_utc
    , max(commence_time_et) over (partition by ds, event_id)
                                              as commence_time_et
    , bookmaker_key
    , bookmaker_title
    , bookmaker_last_update
    , market_key
    , outcome_name
    , outcome_price
    , outcome_point
    , {{ american_odds_to_implied_prob('outcome_price') }}
                                              as implied_probability
    , ingested_at
from source
qualify row_number() over (
    partition by ds, event_id, bookmaker_key, market_key, outcome_name
    order by ingested_at desc
) = 1
