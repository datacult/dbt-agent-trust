with source as (

    select * from {{ ref('olist_customers_dataset') }}

),

renamed as (

    select
        customer_id,
        customer_unique_id,
        lpad(cast(customer_zip_code_prefix as varchar), 5, '0') as customer_zip_code_prefix,
        customer_city,
        customer_state
    from source

)

select * from renamed
