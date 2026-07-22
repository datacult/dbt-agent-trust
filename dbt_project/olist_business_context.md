# Olist Marketplace: Business Context and Analytical Rules

## About the Business

Olist is a Brazilian marketplace aggregator that connects small merchants to major e-commerce channels through a single contract. Olist is not a retailer. It does not hold inventory or set product prices. It provides the platform, logistics coordination, and payment processing layer.

The dataset covers approximately 100,000 orders from September 2016 through August 2018, representing the marketplace's growth from early-stage (~300 orders/month in late 2016) to scale (~7,000 orders/month by early 2018).

All monetary values are in **Brazilian Reais (BRL, R$)**.

---

## Revenue Definitions

### 1. Gross Merchandise Value (GMV)
The primary top-line metric. Total value of goods sold on the platform.

**GMV = SUM(price) from order items on completed orders.**

GMV **excludes**:
- Freight charges (freight_value is a logistics cost passed to the customer, not merchandise revenue)
- Cancelled orders (order_status = 'canceled')
- Unavailable orders (order_status = 'unavailable')
- Orders still in "created" status (incomplete checkout)

Total GMV across the dataset: approximately R$13.5 million.

### 2. Total Order Value (TOV)
The full amount the customer pays, including shipping.

**TOV = SUM(price + freight_value) from order items on completed orders.**

Freight adds approximately 16.6% on top of GMV across the platform. This ratio varies significantly by region and product category (heavy or bulky items in remote states carry much higher freight).

### 3. Average Order Value (AOV)
**AOV = GMV / COUNT(DISTINCT completed order_id)**

Not: GMV / count of order items (that would be average item value, a different metric).

### Default Revenue Metric
When someone asks about "revenue," "sales," or "how much did we sell," default to **GMV**. Specify which definition is being used in the response. If they ask "what did customers pay" or "total order value," use TOV.

---

## Order Status Rules

| Status | Count | Definition | Include in GMV? |
|---|---|---|---|
| delivered | ~96,478 | Customer received the order | Yes |
| shipped | ~1,107 | Dispatched, in transit | Yes |
| canceled | ~625 | Cancelled by buyer or seller | No |
| unavailable | ~609 | Product unavailable post-order | No |
| invoiced | ~314 | Invoice generated | Yes |
| processing | ~301 | Being prepared | Yes |
| created | ~5 | Checkout started, not committed | No |
| approved | ~2 | Payment approved | Yes |

**Note:** The status in the data is spelled "canceled" (single L, American English), not "cancelled." Queries must match the exact string.

### 1. Completed Orders
An order is **completed** if its status is: delivered, shipped, processing, invoiced, or approved. These represent transactions where the customer committed and the order proceeded.

Default filter for all revenue, performance, and operational metrics is **completed orders only** unless the question specifically asks about cancellations or all orders.

### 2. Cancellation Rate
**Cancellation rate = canceled orders / (completed orders + canceled orders)**

Exclude "created" (incomplete checkout, not a cancellation) and "unavailable" (supply-side failure, not a customer cancellation) from both numerator and denominator.

Across the dataset, the cancellation rate is approximately 0.6%. This is low, which is expected for a marketplace where sellers confirm availability before the order is finalized.

---

## Calendar Conventions

### Week Definition
Week starts **Monday**, ends **Sunday** (ISO 8601, standard Brazilian business convention).

### Fiscal Calendar
Calendar year. Q1 = Jan-Mar, Q2 = Apr-Jun, Q3 = Jul-Sep, Q4 = Oct-Dec.

### Timezone
All timestamps in the dataset are **UTC**. Brazilian business operates in **America/Sao_Paulo (UTC-3)**. For daily, weekly, and monthly aggregations, convert to Sao Paulo time before truncating.

An order placed at 23:30 UTC on January 31 is actually 20:30 on January 31 in Sao Paulo (same day in this case). But an order at 01:00 UTC on February 1 is 22:00 on January 31 in Sao Paulo (different day). This matters for daily GMV and weekly trend reporting.

### Order Date
The reporting date for an order is **order_purchase_timestamp** (when the customer placed the order), not the approval or delivery date.

### Data Coverage
- First orders: September 2016 (only 2 orders, effectively a test period)
- Ramp-up: October 2016 through January 2017
- Stable growth: February 2017 through August 2018
- Last complete month: August 2018


**For clean trend analysis, use January 2017 through August 2018 as the reliable reporting window.**

---

## Customer Definitions

### 1. The customer_id Trap
The dataset has two customer identifiers, and using the wrong one produces silently incorrect results:

- **customer_id**: Changes with every order. One person placing 3 orders gets 3 different customer_ids. Using this for "unique customer count" gives you the order count, not the customer count.
- **customer_unique_id**: Persistent across orders. This is the real person.

**Always use customer_unique_id for customer counts, cohort analysis, and retention metrics.** There are ~96,096 unique customers across ~99,441 orders.

### 2. New vs Returning Customers
- **New customer**: A customer_unique_id whose earliest order_purchase_timestamp falls within the reporting period
- **Returning customer**: A customer_unique_id who placed a completed order before the start of the reporting period

### 3. Repeat Purchase Rate
**Repeat rate = customers with 2+ completed orders / total unique customers**

The actual repeat purchase rate is approximately **3.1%** (2,997 repeat buyers out of 96,096 unique customers). This is low but typical for a marketplace aggregator where customers often don't realize they're buying through Olist versus buying directly from a retailer. Low brand recognition drives low repeat purchase to the platform specifically.

This metric matters for the business because improving it from 3% to even 5% represents significant revenue growth without customer acquisition cost.

---

## Delivery Performance

### 1. On-Time Delivery
**On-time** = order_delivered_customer_date is on or before order_estimated_delivery_date.
**Late** = order_delivered_customer_date is after order_estimated_delivery_date.

Only evaluate for orders with status = 'delivered' and where both date fields are populated.

### 2. Actual Performance (from the data)
- **On-time rate: 91.9%** (88,644 of 96,470 delivered orders with dates)
- **Average delivery time: 12.6 days** (purchase to delivery)
- **Median delivery time: 10.2 days**
- **P95 delivery time: 29.3 days** (the long tail)
- **Average days late when late: 9.6 days** past estimated delivery

### 3. Delivery Time
**Delivery time = order_delivered_customer_date - order_purchase_timestamp**, in calendar days.

### 4. Carrier Handoff Time
**Carrier handoff time = order_delivered_carrier_date - order_approved_at**, in calendar days.

This measures seller fulfillment speed: how quickly the seller hands the package to the carrier after payment clears. This is the metric the seller success team cares about, because it's the part of delivery the seller controls.

### 5. Inter-State vs Intra-State
- **Intra-state**: customer_state = seller_state
- **Inter-state**: customer_state differs from seller_state

**63.8% of all items are inter-state shipments.** This is because sellers are heavily concentrated in Sao Paulo (60% of sellers are in SP) while customers are distributed across all states. Inter-state orders have longer delivery times by nature, so segmenting delivery performance by this dimension is essential to avoid misleading averages.

### Delivery Outliers
Orders exceeding 60 days delivery time should be flagged as outliers in average calculations. The maximum in the data is approximately 210 days, which pulls averages meaningfully if not handled. For median-based reporting, this is less of a concern.

---

## Seller Performance

### Active Sellers
A seller is **active** if they have at least one completed order in the reporting period. Approximately 3,053 sellers are active across the full dataset.

### Seller Concentration
Revenue is heavily concentrated:
- **Top 10% of sellers (305 sellers) generate 67.4% of GMV**
- **Top 20% of sellers (610 sellers) generate 82.5% of GMV**

This is a platform risk metric. If a handful of top sellers leave, a disproportionate share of GMV goes with them. The marketplace health team monitors this quarterly.

### Seller Revenue Attribution
Seller revenue is calculated at the **order-item level**, not the order level. A single order can contain items from multiple sellers (approximately 1.3% of orders do). Each item's price is attributed to the seller who fulfilled it.

---

## Geographic Concentration

### The Sao Paulo Dominance
Sao Paulo state (SP) accounts for:
- **42% of all customers**
- **60% of all sellers**

This means SP-to-SP (intra-state within Sao Paulo) is the single largest corridor by volume, and any metric that isn't segmented by region will be dominated by SP patterns.

### Regional Groupings
For executive and operational reporting, states are grouped into five regions:

| Region | States | Customer Share |
|---|---|---|
| Southeast | SP, RJ, MG, ES | ~69% |
| South | PR, SC, RS | ~14% |
| Northeast | BA, CE, PE, MA, PB, PI, RN, AL, SE | ~10% |
| Central-West | DF, GO, MT, MS | ~5% |
| North | AM, PA, AC, RO, RR, AP, TO | ~2% |

The Southeast generates approximately two-thirds of all orders. Always present regional metrics with both absolute numbers and percentages, otherwise the Southeast dominates every chart and the other regions' patterns become invisible.

---

## Product Categories

### Category Translation
Source data uses Portuguese category names. The translation table provides English equivalents. **Always present category names in English.**

### Top Categories by GMV
The top 5 categories account for approximately 40% of total GMV:
1. Health & Beauty (~9.3%)
2. Watches & Gifts (~8.9%)
3. Bed, Bath & Table (~7.7%)
4. Sports & Leisure (~7.3%)
5. Computers & Accessories (~6.7%)

### Uncategorized Products
Approximately 1,589 order items (~1.4%) have products with no category assigned (NULL product_category_name). These should be labeled **"Uncategorized"** in reports, not excluded. They represent valid completed orders contributing to GMV.

### Department Groupings
For executive-level reporting, the 70+ individual categories roll up into departments:

| Department | Includes |
|---|---|
| Electronics | computers_accessories, electronics, computers, tablets_printing_image, telephony, consoles_games, fixed_telephony, signaling_and_security |
| Home & Living | furniture_decor, garden_tools, housewares, bed_bath_table, home_confort, home_comfort_2, home_construction, kitchen_dining_laundry_garden_furniture, furniture_living_room, furniture_bedroom, furniture_mattress_and_upholstery, office_furniture, bathroom_items |
| Health & Beauty | health_beauty, perfumery, diapers_and_hygiene |
| Sports & Leisure | sports_leisure, fashion_sport |
| Fashion & Accessories | fashion_bags_accessories, fashion_shoes, fashion_underwear_beach, fashion_male_clothing, fashion_childrens_clothes, watches_gifts, luggage_accessories, cool_stuff |
| Auto & Industry | auto, industry_commerce_and_business |
| Food & Drink | food, drinks, food_drink |
| Books & Media | books_general_interest, books_technical, books_imported, dvds_blu_ray, cds_dvds_musicals, music, arts_and_craftmanship |
| Baby & Toys | baby, toys |
| Tools & Construction | construction_tools_construction, construction_tools_lights, construction_tools_safety, construction_tools_garden |
| Pet | pet_shop |
| Stationery & Party | stationery, party_supplies |
| Other | all remaining categories including uncategorized |

---

## Payment Rules

### Payment Type Distribution
| Type | Share | Notes |
|---|---|---|
| Credit card | 74% | Supports installments |
| Boleto | 19% | Brazilian bank slip, single payment |
| Voucher | 6% | Promotional credit or gift card |
| Debit card | 1.5% | Direct bank debit |

### Installments
Installments apply only to credit card payments. The most common is 1 (full upfront payment), followed by 2, 3, 4, and 10. Ten installments is notably popular (5% of all payments), likely driven by Brazilian consumer culture of "parceling" larger purchases into monthly payments.

**When asked about average installments, filter to credit card payments only.** Including boleto (always 1) dilutes the metric and misrepresents actual installment behavior.

### Multi-Payment Orders
Approximately 3% of orders use multiple payment methods (e.g., voucher plus credit card). The sum of all payment_value records for an order should equal the order's TOV.

---

## Review and Satisfaction Metrics

### Review Score Distribution
| Score | Share | Label |
|---|---|---|
| 5 | 57.8% | Excellent |
| 4 | 19.3% | Good |
| 3 | 8.2% | Neutral |
| 2 | 3.2% | Poor |
| 1 | 11.5% | Terrible |

The distribution is polarized: most customers either love the experience (5) or hate it (1), with relatively few in the middle. This is typical of marketplace reviews where delivery experience heavily influences the score.

### Customer Satisfaction Score (CSAT)
**CSAT = percentage of reviews scoring 4 or 5**

Actual CSAT: approximately **77.1%**

### Dissatisfaction Rate
**Dissatisfaction rate = percentage of reviews scoring 1 or 2**

Actual dissatisfaction: approximately **14.7%**

The 11.5% score-of-1 rate is high and likely correlated with late deliveries. When analyzing satisfaction, always cross-reference with delivery performance.

### Review Coverage
**Review coverage = orders with at least one review / total completed orders**

Actual coverage: approximately **99.3%**. This is unusually high and means review-based metrics are highly representative. The marketplace likely sends automated review solicitation emails, which drives high coverage.

---

## Seasonality and Events

### Black Friday (November)
November 2017 was the single largest month: ~7,400 orders and ~R$1M GMV, roughly 40-50% above the surrounding months. November is Black Friday month in Brazil and drives significant spikes. **Any trend analysis crossing November should account for this seasonality.**

### December Drop
December 2017 shows a drop from November, likely post-Black-Friday normalization combined with the holiday period when logistics slow down. This is expected behavior, not a problem.

### Month-to-Month Comparisons
When comparing months, compare same-month year-over-year (Jan 2018 vs Jan 2017) rather than sequential months, to avoid conflating seasonality with growth.

---

## Metrics Glossary

| Metric | Definition | Filter  |
|---|---|---|
| GMV | SUM(price) from order items | Completed orders |
| TOV | SUM(price + freight_value) from order items | Completed orders |
| AOV | GMV / COUNT(DISTINCT order_id) | Completed orders  |
| Order Count | COUNT(DISTINCT order_id) | Completed orders |
| Cancellation Rate | Canceled / (Completed + Canceled) | Excl. created, unavailable |
| On-Time Delivery Rate | Delivered on-time / Total delivered | Delivered with both dates |
| Delivery Time | delivered_date - purchase_date (days) | Delivered orders |
| Carrier Handoff Time | carrier_date - approved_date (days) | Delivered orders |
| CSAT | % reviews scoring 4 or 5 | Orders with reviews |
| Dissatisfaction Rate | % reviews scoring 1 or 2 | Orders with reviews |
| Repeat Purchase Rate | Customers with 2+ orders / Total unique customers | By customer_unique_id|
| Freight Ratio | SUM(freight_value) / SUM(price) | Completed orders |
| Review Coverage | Orders with review / Total completed | All completed |
| Active Sellers | Sellers with 1+ completed order in period | Per period |
| Seller Concentration | % GMV from top N% sellers | Completed orders |
| New Customer Count | customer_unique_ids with first order in period | By first purchase date |