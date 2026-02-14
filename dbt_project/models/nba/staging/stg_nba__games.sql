with source as (

    select *
    from {{ source('nba_cold', 'hist_nba_games') }}
    where status = 'Final'

)

select
    ds                                        as game_date
    , game_id
    , season
    , status
    , home_team_id
    , home_team_name
    , home_team_score
    , visitor_team_id
    , visitor_team_name
    , visitor_team_score
    , home_team_score - visitor_team_score     as score_margin
    , home_team_score + visitor_team_score     as total_points
    , coalesce(postseason, false)             as is_postseason
    , ingested_at
from source
