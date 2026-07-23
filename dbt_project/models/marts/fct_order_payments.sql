with payments as (

    select * from {{ ref('stg_olist__order_payments') }}

),

orders as (

    select
        order_id,
        purchased_at,
        is_completed
    from {{ ref('int_orders__enriched') }}

)

select
    payments.order_payment_pk,
    payments.order_id,
    payments.payment_sequential,
    payments.payment_type,
    payments.payment_installments,
    payments.payment_value,
    orders.purchased_at,
    orders.is_completed
from payments
left join orders on payments.order_id = orders.order_id
