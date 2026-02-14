{% macro safe_divide(numerator, denominator) -%}
    ({{ numerator }})::float / nullif({{ denominator }}, 0)
{%- endmacro %}
