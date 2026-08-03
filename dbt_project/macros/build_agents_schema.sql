{%- macro _agents_str(v) -%}
  {%- if v is none -%}null{%- else -%}'{{ v | string | replace("'", "''") }}'{%- endif -%}
{%- endmacro -%}

{% macro build_agents_schema() %}
  {% if not execute %}{{ return('') }}{% endif %}

  {# 1. schema + tables (DuckDB types: VARIANT->JSON, TEXT ok) #}
  {% do run_query('create schema if not exists agents') %}
  {% do run_query('create or replace table agents.root (provider varchar not null, key varchar not null, content text not null, primary key (provider, key))') %}
  {% do run_query('create or replace table agents.dbt_model (unique_id varchar not null, name varchar not null, database_name varchar, schema_name varchar, materialization varchar, description text, file_path varchar, tags json, meta text, primary key (unique_id))') %}
  {% do run_query('create or replace table agents.dbt_column (model_id varchar not null, column_name varchar not null, data_type varchar, description text, primary key (model_id, column_name))') %}
  {% do run_query('create or replace table agents.dbt_dependency (upstream_id varchar not null, downstream_id varchar not null, upstream_type varchar, downstream_type varchar, primary key (upstream_id, downstream_id))') %}

  {# 2. determine the exposed set: only models tagged 'agent' (the marts) #}
  {% set exposed = [] %}
  {% for node in graph.nodes.values() if node.resource_type == 'model' and 'agent' in node.tags %}
    {% do exposed.append(node.unique_id) %}
  {% endfor %}

  {# 3. read the in-memory manifest for exposed models only #}
  {% set models = [] %}{% set columns = [] %}{% set deps = [] %}
  {% for node in graph.nodes.values() if node.resource_type == 'model' and 'agent' in node.tags %}
    {% set meta = node.config.meta if node.config.meta else node.meta %}
    {% do models.append('(' ~ _agents_str(node.unique_id) ~ ',' ~ _agents_str(node.name) ~ ',' ~ _agents_str(node.database) ~ ',' ~ _agents_str(node.schema) ~ ',' ~ _agents_str(node.config.materialized) ~ ',' ~ _agents_str(node.description or '') ~ ',' ~ _agents_str(node.original_file_path) ~ ',' ~ _agents_str(tojson(node.tags)) ~ ',' ~ _agents_str(tojson(meta)) ~ ')') %}
    {% for col in node.columns.values() %}
      {% do columns.append('(' ~ _agents_str(node.unique_id) ~ ',' ~ _agents_str(col.name) ~ ',' ~ _agents_str(col.data_type or '') ~ ',' ~ _agents_str(col.description or '') ~ ')') %}
    {% endfor %}
    {% for up in node.depends_on.nodes if up in exposed %}
      {% do deps.append('(' ~ _agents_str(up) ~ ',' ~ _agents_str(node.unique_id) ~ ',' ~ _agents_str(up.split('.')[0]) ~ ",'model')") %}
    {% endfor %}
  {% endfor %}

  {# 4. write rows #}
  {% if models | length %}{% do run_query('insert into agents.dbt_model values ' ~ (models | join(','))) %}{% endif %}
  {% if columns | length %}{% do run_query('insert into agents.dbt_column values ' ~ (columns | join(','))) %}{% endif %}
  {% if deps | length %}{% do run_query('insert into agents.dbt_dependency values ' ~ (deps | join(','))) %}{% endif %}

  {# 5. provider docs + business context in ROOT #}
  {% set root = [
    "('dbt','overview','dbt mart models the agent may query: fact and dimension tables. Read AGENTS.DBT_MODEL and AGENTS.DBT_COLUMN for details. Only these marts are exposed; staging and intermediate models are intentionally hidden.')",
    "('dbt','model','AGENTS.DBT_MODEL - one row per exposed mart model: name, schema, materialization, description.')",
    "('dbt','column','AGENTS.DBT_COLUMN - one row per documented column: model_id, column_name, data_type, description.')",
    "('dbt','dependency','AGENTS.DBT_DEPENDENCY - one row per DAG edge between exposed models: upstream_id -> downstream_id.')"
  ] %}
  {% do run_query('insert into agents.root values ' ~ (root | join(','))) %}

  {# load the human-authored business rules + scope boundaries straight from the markdown #}
  {% do run_query("insert into agents.root select 'olist', 'business_context', content from read_text('olist_business_context.md')") %}

  {{ log('AGENTS built (marts only): ' ~ (models|length) ~ ' models, ' ~ (columns|length) ~ ' columns, ' ~ (deps|length) ~ ' deps, + business_context.', info=true) }}
{% endmacro %}
