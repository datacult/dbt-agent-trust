# Data Foundation: The Metric Agent Playbook

**Owner: David Effiong**

This directory contains the dbt project that models the public dataset into governed metrics and dimensions. It is the foundation everything else in this repo builds on.

## What this layer provides

- **Staging models**: clean and standardize raw source data
- **Mart models**: business-ready fact and dimension tables with tests and documentation
- **Semantic layer**: metric definitions, dimensions, and entity relationships that give the agent governed access to the data

## Design decisions to document

As you build, capture the reasoning behind key choices in this README. These decisions are what make the playbook useful to someone adapting it for their own data:

- Why this data model structure (star schema, wide tables, or other)?
- How metrics are defined and why (which aggregations, which grain)
- What the semantic layer exposes and what it deliberately hides
- The tradeoffs between dbt Semantic Layer (MetricFlow) and agent schema, and which you chose and why
- What tests are included and what they catch

## Setup

```bash
cd dbt_project
dbt deps
dbt seed
dbt run
dbt test
```

## Dataset

[To be confirmed: the shared public dataset both halves of this project build on]

The dataset must be:
- Genuinely public and licensed for republication
- Analytically rich enough to support real business questions (not just trivial lookups)
- Suitable for modeling into governed metrics with interesting edge cases