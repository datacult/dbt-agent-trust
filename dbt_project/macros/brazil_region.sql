{% macro brazil_region(state_column) %}
    case
        when {{ state_column }} in ('SP', 'RJ', 'MG', 'ES')
            then 'Southeast'
        when {{ state_column }} in ('PR', 'SC', 'RS')
            then 'South'
        when {{ state_column }} in ('BA', 'CE', 'PE', 'MA', 'PB', 'PI', 'RN', 'AL', 'SE')
            then 'Northeast'
        when {{ state_column }} in ('DF', 'GO', 'MT', 'MS')
            then 'Central-West'
        when {{ state_column }} in ('AM', 'PA', 'AC', 'RO', 'RR', 'AP', 'TO')
            then 'North'
        else 'Unknown'
    end
{% endmacro %}
