with spine as (

    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('2016-01-01' as date)",
        end_date="cast('2019-01-01' as date)"
    ) }}

),

dates as (

    select
        cast(date_day as date) as date_day
    from spine

),

enriched as (

    select
        date_day,
        extract(year    from date_day)                             as year,
        extract(quarter from date_day)                             as quarter,
        extract(month   from date_day)                             as month,
        extract(week    from date_day)                             as iso_week,
        extract(day     from date_day)                             as day_of_month,
        extract(dayofweek from date_day)                           as day_of_week,
        date_trunc('week',    date_day)::date                      as week_start_date,
        date_trunc('month',   date_day)::date                      as month_start_date,
        date_trunc('quarter', date_day)::date                      as quarter_start_date,
        date_trunc('year',    date_day)::date                      as year_start_date,
        cast(extract(year from date_day) as varchar) || '-Q'
            || cast(extract(quarter from date_day) as varchar)     as year_quarter,
        strftime(date_day, '%Y-%m')                                as year_month
    from dates

)

select * from enriched
