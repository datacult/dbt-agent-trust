with orders as (

    select * from {{ ref('stg_olist__orders') }}

),

customers as (

    select
        customer_id,
        customer_unique_id,
        customer_state,
        customer_region
    from {{ ref('int_customers__region_assigned') }}

),

joined as (

    select
        orders.order_id,
        orders.customer_id,
        customers.customer_unique_id,
        customers.customer_state,
        customers.customer_region,
        orders.order_status,
        orders.is_completed,
        orders.order_status = 'delivered' as is_delivered,
        orders.order_status = 'canceled'  as is_canceled,
        orders.purchased_at,
        -- Sao Paulo local time. DuckDB reads naive timestamps as UTC via AT TIME ZONE.
        (orders.purchased_at at time zone 'UTC' at time zone 'America/Sao_Paulo')
            as purchased_at_sao_paulo,
        orders.approved_at,
        orders.delivered_to_carrier_at,
        orders.delivered_to_customer_at,
        orders.estimated_delivery_at
    from orders
    left join customers on orders.customer_id = customers.customer_id

),

with_delivery_metrics as (

    select
        *,
        case
            when is_delivered
                and delivered_to_customer_at is not null
                then datediff('day', purchased_at, delivered_to_customer_at)
        end as delivery_time_days,
        case
            when delivered_to_carrier_at is not null
                and approved_at is not null
                then datediff('day', approved_at, delivered_to_carrier_at)
        end as carrier_handoff_days,
        case
            when is_delivered
                and delivered_to_customer_at is not null
                and estimated_delivery_at is not null
                then delivered_to_customer_at <= estimated_delivery_at
        end as is_on_time,
        case
            when is_delivered
                and delivered_to_customer_at is not null
                and estimated_delivery_at is not null
                then delivered_to_customer_at > estimated_delivery_at
        end as is_late,
        case
            when is_delivered
                and delivered_to_customer_at is not null
                and estimated_delivery_at is not null
                and delivered_to_customer_at > estimated_delivery_at
                then datediff('day', estimated_delivery_at, delivered_to_customer_at)
        end as days_late
    from joined

)

select * from with_delivery_metrics
