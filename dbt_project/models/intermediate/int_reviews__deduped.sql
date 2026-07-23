with reviews as (

    select * from {{ ref('stg_olist__order_reviews') }}

),

orders as (

    select
        order_id,
        purchased_at,
        is_completed
    from {{ ref('stg_olist__orders') }}

),

deduped as (

    -- Source review_id can repeat across orders. Grain here is (review_id, order_id);
    -- if that pair repeats we keep the earliest created record.
    select
        reviews.*,
        row_number() over (
            partition by reviews.review_id, reviews.order_id
            order by reviews.review_created_at asc
        ) as _row_num
    from reviews

),

joined as (

    select
        {{ dbt_utils.generate_surrogate_key(['deduped.review_id', 'deduped.order_id']) }}
            as review_pk,
        deduped.review_id,
        deduped.order_id,
        orders.purchased_at,
        orders.is_completed,
        deduped.review_score,
        deduped.review_score >= 4 as is_positive_review,
        deduped.review_score <= 2 as is_negative_review,
        deduped.review_comment_title,
        deduped.review_comment_message,
        deduped.review_created_at,
        deduped.review_answered_at
    from deduped
    left join orders on deduped.order_id = orders.order_id
    where deduped._row_num = 1

)

select * from joined
