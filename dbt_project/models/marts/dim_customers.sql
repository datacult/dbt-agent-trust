with customers as (

    select * from {{ ref('int_customers__region_assigned') }}

),

orders as (

    select
        customer_id,
        purchased_at,
        is_completed
    from {{ ref('int_orders__enriched') }}

),

customer_orders as (

    select
        customers.customer_unique_id,
        customers.customer_id,
        customers.customer_state,
        customers.customer_region,
        customers.customer_city,
        customers.customer_zip_code_prefix,
        orders.purchased_at,
        orders.is_completed,
        row_number() over (
            partition by customers.customer_unique_id
            order by orders.purchased_at desc nulls last
        ) as recency_rank
    from customers
    left join orders on customers.customer_id = orders.customer_id

),

aggregated as (

    select
        customer_unique_id,
        -- address of the most recent order stands in for the person
        max(case when recency_rank = 1 then customer_state end)           as customer_state,
        max(case when recency_rank = 1 then customer_region end)          as customer_region,
        max(case when recency_rank = 1 then customer_city end)            as customer_city,
        max(case when recency_rank = 1 then customer_zip_code_prefix end) as customer_zip_code_prefix,
        min(purchased_at)                                                 as first_purchased_at,
        max(purchased_at)                                                 as last_purchased_at,
        count(distinct case when is_completed then customer_id end)       as completed_order_count,
        count(distinct case when is_completed then customer_id end) >= 2  as is_repeat_buyer
    from customer_orders
    group by 1

)

select * from aggregated
