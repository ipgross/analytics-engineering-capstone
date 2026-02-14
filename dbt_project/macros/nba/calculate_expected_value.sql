{% macro calculate_expected_value(win_prob_expr, american_odds_expr) -%}
    case
        when {{ american_odds_expr }} > 0
            then ({{ win_prob_expr }}) * ({{ american_odds_expr }} / 100.0)
                 - (1.0 - ({{ win_prob_expr }}))
        when {{ american_odds_expr }} < 0
            then ({{ win_prob_expr }}) * (100.0 / abs({{ american_odds_expr }}))
                 - (1.0 - ({{ win_prob_expr }}))
        else null
    end
{%- endmacro %}
