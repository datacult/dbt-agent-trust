with sellers as (

    select * from {{ ref('stg_olist__sellers') }}

),

with_region as (

    select
        seller_id,
        seller_zip_code_prefix,
        seller_city,
        seller_state,
        {{ brazil_region('seller_state') }} as seller_region
    from sellers

)

select * from with_region
