{% macro parse_minutes(column_name) -%}
    case
        when {{ column_name }} is null or {{ column_name }} = '' then 0.0
        when {{ column_name }} like '%:%'
            then split_part({{ column_name }}, ':', 1)::float
                 + split_part({{ column_name }}, ':', 2)::float / 60.0
        else try_to_double({{ column_name }})
    end
{%- endmacro %}
