with products as (

    select * from {{ ref('olist_products_dataset') }}

),

translation as (

    select * from {{ ref('product_category_name_translation') }}

),

renamed as (

    select
        products.product_id,
        products.product_category_name,
        translation.product_category_name_english,
        products.product_name_lenght as product_name_length,
        products.product_description_lenght as product_description_length,
        products.product_photos_qty,
        products.product_weight_g,
        products.product_length_cm,
        products.product_height_cm,
        products.product_width_cm
    from products
    left join translation
        on products.product_category_name = translation.product_category_name

)

select * from renamed
