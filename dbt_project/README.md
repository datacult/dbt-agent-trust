# Data Foundation: The Metric Agent Playbook

**Owner: David Effiong**

This directory contains the dbt project that models the public dataset into governed metrics and dimensions. It is the foundation everything else in this repo builds on.

## What this layer provides

- **Staging models**: clean and standardize the raw Olist data
- **Mart models**: business-ready fact and dimension tables, with tests and documentation
- **Agent Schema context**: governed marts plus in-warehouse metadata the agent reads to
  understand what it can query and what each field means


## Why a star schema?

Our questions ask for numbers at different levels: revenue is per **order item**, delivery is per **order**, satisfaction is per **review**, payments are per **payment**. So we use a **star schema**: one fact table per level, plus shared dimension tables (customers, sellers, products, dates) that every fact can join to. This keeps every number correct and defines things like "region" in one place.

## How metrics are defined

Each metric is defined once, so the agent always computes it the same way:

- **GMV** = sum of item `price` on completed orders. No freight, no canceled orders. (~R$13.5M)
- **TOV** = sum of `price + freight` on completed orders.
- **AOV** = GMV ÷ number of completed orders (not number of items).
- **Completed order** = status is delivered, shipped, processing, invoiced, or approved.
- **CSAT** = % of reviews scored 4 or 5 (not the average score).
- **Repeat customer** = a person (`customer_unique_id`) with 2 or more completed orders. (~3.1%)
- **On-time / delivery time** = date math on delivered orders only.
- **Region** and **department** are simple lookups from state and product category.

## What the agent sees, and what it doesn't

**Sees:** the clean marts, clear names (`gmv_amount`, not `price`), ready-made flags (`is_completed`, `is_on_time`), region and department already filled in, and a description for every column.
**Doesn't see:** the raw source tables (messy names, Portuguese categories, no flags), the in-between models, or the geolocation data (we dropped it as no question needs map coordinates). The agent only works with the clean tables, so it never has to guess how a metric is built.

## Why Agent Schema (not a semantic layer) as Metrics Layer

We chose **Agent Schema**: we publish context as tables in the warehouse, and the agent reads them and writes its own SQL. A semantic layer is stricter — the agent can only ask for metrics we defined ahead of time and it needs a special runtime (the hosted version is a dbt Cloud feature). Agent Schema is more flexible (it can answer questions we didn't plan for), fully portable (just SQL tables, works on any warehouse including DuckDB, no runtime needed), and easy for anyone to copy into their own warehouse.

The catch: because the agent writes its own SQL, we can't rely on guardrails for correctness — we rely on **testing and evaluation** instead, which is what the golden questions and the LLM judge in this repo are for.

## What the tests catch

- **`unique` + `not_null`** on every ID column to catch duplicate or missing rows.
- **`relationships`** — catches facts that point to a customer, product, or order that doesn't exist.
- **`accepted_values`** on status, payment type, review score, region, and department — catches bad or unmapped values (like a state that never got assigned a region).


## Setup

## Prerequisites

- **git**, and this repo cloned.
- **dbt Fusion** (v2.0.0-preview.200+). Fusion is a standalone binary — **not** `pip install`-able,
  and **not** dbt Core. Install via the official dbt Fusion installer
  (docs.getdbt.com/docs/fusion/install-fusion), then confirm:

      dbt --version    # → dbt-fusion 2.0.x

- **No database to install** — DuckDB is embedded in the adapter. No server, no credentials.
  The warehouse is a single local file (`olist.duckdb`) created on first build.
- **No Python/venv needed** to run the dbt project. (`.venv` + `requirements.txt` are only for the
  agent and evaluation tooling.)

## Run it (clone → results in 3 commands)

```bash
git clone <repo-url>
cd dbt-agent-trust/dbt_project      # run all dbt commands from here

dbt deps      # install package dependencies (dbt_utils, etc.)
dbt seed      # load the committed Olist CSVs into olist.duckdb
dbt build     # run all models + tests in dependency order
```

`profiles.yml` ships inside this folder (DuckDB target, no credentials) and Fusion discovers it automatically — no `~/.dbt/` setup required.

### Verify it worked

```bash
dbt show --inline "select round(sum(gmv_amount),2) as gmv from main.fct_order_items where is_completed"
# → ~13,500,000  (total GMV, matches the business context)
```


## Dataset

[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)



```mermaid                                                
  erDiagram
      dim_customers ||--o{ fct_order_items    : "buys"
      dim_customers ||--o{ fct_orders         : "places"                                                   
      dim_products  ||--o{ fct_order_items    : "sold as"                                                  
      dim_sellers   ||--o{ fct_order_items    : "fulfills"                                                 
      dim_dates     ||--o{ fct_order_items    : "purchased on"                                             
      dim_dates     ||--o{ fct_orders         : "purchased on"
      dim_dates     ||--o{ fct_order_reviews  : "purchased on"                                             
      dim_dates     ||--o{ fct_order_payments : "purchased on"
                                                                                                           
      fct_orders    ||--o{ fct_order_items    : "contains"  
      fct_orders    ||--o{ fct_order_reviews  : "has"                                                      
      fct_orders    ||--o{ fct_order_payments : "paid by"                                                  
  
      dim_customers {                                                                                      
          string  customer_unique_id PK                     
          string  customer_state                                                                           
          string  customer_region
          string  customer_city                                                                            
          date    first_purchased_at                        
          date    last_purchased_at
          int     completed_order_count
          bool    is_repeat_buyer                                                                          
      }
                                                                                                           
      dim_products {                                        
          string  product_id PK
          string  product_category_name
          string  product_department
          int     product_weight_g
      }                                                                                                    
  
      dim_sellers {                                                                                        
          string  seller_id PK                              
          string  seller_state
          string  seller_region
          string  seller_city
      }

      dim_dates {
          date    date_day PK                                                                              
          int     year
          int     quarter                                                                                  
          int     month                                     
          int     iso_week
          date    week_start_date
          date    month_start_date
          date    quarter_start_date
          string  year_quarter                                                                             
      }
                                                                                                           
      fct_order_items {                                     
          string  order_item_pk PK
          string  order_id FK
          string  product_id FK
          string  seller_id FK
          string  customer_unique_id FK                                                                    
          bool    is_completed
          bool    is_intra_state                                                                           
          string  customer_region                           
          string  seller_region
          string  product_department
          decimal gmv_amount                                                                               
          decimal freight_amount
          decimal tov_amount                                                                               
          timestamp purchased_at                            
      }

      fct_orders {
          string  order_id PK
          string  customer_unique_id FK
          string  order_status                                                                             
          bool    is_completed
          bool    is_delivered                                                                             
          bool    is_canceled                               
          timestamp purchased_at
          timestamp delivered_to_customer_at
          timestamp estimated_delivery_at                                                                  
          int     delivery_time_days
          int     carrier_handoff_days                                                                     
          bool    is_on_time                                
          bool    is_late                                                                                  
          int     days_late
      }                                                                                                    
                                                            
      fct_order_reviews {
          string  review_pk PK
          string  review_id
          string  order_id FK
          int     review_score
          bool    is_positive_review                                                                       
          bool    is_negative_review
          timestamp review_created_at                                                                      
      }                                                     

      fct_order_payments {
          string  order_payment_pk PK
          string  order_id FK
          string  payment_type                                                                             
          int     payment_installments
          decimal payment_value                                                                            
      }                                                     
  ```  