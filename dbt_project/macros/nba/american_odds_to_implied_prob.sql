{% macro american_odds_to_implied_prob(column_name) -%}
    case
        when {{ column_name }} > 0
            then 100.0 / ({{ column_name }} + 100.0)
        when {{ column_name }} < 0
            then abs({{ column_name }}) / (abs({{ column_name }}) + 100.0)
        else null
    end
{%- endmacro %}
