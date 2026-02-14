with source as (

    select * from {{ source('nba_cold', 'hist_nba_events') }}

)

select
    ds                                        as game_date
    , event_id
    , season
    , sport_key
    , commence_time_utc
    , commence_time_et
    , home_team
    , away_team
    , coalesce(postponed, false)              as is_postponed
    , ingested_at
from source
