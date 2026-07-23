with source as (

    select * from {{ ref('olist_order_items_dataset') }}

),

renamed as (

    select
        {{ dbt_utils.generate_surrogate_key(['order_id', 'order_item_id']) }} as order_item_pk,
        order_id,
        order_item_id,
        product_id,
        seller_id,
        shipping_limit_date as shipping_limit_at,
        price,
        freight_value
    from source

)

select * from renamed
