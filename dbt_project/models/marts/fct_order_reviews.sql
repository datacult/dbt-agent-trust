select
    review_pk,
    review_id,
    order_id,
    purchased_at,
    is_completed,
    review_score,
    is_positive_review,
    is_negative_review,
    review_created_at,
    review_answered_at
from {{ ref('int_reviews__deduped') }}
