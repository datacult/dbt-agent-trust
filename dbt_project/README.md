# The Metric Agent Playbook: a dbt Agent Schema

**Owner: David Effiong**

The data foundation for a **trusted, warehouse-native metrics layer that an AI agent can query directly.** It models a public dataset into governed marts, then publishes the models, their column meanings, and the business rules into an **Agent Schema**, a standard `AGENTS` schema of tables the agent reads to learn what it can query and how.

## Why Agent Schema (and not the dbt Semantic Layer)

This project started toward the dbt Semantic Layer (MetricFlow) and deliberately chose **Agent Schema** instead:

- **Runs anywhere, no Cloud.** The Semantic Layer's agent-facing API is a dbt Cloud feature. Agent Schema is just SQL tables in the warehouse and it works on local DuckDB with an MCP server, so anyone can clone this repo and reproduce it.
- **Flexible.** The agent reads context and rules and writes its own SQL, so it can answer questions no one pre-modeled, not only predefined metrics.
- **Portable.** No runtime or no lock-in; the same pattern works on DuckDB, Snowflake, or BigQuery. For Snowflake, BigQuery or DataBricks users, you can refer to AgentSchema official docs as those destinations are supported out of the bucket. 

There is a trade-off. Your metric definitions can live in markdown files and sent to agent.root like `olist_business_context.md`, they are authoritative, and when they include the SQL pattern the agent follows them closely making sure answers are highly accurate. The difference though is that  the Semantic Layer *compiles* a metric deterministically (same definition → same SQL every time), while the agent *generates* SQL from that definition which is an LLM step that is highly accurate with a good guide but not deterministically guaranteed. That's why accuracy of your metrics/context layer is determined the golden-question evaluation.

> On dbt Cloud and want compiler-guaranteed metrics? The Semantic Layer is the alternative. This playbook shows the warehouse-native path that works everywhere, including locally.

## What this layer provides

- **Staging models** : clean and standardize the raw source data
- **Mart models** : business-ready fact and dimension tables, tested and documented
- **Agent Schema context** : the `AGENTS` schema: governed marts plus in-warehouse metadata (model + column descriptions, metric definitions, scope boundaries) the agent reads before writing SQL

## How it works

```
dbt marts (fct_*, dim_*)  +  column descriptions  +  business_context.md
              │
              ▼   build_agents_schema macro (auto-run at the end of every dbt build)
        AGENTS schema, inside olist.duckdb
        ├─ agents.root         business rules, metric definitions, scope boundaries
        ├─ agents.dbt_model    one row per exposed mart
        ├─ agents.dbt_column   one row per column (with descriptions)
        └─ agents.dbt_dependency
              │
              ▼
   Agent reads agents.root (rules) + agents.dbt_column (where things live),
   then writes SQL against the marts.
```

## Prerequisites

- **git**, and this repo cloned.
- **dbt Fusion** (v2.0.0-preview.200+). Fusion is a standalone binary — **not** `pip install`-able and **not** dbt Core. Install via the official dbt Fusion installer, then confirm: `dbt --version` → `dbt-fusion 2.0.x`.
- **No database to install** : DuckDB is embedded in the adapter. No server, no credentials. The warehouse is one local file (`olist.duckdb`), created on first build.
- **No Python/venv needed** to run dbt. (`.venv` is only for tooling.)

## Setup (clone → agent-ready in 3 commands)

```bash
git clone <repo-url>
cd dbt-agent-trust/dbt_project      # run all dbt commands from here

dbt deps      # install package dependencies
dbt seed      # load the committed Olist CSVs into olist.duckdb
dbt build     # models + tests + the AGENTS schema, all in one
```

`profiles.yml` ships inside this folder (DuckDB target, no credentials) and Fusion finds it automatically. The `AGENTS` schema is built automatically at the end of `dbt build` via an `on-run-end` hook — no extra step.

**Verify:**
```bash
dbt show --inline "select round(sum(gmv_amount),2) as gmv from main.fct_order_items where is_completed"
# ~13,500,000  (total GMV)

duckdb -readonly olist.duckdb "SELECT provider, key FROM agents.root; SELECT name FROM agents.dbt_model;"
# agents.root rules + business_context; only fct_*/dim_* exposed
```

## Testing with an agent

Connect a DuckDB MCP server to `olist.duckdb`, then set one **standing instruction** in your agent/project prompt:

> "This warehouse uses an AGENTS schema. Before answering any data question, read `agents.root` for the rules and scope, and `agents.dbt_model` / `agents.dbt_column` to find the right models. Only query the marts. If a question is out of scope per `agents.root`, decline."

Then ask business questions in plain language, the agent consults the context on its own. It answers in-scope questions (e.g. "GMV for Q1 2018") and declines out-of-scope ones (e.g. "profit margin", no cost data).

## The AGENTS schema

Four tables, following the [dbt-labs/agents_schema](https://github.com/dbt-labs/agents_schema) spec:

| Table | Holds |
|---|---|
| `agents.root` | Business rules, metric definitions, scope boundaries (from `olist_business_context.md`) + provider docs |
| `agents.dbt_model` | One row per exposed mart model |
| `agents.dbt_column` | One row per column, with descriptions |
| `agents.dbt_dependency` | Dependency edges between exposed models |

Only **mart** models (tagged `agent`) are exposed with staging and intermediate models are intentionally hidden. The tables are **regenerated on every build**, so your `.yml` descriptions and `business_context.md` are the single source of truth. Never hand-edit the `AGENTS` tables, edit the source and re-run `dbt build`. If rebuilding at every dbt build is too frequent, you can make updates to recreate the agent schema based on your required cadance. 

## Using Agent Schema as a real-world metrics / context layer

### Do I define metrics in code, or can I just write them in a doc?
**In a doc and that's the point.** Your metric definitions live in a markdown file (`olist_business_context.md`), which the build loads into `agents.root`. The agent reads those definitions and uses them as a **guide to write SQL**, instead of inventing a query from scratch. The more precise the guide, the less the agent improvises:

```markdown
GMV = SUM(price) on completed orders. Excludes freight, canceled, and unavailable orders.
  SQL pattern: SUM(gmv_amount) FROM fct_order_items WHERE is_completed [+ your date/filter]
```

Given that, the agent mostly just fills in the filters without guessing how GMV is defined. This is how Agent Schema gets close to consistent answers without a compiler: **the definition is the guide; the agent adapts it.**

### Where do I put generic business rules e.g. "exclude certain order/appointment types from this metric"?
In **`agents.root`**, via your context markdown. ROOT is free-form context (`provider`, `key`, `content`) and is **not tied to any table**, so cross-cutting rules belong there:

```markdown
Completed order = status in (delivered, shipped, processing, invoiced, approved).
Exclude 'canceled' and 'unavailable' from ALL revenue and performance metrics.
```

That's exactly how our GMV exclusions work. For a clinic you'd write "exclude no-show and cancelled appointment types from utilization" as a ROOT rule, and every metric that touches it inherits the rule.

### Is there a place for general context vs. context tied to a specific table?
**Yes, two distinct layers, by design:**

| Layer | Table | Holds |
|---|---|---|
| **Generalized** (not tied to a table) | `agents.root` | Metric definitions, business rules, exclusions, scope boundaries, domain overviews |
| **Table/column-specific** | `agents.dbt_model` / `agents.dbt_column` | "This model is…", "this column means…" — from your `.yml` descriptions |

So a rule like "exclude cancelled orders" lives in `root` (it spans tables), while "`gmv_amount` = item price in BRL" lives on the column in `dbt_column`. The agent reads both: `root` for *how to think*, `dbt_column` for *where things are*.

### How do I guide the agent across multiple domains (product, marketing, finance, etc)?
Make **`agents.root` a router** and tag models by domain:

1. **Tag models with their domain** in `dbt_project.yml` — the macro already captures `meta` into `agents.dbt_model`:
   ```yaml
   models:
     my_project:
       marketing: { +tags: ['agent'], +meta: {domain: marketing} }
       product:   { +tags: ['agent'], +meta: {domain: product} }
   ```
   The agent can then narrow: `select name from agents.dbt_model where meta->>'domain' = 'marketing';`
2. **Give each domain its own `root` rows** as an overview and its own rules/scope. Add one context file per domain to the macro's `context_files` list:
   ```jinja
   {% set context_files = [
       ('olist',     'business_context', 'olist_business_context.md'),
       ('marketing', 'context',          'marketing_context.md'),
       ('product',   'context',          'product_context.md')
   ] %}
   ```

The flow becomes: **read `root` → match the question to a domain → query only that domain's models and rules.** Each domain owns its exposed models, descriptions, and scope, so domains stay governed and isolated.

### Does the agent scan the entire schema for every prompt?
**No.** For a large project the agent reads a slice proportional to the question, not the whole catalog:
- **`agents.root` is small** (domain + rule rows) and read **once per session** as a router.
- **Detail tables are queried with filters, not dumped:** `... where meta->>'domain' = 'marketing'` or `where description ilike '%CAC%'` returns a handful of rows.
- **Within a session, context is cached** in the model's window so it isn't re-read on every follow-up.

Cost scales with the **question**, not the project size. (The one dependency: your standing instruction should tell the agent to *narrow by domain first*, not scan everything — the schema is built to be queried selectively, but the prompt makes it happen.)

### Can I see exactly what context the agent uses at runtime?
**Yes, because it's all just SQL tables, nothing is hidden.** There is no opaque semantic-layer runtime: the "instructions" the agent sees are literally the rows it queried. You can inspect the full available context at any time:
```sql
select provider, key, content from agents.root;
select model_id, column_name, description from agents.dbt_column;
```
What was *actually read on a given turn* is visible in your **MCP/agent tool-call logs** (they record each query the agent ran). Transparency comes from both: the context is fully inspectable, and the runtime trace is your client's tool-call log. That auditability is a direct benefit of putting context *in the warehouse* rather than behind a service.

### How do I update the context, and can the agent write to my data?
- **Update:** edit the source (`.yml` descriptions or `business_context.md`) and re-run `dbt build`. The `agents.*` tables are **regenerated every build** (or at your preferred cadance).
- **Safety:** connect the MCP server **read-only** (the agent can't modify data), and expose **only mart models** (`+tags: ['agent']`) — staging, intermediate, and any sensitive columns you don't tag stay invisible. Governance is *what you expose* + *read-only access* + *scope rules in `root`*.

> When in doubt about table shapes or conventions, refer to the spec: [dbt-labs/agents_schema](https://github.com/dbt-labs/agents_schema).

## Apply this to your own dbt project

1. **Tag your marts** `+tags: ['agent']` so only they are exposed.
2. **Write clear column descriptions** in your `.yml` — these become the agent's field-level context.
3. **Write a `business_context.md`** with your metric definitions (and their SQL patterns) plus an *out-of-scope / data boundaries* section.
4. **Add the `build_agents_schema` macro** and the `on-run-end` hook.
5. **`dbt build`**, connect an MCP server, set the standing instruction. 


## Design decisions

**Why a star schema?** The questions live at different grains including revenue per order-item, delivery per order, satisfaction per review, payments per payment. One wide table would fan out and double-count. Separate fact tables plus shared dimensions keep every number correct and define things like region once.

**How metrics are defined.** Each metric is defined once so the agent computes it the same way every time: GMV = `SUM(price)` on completed orders (no freight); AOV = GMV ÷ distinct completed orders; CSAT = % of reviews scored 4–5; repeat customer = a `customer_unique_id` with 2+ completed orders. The marts store the *ingredients* (`gmv_amount`, flags); the metric is the aggregation the agent writes, guided by `business_context.md`.

**What the agent sees.** Clean marts with business names, ready-made flags, region/department filled in, and a description on every column. It does **not** see raw sources, intermediate models, or staging.

**Why Agent Schema, not a semantic layer.** See the section above, including flexibility and portability, with correctness verified by tests + evaluation.

**What the tests catch.** `unique`/`not_null` on grain keys (dupes/fan-out), `relationships` (broken joins), `accepted_values` (bad/unmapped categoricals), plus a business-value acceptance gate (GMV ≈ 13.5M, freight ≈ 16.6%, repeat ≈ 3.1%).

## Dataset

[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). ~100k orders, Sep 2016–Aug 2018, all values in BRL. **Geolocation excluded** — no benchmark question needs lat/long coordinates; state/region come from the customer and seller tables.

## Evaluation

Correctness is verified against `olist_golden_questions.csv` (40 benchmark questions with expected SQL) by a **separate evaluation framework** maintained by Opeyemi Fabiyi. The benchmark lives outside this dbt project because it's an evaluation artifact, not a dbt asset.

## Dataset

[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)

## Data model (ERD)


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