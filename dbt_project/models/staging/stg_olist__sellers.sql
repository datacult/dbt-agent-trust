with source as (

    select * from {{ ref('olist_sellers_dataset') }}

),

renamed as (

    select
        seller_id,
        lpad(cast(seller_zip_code_prefix as varchar), 5, '0') as seller_zip_code_prefix,
        seller_city,
        seller_state
    from source

)

select * from renamed
