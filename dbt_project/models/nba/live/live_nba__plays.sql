select
    game_id
    , play_id
    , period
    , period_display
    , clock
    , action_type
    , description
    , team_id
    , team_name
    , scoring_play
    , shooting_play
    , score_value
    , home_score
    , away_score
    , coordinate_x
    , coordinate_y
    , updated_at
from {{ source('nba_live', 'live_nba_plays') }}
