-- Live game results: betting outcomes for Final games.
-- Mirrors mart_nba__game_results using live scoreboard + live odds.
-- Grain: one row per game_id (Final games only).
-- Always fresh — reads directly from hot-path views.

with scoreboard as (

    select
        game_id
        , game_date
        , season
        , home_team_name
        , visitor_team_name
        , home_team_score
        , visitor_team_score
        , home_team_score - visitor_team_score       as score_margin
        , home_team_score + visitor_team_score       as total_points
        , postseason                                 as is_postseason
    from {{ ref('live_nba__scoreboard') }}
    where status = 'Final'

)

-- One row per (event_id, market_key, side) with consensus data only
, consensus as (

    select distinct
        event_id
        , game_date
        , home_team
        , away_team
        , market_key
        , side
        , consensus_price
        , consensus_line
        , consensus_implied_prob
    from {{ ref('live_nba__odds_current') }}

)

, spreads_home as (

    select *
    from consensus
    where market_key = 'spreads'
        and side = home_team
    qualify row_number() over (
        partition by home_team, game_date
        order by event_id desc
    ) = 1

)

, spreads_away as (

    select *
    from consensus
    where market_key = 'spreads'
        and side = away_team
    qualify row_number() over (
        partition by away_team, game_date
        order by event_id desc
    ) = 1

)

, totals_over as (

    select *
    from consensus
    where market_key = 'totals'
        and side = 'Over'
    qualify row_number() over (
        partition by home_team, game_date
        order by event_id desc
    ) = 1

)

, h2h_home as (

    select *
    from consensus
    where market_key = 'h2h'
        and side = home_team
    qualify row_number() over (
        partition by home_team, game_date
        order by event_id desc
    ) = 1

)

, h2h_away as (

    select *
    from consensus
    where market_key = 'h2h'
        and side = away_team
    qualify row_number() over (
        partition by away_team, game_date
        order by event_id desc
    ) = 1

)

select
    s.game_date
    , s.game_id
    , s.season
    , s.home_team_name
    , s.visitor_team_name
    , s.home_team_score
    , s.visitor_team_score
    , s.score_margin
    , s.total_points
    , s.is_postseason
    , case
        when s.score_margin > 0 then s.home_team_name
        when s.score_margin < 0 then s.visitor_team_name
        else 'TIE'
      end                                            as winner
    -- Spread
    , sh.consensus_line                              as home_spread
    , sh.consensus_price                             as home_spread_price
    , case
        when sh.consensus_line is null then null
        when s.score_margin + sh.consensus_line > 0 then 'COVERED'
        when s.score_margin + sh.consensus_line = 0 then 'PUSH'
        else 'MISSED'
      end                                            as home_spread_result
    , sa.consensus_line                              as away_spread
    , sa.consensus_price                             as away_spread_price
    , case
        when sa.consensus_line is null then null
        when -s.score_margin + sa.consensus_line > 0 then 'COVERED'
        when -s.score_margin + sa.consensus_line = 0 then 'PUSH'
        else 'MISSED'
      end                                            as away_spread_result
    -- Total
    , t.consensus_line                               as total_line
    , t.consensus_price                              as over_price
    , case
        when t.consensus_line is null then null
        when s.total_points > t.consensus_line then 'COVERED'
        when s.total_points = t.consensus_line then 'PUSH'
        else 'MISSED'
      end                                            as over_result
    -- Moneyline
    , hh.consensus_price                             as home_ml_price
    , hh.consensus_implied_prob                      as home_ml_implied_prob
    , case
        when hh.consensus_price is null then null
        when s.score_margin > 0 then 'COVERED'
        else 'MISSED'
      end                                            as home_ml_result
    , ha.consensus_price                             as away_ml_price
    , ha.consensus_implied_prob                      as away_ml_implied_prob
    , case
        when ha.consensus_price is null then null
        when s.score_margin < 0 then 'COVERED'
        else 'MISSED'
      end                                            as away_ml_result
from scoreboard as s
left join spreads_home as sh
    on s.home_team_name = sh.home_team
    and s.game_date = sh.game_date
left join spreads_away as sa
    on s.visitor_team_name = sa.away_team
    and s.game_date = sa.game_date
left join totals_over as t
    on s.home_team_name = t.home_team
    and s.game_date = t.game_date
left join h2h_home as hh
    on s.home_team_name = hh.home_team
    and s.game_date = hh.game_date
left join h2h_away as ha
    on s.visitor_team_name = ha.away_team
    and s.game_date = ha.game_date
