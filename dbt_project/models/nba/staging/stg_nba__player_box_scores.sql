with source as (

    select * from {{ source('nba_cold', 'hist_nba_player_box_scores') }}

)

select
    ds                                        as game_date
    , game_id
    , player_id
    , player_name
    , team_id
    , team_name
    , season::varchar || '-' || right((season + 1)::varchar, 2)
                                              as season
    , is_home
    , {{ parse_minutes('min') }}              as minutes_played
    , coalesce(pts, 0)                        as pts
    , coalesce(reb, 0)                        as reb
    , coalesce(oreb, 0)                       as oreb
    , coalesce(dreb, 0)                       as dreb
    , coalesce(ast, 0)                        as ast
    , coalesce(stl, 0)                        as stl
    , coalesce(blk, 0)                        as blk
    , coalesce(turnover, 0)                   as turnovers
    , coalesce(pf, 0)                         as pf
    , coalesce(fgm, 0)                        as fgm
    , coalesce(fga, 0)                        as fga
    , coalesce(fg3m, 0)                       as fg3m
    , coalesce(fg3a, 0)                       as fg3a
    , coalesce(ftm, 0)                        as ftm
    , coalesce(fta, 0)                        as fta
    , ingested_at
from source
