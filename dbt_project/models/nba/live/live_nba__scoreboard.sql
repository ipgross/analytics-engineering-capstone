select
    game_id
    , game_date
    , season
    , status
    , period
    , clock
    , game_datetime
    , home_team_id
    , home_team_name
    , home_team_score
    , home_q1
    , home_q2
    , home_q3
    , home_q4
    , home_ot1
    , home_ot2
    , home_ot3
    , home_timeouts_remaining
    , home_in_bonus
    , visitor_team_id
    , visitor_team_name
    , visitor_team_score
    , visitor_q1
    , visitor_q2
    , visitor_q3
    , visitor_q4
    , visitor_ot1
    , visitor_ot2
    , visitor_ot3
    , visitor_timeouts_remaining
    , visitor_in_bonus
    , postseason
    , postponed
    , updated_at
from {{ source('nba_live', 'live_nba_scoreboard') }}
