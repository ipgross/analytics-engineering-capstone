{{ config(materialized='table') }}

-- WAP audit table: current batch of game predictions for quality checks
-- before publishing to the incremental production table.
-- Computes predictions for all unplayed games across all 3 markets.
-- Grain: one row per (event_id, market_key, side).

with upcoming_events as (

    select
        game_date
        , event_id
        , season
        , home_team
        , away_team
        , commence_time_utc
        , commence_time_et
    from {{ ref('stg_nba__events') }}
    where not is_postponed
        and event_id not in (
            select distinct event_id
            from {{ ref('int_nba__game_betting_results') }}
        )

)

, consensus as (

    select * from {{ ref('int_nba__consensus_lines') }}

)

-- Most recent rolling stats per team (latest game played)
, latest_rolling as (

    select *
    from {{ ref('int_nba__team_rolling_stats') }}
    qualify row_number() over (
        partition by team_id, season
        order by game_date desc, game_id desc
    ) = 1

)

, ats_records as (

    select * from {{ ref('mart_nba__team_ats_records') }}

)

-- One row per upcoming event with team context
, predictions_base as (

    select
        ue.game_date
        , ue.event_id
        , ue.season
        , ue.home_team
        , ue.away_team
        , ue.commence_time_utc
        , ue.commence_time_et
        -- Projected scores: blend of (team off + opp def allowed) / 2
        , (
            coalesce(hr.l10_avg_pts, hr.season_avg_pts)
            + coalesce(ar.l10_avg_opp_pts, ar.season_avg_opp_pts)
          ) / 2.0                             as projected_home_score
        , (
            coalesce(ar.l10_avg_pts, ar.season_avg_pts)
            + coalesce(hr.l10_avg_opp_pts, hr.season_avg_opp_pts)
          ) / 2.0                             as projected_away_score
        -- Home team rolling context
        , hr.l10_avg_pts                      as home_l10_pts
        , hr.l10_avg_off_rating               as home_l10_off_rating
        , hr.l10_avg_def_rating               as home_l10_def_rating
        , hr.season_avg_off_rating            as home_season_off_rating
        -- Away team rolling context
        , ar.l10_avg_pts                      as away_l10_pts
        , ar.l10_avg_off_rating               as away_l10_off_rating
        , ar.l10_avg_def_rating               as away_l10_def_rating
        , ar.season_avg_off_rating            as away_season_off_rating
        -- Home Four Factors L10 (offense)
        , hr.l10_avg_efg_pct                  as home_l10_efg_pct
        , hr.l10_avg_tov_pct                  as home_l10_tov_pct
        , hr.l10_avg_orb_pct                  as home_l10_orb_pct
        , hr.l10_avg_ftr                      as home_l10_ftr
        -- Home opponent Four Factors L10 (defense — what opponents do against home)
        , hr.l10_avg_opp_efg_pct              as home_l10_opp_efg_pct
        , hr.l10_avg_opp_tov_pct              as home_l10_opp_tov_pct
        , hr.l10_avg_opp_orb_pct              as home_l10_opp_orb_pct
        , hr.l10_avg_opp_ftr                  as home_l10_opp_ftr
        -- Away Four Factors L10 (offense)
        , ar.l10_avg_efg_pct                  as away_l10_efg_pct
        , ar.l10_avg_tov_pct                  as away_l10_tov_pct
        , ar.l10_avg_orb_pct                  as away_l10_orb_pct
        , ar.l10_avg_ftr                      as away_l10_ftr
        -- Away opponent Four Factors L10 (defense — what opponents do against away)
        , ar.l10_avg_opp_efg_pct              as away_l10_opp_efg_pct
        , ar.l10_avg_opp_tov_pct              as away_l10_opp_tov_pct
        , ar.l10_avg_opp_orb_pct              as away_l10_opp_orb_pct
        , ar.l10_avg_opp_ftr                  as away_l10_opp_ftr
        -- Rest days: days since each team's last game
        , datediff('day', hr.game_date, ue.game_date)
                                              as home_rest_days
        , datediff('day', ar.game_date, ue.game_date)
                                              as away_rest_days
        -- Pace (for totals)
        , hr.l10_avg_possessions              as home_l10_possessions
        , ar.l10_avg_possessions              as away_l10_possessions
        -- ATS records
        , hats.ats_wins                       as home_ats_wins
        , hats.ats_losses                     as home_ats_losses
        , hats.ats_pushes                     as home_ats_pushes
        , hats.ats_pct                        as home_ats_pct
        , aats.ats_wins                       as away_ats_wins
        , aats.ats_losses                     as away_ats_losses
        , aats.ats_pushes                     as away_ats_pushes
        , aats.ats_pct                        as away_ats_pct
        -- SU records
        , hats.su_wins                        as home_su_wins
        , hats.su_losses                      as home_su_losses
        , hats.su_pct                         as home_su_pct
        , aats.su_wins                        as away_su_wins
        , aats.su_losses                      as away_su_losses
        , aats.su_pct                         as away_su_pct
        -- O/U records
        , hats.over_wins                      as home_over_wins
        , hats.under_wins                     as home_under_wins
        , hats.ou_pushes                      as home_ou_pushes
        , aats.over_wins                      as away_over_wins
        , aats.under_wins                     as away_under_wins
    from upcoming_events as ue
    left join latest_rolling as hr
        on ue.home_team = hr.team_name
        and ue.season = hr.season
    left join latest_rolling as ar
        on ue.away_team = ar.team_name
        and ue.season = ar.season
    left join ats_records as hats
        on ue.home_team = hats.team_name
        and ue.season = hats.season
    left join ats_records as aats
        on ue.away_team = aats.team_name
        and ue.season = aats.season

)

-- =====================================================================
-- SPREADS: composite of projected edge, Four Factors matchup, rest, ATS
-- =====================================================================
, spread_base as (

    select
        pb.game_date
        , pb.event_id
        , pb.season
        , pb.home_team
        , pb.away_team
        , pb.commence_time_utc
        , pb.commence_time_et
        , pb.projected_home_score
        , pb.projected_away_score
        , pb.projected_home_score + pb.projected_away_score
                                              as projected_total
        , 'spreads'                           as market_key
        , cl.side
        , cl.consensus_line
        , cl.consensus_price
        , cl.consensus_implied_prob
        , cl.num_bookmakers
        , cl.best_price
        -- Composite cover probability (research-backed)
        , greatest(0.30, least(0.70,
            0.50
            -- Signal 1: Projected edge vs spread (strongest actionable signal)
            -- Each point of edge ~ +1.5% cover prob, capped +/-12%
            + greatest(-0.12, least(0.12,
                (case when cl.side = pb.home_team
                    then (pb.projected_home_score - pb.projected_away_score)
                         + cl.consensus_line
                    else (pb.projected_away_score - pb.projected_home_score)
                         + cl.consensus_line
                end) * 0.015
            ))
            -- Signal 2: Four Factors matchup (Oliver: eFG 40%, TO 25%, ORB 20%, FTR 15%)
            -- Compares side's offensive efficiency vs opponent's defensive efficiency
            + (case when cl.side = pb.home_team then
                  0.40 * (coalesce(pb.home_l10_efg_pct, 0.50)
                        - coalesce(pb.away_l10_opp_efg_pct, 0.50)) / 0.04
                + 0.25 * (coalesce(pb.away_l10_opp_tov_pct, 0.14)
                        - coalesce(pb.home_l10_tov_pct, 0.14)) / 0.03
                + 0.20 * (coalesce(pb.home_l10_orb_pct, 0.25)
                        - coalesce(pb.away_l10_opp_orb_pct, 0.25)) / 0.05
                + 0.15 * (coalesce(pb.home_l10_ftr, 0.25)
                        - coalesce(pb.away_l10_opp_ftr, 0.25)) / 0.05
              else
                  0.40 * (coalesce(pb.away_l10_efg_pct, 0.50)
                        - coalesce(pb.home_l10_opp_efg_pct, 0.50)) / 0.04
                + 0.25 * (coalesce(pb.home_l10_opp_tov_pct, 0.14)
                        - coalesce(pb.away_l10_tov_pct, 0.14)) / 0.03
                + 0.20 * (coalesce(pb.away_l10_orb_pct, 0.25)
                        - coalesce(pb.home_l10_opp_orb_pct, 0.25)) / 0.05
                + 0.15 * (coalesce(pb.away_l10_ftr, 0.25)
                        - coalesce(pb.home_l10_opp_ftr, 0.25)) / 0.05
              end) * 0.08
            -- Signal 3: Rest day adjustment (~1pt defensive penalty on back-to-back)
            + case when cl.side = pb.home_team then
                case when pb.home_rest_days = 1
                      and coalesce(pb.away_rest_days, 2) > 1 then -0.02
                     when coalesce(pb.home_rest_days, 2) > 1
                      and pb.away_rest_days = 1 then 0.02
                     else 0.0 end
              else
                case when pb.away_rest_days = 1
                      and coalesce(pb.home_rest_days, 2) > 1 then -0.02
                     when coalesce(pb.away_rest_days, 2) > 1
                      and pb.home_rest_days = 1 then 0.02
                     else 0.0 end
              end
            -- Signal 4: ATS track record as dampened prior (max +/-3%)
            + greatest(-0.03, least(0.03,
                (coalesce(
                    case when cl.side = pb.home_team
                        then pb.home_ats_pct else pb.away_ats_pct end,
                    0.50
                ) - 0.50) * 0.15
            ))
          ))                                  as cover_probability
        -- Season record for this market/side
        , case
            when cl.side = pb.home_team then pb.home_ats_wins
            else pb.away_ats_wins
          end                                 as season_market_wins
        , case
            when cl.side = pb.home_team
                then pb.home_ats_wins + pb.home_ats_losses + pb.home_ats_pushes
            else pb.away_ats_wins + pb.away_ats_losses + pb.away_ats_pushes
          end                                 as season_market_total
        -- Rolling stats context
        , pb.home_l10_pts
        , pb.home_l10_off_rating
        , pb.home_l10_def_rating
        , pb.away_l10_pts
        , pb.away_l10_off_rating
        , pb.away_l10_def_rating
        -- Rest days & pace context
        , pb.home_rest_days
        , pb.away_rest_days
        , pb.home_l10_possessions
        , pb.away_l10_possessions
        -- Four Factors L10 (home offense + defense)
        , pb.home_l10_efg_pct
        , pb.home_l10_tov_pct
        , pb.home_l10_orb_pct
        , pb.home_l10_ftr
        , pb.home_l10_opp_efg_pct
        , pb.home_l10_opp_tov_pct
        , pb.home_l10_opp_orb_pct
        , pb.home_l10_opp_ftr
        -- Four Factors L10 (away offense + defense)
        , pb.away_l10_efg_pct
        , pb.away_l10_tov_pct
        , pb.away_l10_orb_pct
        , pb.away_l10_ftr
        , pb.away_l10_opp_efg_pct
        , pb.away_l10_opp_tov_pct
        , pb.away_l10_opp_orb_pct
        , pb.away_l10_opp_ftr
    from predictions_base as pb
    inner join consensus as cl
        on pb.event_id = cl.event_id
        and pb.game_date = cl.game_date
        and cl.market_key = 'spreads'

)

, spread_predictions as (

    select
        game_date, event_id, season, home_team, away_team
        , commence_time_utc, commence_time_et
        , projected_home_score, projected_away_score, projected_total
        , market_key, side, consensus_line, consensus_price
        , consensus_implied_prob, num_bookmakers, best_price
        , cover_probability
        , season_market_wins
        , season_market_total
        , {{ calculate_expected_value('cover_probability', 'consensus_price') }}
                                              as expected_value
        , home_l10_pts, home_l10_off_rating, home_l10_def_rating
        , away_l10_pts, away_l10_off_rating, away_l10_def_rating
        , home_rest_days, away_rest_days
        , home_l10_possessions, away_l10_possessions
        , home_l10_efg_pct, home_l10_tov_pct, home_l10_orb_pct, home_l10_ftr
        , home_l10_opp_efg_pct, home_l10_opp_tov_pct, home_l10_opp_orb_pct, home_l10_opp_ftr
        , away_l10_efg_pct, away_l10_tov_pct, away_l10_orb_pct, away_l10_ftr
        , away_l10_opp_efg_pct, away_l10_opp_tov_pct, away_l10_opp_orb_pct, away_l10_opp_ftr
    from spread_base

)

-- =====================================================================
-- H2H (moneyline): market implied prob base + Four Factors + rest
-- =====================================================================
, h2h_base as (

    select
        pb.game_date
        , pb.event_id
        , pb.season
        , pb.home_team
        , pb.away_team
        , pb.commence_time_utc
        , pb.commence_time_et
        , pb.projected_home_score
        , pb.projected_away_score
        , pb.projected_home_score + pb.projected_away_score
                                              as projected_total
        , 'h2h'                               as market_key
        , cl.side
        , cl.consensus_line
        , cl.consensus_price
        , cl.consensus_implied_prob
        , cl.num_bookmakers
        , cl.best_price
        -- Composite win probability: market implied prob + adjustments
        , greatest(0.10, least(0.90,
            coalesce(cl.consensus_implied_prob, 0.50)
            -- Signal 1: Four Factors matchup (lighter weight — market already prices team quality)
            + (case when cl.side = pb.home_team then
                  0.40 * (coalesce(pb.home_l10_efg_pct, 0.50)
                        - coalesce(pb.away_l10_opp_efg_pct, 0.50)) / 0.04
                + 0.25 * (coalesce(pb.away_l10_opp_tov_pct, 0.14)
                        - coalesce(pb.home_l10_tov_pct, 0.14)) / 0.03
                + 0.20 * (coalesce(pb.home_l10_orb_pct, 0.25)
                        - coalesce(pb.away_l10_opp_orb_pct, 0.25)) / 0.05
                + 0.15 * (coalesce(pb.home_l10_ftr, 0.25)
                        - coalesce(pb.away_l10_opp_ftr, 0.25)) / 0.05
              else
                  0.40 * (coalesce(pb.away_l10_efg_pct, 0.50)
                        - coalesce(pb.home_l10_opp_efg_pct, 0.50)) / 0.04
                + 0.25 * (coalesce(pb.home_l10_opp_tov_pct, 0.14)
                        - coalesce(pb.away_l10_tov_pct, 0.14)) / 0.03
                + 0.20 * (coalesce(pb.away_l10_orb_pct, 0.25)
                        - coalesce(pb.home_l10_opp_orb_pct, 0.25)) / 0.05
                + 0.15 * (coalesce(pb.away_l10_ftr, 0.25)
                        - coalesce(pb.home_l10_opp_ftr, 0.25)) / 0.05
              end) * 0.06
            -- Signal 2: Rest day adjustment
            + case when cl.side = pb.home_team then
                case when pb.home_rest_days = 1
                      and coalesce(pb.away_rest_days, 2) > 1 then -0.02
                     when coalesce(pb.home_rest_days, 2) > 1
                      and pb.away_rest_days = 1 then 0.02
                     else 0.0 end
              else
                case when pb.away_rest_days = 1
                      and coalesce(pb.home_rest_days, 2) > 1 then -0.02
                     when coalesce(pb.away_rest_days, 2) > 1
                      and pb.home_rest_days = 1 then 0.02
                     else 0.0 end
              end
          ))                                  as cover_probability
        , case
            when cl.side = pb.home_team then pb.home_su_wins
            else pb.away_su_wins
          end                                 as season_market_wins
        , case
            when cl.side = pb.home_team
                then pb.home_su_wins + pb.home_su_losses
            else pb.away_su_wins + pb.away_su_losses
          end                                 as season_market_total
        , pb.home_l10_pts
        , pb.home_l10_off_rating
        , pb.home_l10_def_rating
        , pb.away_l10_pts
        , pb.away_l10_off_rating
        , pb.away_l10_def_rating
        -- Rest days & pace context
        , pb.home_rest_days
        , pb.away_rest_days
        , pb.home_l10_possessions
        , pb.away_l10_possessions
        -- Four Factors L10 (home offense + defense)
        , pb.home_l10_efg_pct
        , pb.home_l10_tov_pct
        , pb.home_l10_orb_pct
        , pb.home_l10_ftr
        , pb.home_l10_opp_efg_pct
        , pb.home_l10_opp_tov_pct
        , pb.home_l10_opp_orb_pct
        , pb.home_l10_opp_ftr
        -- Four Factors L10 (away offense + defense)
        , pb.away_l10_efg_pct
        , pb.away_l10_tov_pct
        , pb.away_l10_orb_pct
        , pb.away_l10_ftr
        , pb.away_l10_opp_efg_pct
        , pb.away_l10_opp_tov_pct
        , pb.away_l10_opp_orb_pct
        , pb.away_l10_opp_ftr
    from predictions_base as pb
    inner join consensus as cl
        on pb.event_id = cl.event_id
        and pb.game_date = cl.game_date
        and cl.market_key = 'h2h'

)

, h2h_predictions as (

    select
        game_date, event_id, season, home_team, away_team
        , commence_time_utc, commence_time_et
        , projected_home_score, projected_away_score, projected_total
        , market_key, side, consensus_line, consensus_price
        , consensus_implied_prob, num_bookmakers, best_price
        , cover_probability
        , season_market_wins
        , season_market_total
        , {{ calculate_expected_value('cover_probability', 'consensus_price') }}
                                              as expected_value
        , home_l10_pts, home_l10_off_rating, home_l10_def_rating
        , away_l10_pts, away_l10_off_rating, away_l10_def_rating
        , home_rest_days, away_rest_days
        , home_l10_possessions, away_l10_possessions
        , home_l10_efg_pct, home_l10_tov_pct, home_l10_orb_pct, home_l10_ftr
        , home_l10_opp_efg_pct, home_l10_opp_tov_pct, home_l10_opp_orb_pct, home_l10_opp_ftr
        , away_l10_efg_pct, away_l10_tov_pct, away_l10_orb_pct, away_l10_ftr
        , away_l10_opp_efg_pct, away_l10_opp_tov_pct, away_l10_opp_orb_pct, away_l10_opp_ftr
    from h2h_base

)

-- =====================================================================
-- TOTALS: projected total edge + pace matchup + O/U track record
-- =====================================================================
, total_base as (

    select
        pb.game_date
        , pb.event_id
        , pb.season
        , pb.home_team
        , pb.away_team
        , pb.commence_time_utc
        , pb.commence_time_et
        , pb.projected_home_score
        , pb.projected_away_score
        , pb.projected_home_score + pb.projected_away_score
                                              as projected_total
        , 'totals'                            as market_key
        , cl.side
        , cl.consensus_line
        , cl.consensus_price
        , cl.consensus_implied_prob
        , cl.num_bookmakers
        , cl.best_price
        -- Composite cover probability for totals
        , greatest(0.30, least(0.70,
            0.50
            -- Signal 1: Projected total edge vs line
            -- Each point of edge ~ +1.5% cover prob, capped +/-12%
            + greatest(-0.12, least(0.12,
                (case when cl.side = 'Over'
                    then (pb.projected_home_score + pb.projected_away_score)
                         - cl.consensus_line
                    else cl.consensus_line
                         - (pb.projected_home_score + pb.projected_away_score)
                end) * 0.015
            ))
            -- Signal 2: Pace matchup — high-pace games push overs
            -- League average ~97 possessions; each possession above/below ~ +0.5% prob
            + greatest(-0.05, least(0.05,
                (case when cl.side = 'Over' then 1 else -1 end)
                * ((coalesce(pb.home_l10_possessions, 97)
                    + coalesce(pb.away_l10_possessions, 97)) / 2.0 - 97.0)
                * 0.005
            ))
            -- Signal 3: O/U track record as dampened prior (max +/-3%)
            + greatest(-0.03, least(0.03,
                (coalesce(
                    case when cl.side = 'Over'
                        then {{ safe_divide('pb.home_over_wins',
                            'pb.home_over_wins + pb.home_under_wins + pb.home_ou_pushes') }}
                        else {{ safe_divide('pb.home_under_wins',
                            'pb.home_over_wins + pb.home_under_wins + pb.home_ou_pushes') }}
                    end,
                    0.50
                ) - 0.50) * 0.15
            ))
          ))                                  as cover_probability
        , case
            when cl.side = 'Over' then pb.home_over_wins
            else pb.home_under_wins
          end                                 as season_market_wins
        , pb.home_over_wins + pb.home_under_wins + pb.home_ou_pushes
                                              as season_market_total
        , pb.home_l10_pts
        , pb.home_l10_off_rating
        , pb.home_l10_def_rating
        , pb.away_l10_pts
        , pb.away_l10_off_rating
        , pb.away_l10_def_rating
        -- Rest days & pace context
        , pb.home_rest_days
        , pb.away_rest_days
        , pb.home_l10_possessions
        , pb.away_l10_possessions
        -- Four Factors L10 (home offense + defense)
        , pb.home_l10_efg_pct
        , pb.home_l10_tov_pct
        , pb.home_l10_orb_pct
        , pb.home_l10_ftr
        , pb.home_l10_opp_efg_pct
        , pb.home_l10_opp_tov_pct
        , pb.home_l10_opp_orb_pct
        , pb.home_l10_opp_ftr
        -- Four Factors L10 (away offense + defense)
        , pb.away_l10_efg_pct
        , pb.away_l10_tov_pct
        , pb.away_l10_orb_pct
        , pb.away_l10_ftr
        , pb.away_l10_opp_efg_pct
        , pb.away_l10_opp_tov_pct
        , pb.away_l10_opp_orb_pct
        , pb.away_l10_opp_ftr
    from predictions_base as pb
    inner join consensus as cl
        on pb.event_id = cl.event_id
        and pb.game_date = cl.game_date
        and cl.market_key = 'totals'

)

, total_predictions as (

    select
        game_date, event_id, season, home_team, away_team
        , commence_time_utc, commence_time_et
        , projected_home_score, projected_away_score, projected_total
        , market_key, side, consensus_line, consensus_price
        , consensus_implied_prob, num_bookmakers, best_price
        , cover_probability
        , season_market_wins
        , season_market_total
        , {{ calculate_expected_value('cover_probability', 'consensus_price') }}
                                              as expected_value
        , home_l10_pts, home_l10_off_rating, home_l10_def_rating
        , away_l10_pts, away_l10_off_rating, away_l10_def_rating
        , home_rest_days, away_rest_days
        , home_l10_possessions, away_l10_possessions
        , home_l10_efg_pct, home_l10_tov_pct, home_l10_orb_pct, home_l10_ftr
        , home_l10_opp_efg_pct, home_l10_opp_tov_pct, home_l10_opp_orb_pct, home_l10_opp_ftr
        , away_l10_efg_pct, away_l10_tov_pct, away_l10_orb_pct, away_l10_ftr
        , away_l10_opp_efg_pct, away_l10_opp_tov_pct, away_l10_opp_orb_pct, away_l10_opp_ftr
    from total_base

)

, all_predictions as (

    select * from spread_predictions
    union all
    select * from h2h_predictions
    union all
    select * from total_predictions

)

select
    game_date
    , event_id
    , season
    , home_team
    , away_team
    , commence_time_utc
    , commence_time_et
    , projected_home_score
    , projected_away_score
    , projected_total
    , market_key
    , side
    , consensus_line
    , consensus_price
    , consensus_implied_prob
    , num_bookmakers
    , best_price
    , cover_probability
    , season_market_wins
    , season_market_total
    , expected_value
    -- Bet rating: 1-5 stars based on EV
    , case
        when expected_value >= 0.10 then 5
        when expected_value >= 0.05 then 4
        when expected_value >= 0.02 then 3
        when expected_value >= 0.00 then 2
        else 1
      end                                     as bet_rating
    , home_l10_pts
    , home_l10_off_rating
    , home_l10_def_rating
    , away_l10_pts
    , away_l10_off_rating
    , away_l10_def_rating
    , home_rest_days
    , away_rest_days
    , home_l10_possessions
    , away_l10_possessions
    , home_l10_efg_pct
    , home_l10_tov_pct
    , home_l10_orb_pct
    , home_l10_ftr
    , home_l10_opp_efg_pct
    , home_l10_opp_tov_pct
    , home_l10_opp_orb_pct
    , home_l10_opp_ftr
    , away_l10_efg_pct
    , away_l10_tov_pct
    , away_l10_orb_pct
    , away_l10_ftr
    , away_l10_opp_efg_pct
    , away_l10_opp_tov_pct
    , away_l10_opp_orb_pct
    , away_l10_opp_ftr
from all_predictions
