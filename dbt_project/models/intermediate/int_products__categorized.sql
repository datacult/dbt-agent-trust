with products as (

    select * from {{ ref('stg_olist__products') }}

),

categorized as (

    select
        product_id,
        product_category_name as product_category_name_pt,
        coalesce(product_category_name_english, 'uncategorized') as product_category_name,
        case
            when product_category_name in (
                'computers_accessories', 'electronics', 'computers',
                'tablets_printing_image', 'telephony', 'consoles_games',
                'fixed_telephony', 'signaling_and_security'
            ) then 'Electronics'
            when product_category_name in (
                'furniture_decor', 'garden_tools', 'housewares', 'bed_bath_table',
                'home_confort', 'home_comfort_2', 'home_construction',
                'kitchen_dining_laundry_garden_furniture', 'furniture_living_room',
                'furniture_bedroom', 'furniture_mattress_and_upholstery',
                'office_furniture', 'bathroom_items'
            ) then 'Home & Living'
            when product_category_name in (
                'health_beauty', 'perfumery', 'diapers_and_hygiene'
            ) then 'Health & Beauty'
            when product_category_name in (
                'sports_leisure', 'fashion_sport'
            ) then 'Sports & Leisure'
            when product_category_name in (
                'fashion_bags_accessories', 'fashion_shoes', 'fashion_underwear_beach',
                'fashion_male_clothing', 'fashion_childrens_clothes', 'watches_gifts',
                'luggage_accessories', 'cool_stuff'
            ) then 'Fashion & Accessories'
            when product_category_name in (
                'auto', 'industry_commerce_and_business'
            ) then 'Auto & Industry'
            when product_category_name in (
                'food', 'drinks', 'food_drink'
            ) then 'Food & Drink'
            when product_category_name in (
                'books_general_interest', 'books_technical', 'books_imported',
                'dvds_blu_ray', 'cds_dvds_musicals', 'music', 'arts_and_craftmanship'
            ) then 'Books & Media'
            when product_category_name in ('baby', 'toys') then 'Baby & Toys'
            when product_category_name in (
                'construction_tools_construction', 'construction_tools_lights',
                'construction_tools_safety', 'construction_tools_garden'
            ) then 'Tools & Construction'
            when product_category_name = 'pet_shop' then 'Pet'
            when product_category_name in ('stationery', 'party_supplies')
                then 'Stationery & Party'
            else 'Other'
        end as product_department,
        product_weight_g,
        product_length_cm,
        product_height_cm,
        product_width_cm,
        product_photos_qty
    from products

)

select * from categorized
