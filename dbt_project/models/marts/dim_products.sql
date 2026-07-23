select
    product_id,
    product_category_name,
    product_category_name_pt,
    product_department,
    product_weight_g,
    product_length_cm,
    product_height_cm,
    product_width_cm,
    product_photos_qty
from {{ ref('int_products__categorized') }}
