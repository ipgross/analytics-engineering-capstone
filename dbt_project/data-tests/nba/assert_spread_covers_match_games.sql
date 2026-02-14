-- For each game_date, the number of spread outcomes should equal
-- 2x the number of games (one home side + one away side per game).
-- Returns dates where the counts don't match.

with game_counts as (

    select
        game_date
        , count(*)                            as games
    from {{ ref('stg_nba__games') }}
    group by game_date

)

, cover_counts as (

    select
        game_date
        , count(*)                            as spread_outcomes
    from {{ ref('int_nba__game_betting_results') }}
    where market_key = 'spreads'
    group by game_date

)

select
    gc.game_date
    , gc.games
    , cc.spread_outcomes
from game_counts as gc
inner join cover_counts as cc
    on gc.game_date = cc.game_date
where cc.spread_outcomes != gc.games * 2
