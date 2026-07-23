select
    seller_id,
    seller_state,
    seller_region,
    seller_city,
    seller_zip_code_prefix
from {{ ref('int_sellers__region_assigned') }}
