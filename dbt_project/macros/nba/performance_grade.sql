{% macro performance_grade(delta_expr, a_plus=15, a=8, b=3, c=-3, d=-8) %}
case
    when {{ delta_expr }} >= {{ a_plus }} then 'A+'
    when {{ delta_expr }} >= {{ a }} then 'A'
    when {{ delta_expr }} >= {{ b }} then 'B'
    when {{ delta_expr }} >= {{ c }} then 'C'
    when {{ delta_expr }} >= {{ d }} then 'D'
    else 'F'
end
{% endmacro %}
