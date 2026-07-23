with source as (

    select * from {{ ref('olist_orders_dataset') }}

),

renamed as (

    select
        order_id,
        customer_id,
        order_status,
        -- completed = order proceeded past checkout; excludes canceled, unavailable, created
        order_status in ('delivered', 'shipped', 'processing', 'invoiced', 'approved') as is_completed,
        order_purchase_timestamp as purchased_at,
        order_approved_at as approved_at,
        order_delivered_carrier_date as delivered_to_carrier_at,
        order_delivered_customer_date as delivered_to_customer_at,
        order_estimated_delivery_date as estimated_delivery_at
    from source

)

select * from renamed
