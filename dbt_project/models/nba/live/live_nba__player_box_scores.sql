select
    game_id
    , player_id
    , player_name
    , team_id
    , team_name
    , is_home
    , game_date
    , season
    , status
    , min
    , pts
    , reb
    , oreb
    , dreb
    , ast
    , stl
    , blk
    , turnover                                as turnovers
    , pf
    , fgm
    , fga
    , fg_pct
    , fg3m
    , fg3a
    , fg3_pct
    , ftm
    , fta
    , ft_pct
    , updated_at
from {{ source('nba_live', 'live_nba_player_box_scores') }}
