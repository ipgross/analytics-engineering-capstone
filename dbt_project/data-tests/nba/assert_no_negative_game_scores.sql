-- Ensure no completed game has negative scores.
-- Returns rows that violate the constraint (test passes if 0 rows).

select
    game_id
    , game_date
    , home_team_name
    , visitor_team_name
    , home_team_score
    , visitor_team_score
from {{ ref('stg_nba__games') }}
where home_team_score < 0
    or visitor_team_score < 0
