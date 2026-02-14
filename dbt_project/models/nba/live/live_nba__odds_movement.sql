-- Line movement data from archive snapshots for chart visualization.
-- One row per snapshot per bookmaker per market per outcome.

select
    snapshot_time
    , event_id
    , game_date
    , home_team
    , away_team
    , commence_time_utc
    , bookmaker_key
    , bookmaker_title
    , market_key
    , outcome_name                            as side
    , outcome_price
    , outcome_point
    , {{ american_odds_to_implied_prob('outcome_price') }}
                                              as implied_probability
from {{ source('nba_live', 'archive_nba_odds_snapshots') }}
