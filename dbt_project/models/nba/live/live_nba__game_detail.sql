-- Combined game detail view: scoreboard + team box scores + consensus odds.
-- Powers the Game Detail page in Streamlit.

with scoreboard as (

    select * from {{ ref('live_nba__scoreboard') }}

)

, home_box as (

    select * from {{ ref('live_nba__team_box_scores') }}
    where is_home = true

)

, away_box as (

    select * from {{ ref('live_nba__team_box_scores') }}
    where is_home = false

)

, consensus_spreads as (

    select
        event_id
        , game_date
        , home_team
        , consensus_line
        , consensus_price
        , consensus_implied_prob
    from {{ ref('live_nba__odds_current') }}
    where market_key = 'spreads'
        and side = home_team
    qualify row_number() over (
        partition by home_team, game_date
        order by event_id desc
    ) = 1

)

select
    s.game_id
    , s.game_date
    , s.season
    , s.status
    , s.period
    , s.clock
    , s.game_datetime
    , s.home_team_name
    , s.visitor_team_name
    , s.home_team_score
    , s.visitor_team_score
    , s.home_q1
    , s.home_q2
    , s.home_q3
    , s.home_q4
    , s.visitor_q1
    , s.visitor_q2
    , s.visitor_q3
    , s.visitor_q4
    -- Home team box
    , hb.pts                                  as home_pts
    , hb.fg_pct                               as home_fg_pct
    , hb.fg3_pct                              as home_fg3_pct
    , hb.reb                                  as home_reb
    , hb.ast                                  as home_ast
    , hb.turnovers                            as home_turnovers
    , hb.stl                                  as home_stl
    , hb.blk                                  as home_blk
    , hb.est_possessions                      as home_possessions
    -- Away team box
    , ab.pts                                  as away_pts
    , ab.fg_pct                               as away_fg_pct
    , ab.fg3_pct                              as away_fg3_pct
    , ab.reb                                  as away_reb
    , ab.ast                                  as away_ast
    , ab.turnovers                            as away_turnovers
    , ab.stl                                  as away_stl
    , ab.blk                                  as away_blk
    , ab.est_possessions                      as away_possessions
    -- Consensus spread
    , cs.consensus_line                       as home_spread
    , cs.consensus_price                      as home_spread_price
    , cs.consensus_implied_prob               as home_spread_implied_prob
    , s.updated_at
from scoreboard as s
left join home_box as hb
    on s.game_id = hb.game_id
left join away_box as ab
    on s.game_id = ab.game_id
left join consensus_spreads as cs
    on s.home_team_name = cs.home_team
    and s.game_date = cs.game_date
