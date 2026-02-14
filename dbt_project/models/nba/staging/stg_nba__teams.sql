with source as (

    select * from {{ source('nba_cold', 'hist_nba_teams') }}

)

select
    team_id
    , full_name
    , name                                    as short_name
    , city
    , abbreviation
    , conference
    , division
from source
