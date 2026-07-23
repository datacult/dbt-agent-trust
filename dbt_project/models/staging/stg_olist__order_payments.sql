with source as (

    select * from {{ ref('olist_order_payments_dataset') }}

),

renamed as (

    select
        {{ dbt_utils.generate_surrogate_key(['order_id', 'payment_sequential']) }} as order_payment_pk,
        order_id,
        payment_sequential,
        payment_type,
        payment_installments,
        payment_value
    from source

)

select * from renamed
