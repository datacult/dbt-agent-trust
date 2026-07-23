with items as (

    select * from {{ ref('stg_olist__order_items') }}

),

orders as (

    select
        order_id,
        customer_id,
        customer_unique_id,
        customer_state,
        customer_region,
        order_status,
        is_completed,
        purchased_at,
        purchased_at_sao_paulo
    from {{ ref('int_orders__enriched') }}

),

products as (

    select
        product_id,
        product_category_name,
        product_department
    from {{ ref('int_products__categorized') }}

),

sellers as (

    select
        seller_id,
        seller_state,
        seller_region
    from {{ ref('int_sellers__region_assigned') }}

),

enriched as (

    select
        items.order_item_pk,
        items.order_id,
        items.order_item_id,
        items.product_id,
        items.seller_id,
        orders.customer_id,
        orders.customer_unique_id,
        orders.customer_state,
        orders.customer_region,
        orders.order_status,
        orders.is_completed,
        orders.purchased_at,
        orders.purchased_at_sao_paulo,
        products.product_category_name,
        products.product_department,
        sellers.seller_state,
        sellers.seller_region,
        orders.customer_state = sellers.seller_state as is_intra_state,
        items.price,
        items.freight_value,
        items.price + items.freight_value as item_total_value,
        items.shipping_limit_at
    from items
    left join orders   on items.order_id   = orders.order_id
    left join products on items.product_id = products.product_id
    left join sellers  on items.seller_id  = sellers.seller_id

)

select * from enriched
