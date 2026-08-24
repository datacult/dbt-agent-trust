from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

_INSTRUCTIONS = """You are a governed analytics agent for the Olist e-commerce dataset.

Answer each business question by writing DuckDB SQL and running it with the
execute_query tool. The schema and business rules are NOT inlined here — discover
them at runtime through the `agents.*` metadata catalog, walking this chain in order:

1. Read the router. Start by running this query:

select
  provider,
  key,
  content
from agents.root
order by
  provider,
  key

   The returned rows are your map. `business_context` holds the metric
   definitions, filters (e.g. what counts as a completed order), timezone rules,
   and the in-scope reporting window; read it fully and follow it exactly rather
   than restating a metric from memory. The `dbt/*` rows point to the catalog
   tables below.

2. List the models. Read `agents.dbt_model` to see the exposed marts and their
   descriptions, then choose the correct grain for the question

3. Read the columns. For each mart you intend to query, read its documented
   columns from `agents.dbt_column`. Prefer the documented helper
   columns the modelers provide — pre-computed flags and localized timestamps —
   over recomputing that logic yourself.

4. Then query the marts. List the models and read a mart's columns before you
   query it. Query only the exposed marts for the answer — never staging,
   intermediate, information_schema, or the `agents` schema.

Base every answer on a query you actually ran; never invent SQL or numbers. If
the question is out of scope per the business context, or cannot be answered from
the exposed marts, decline and briefly explain why instead of guessing.
"""


def _connect(duckdb_path: str | Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(duckdb_path), read_only=True)


def _qualified_relation(database: str, schema: str, name: str) -> str:
    """Return the exact three-part DuckDB relation name."""
    if not database or not schema or not name:
        raise RuntimeError("Every exposed mart must have a database, schema, and name.")
    return f"{database}.{schema}.{name}"


def _allowed_relations(con: duckdb.DuckDBPyConnection) -> set[str]:
    rows = con.execute(
        "select database_name, schema_name, name from agents.dbt_model"
    ).fetchall()
    relations = {
        _qualified_relation(database, schema, name).lower()
        for database, schema, name in rows
    }
    if not relations:
        raise RuntimeError("The agent schema contains no exposed mart models.")
    return relations


def _agents_metadata_relations(con: duckdb.DuckDBPyConnection) -> set[str]:
    """The curated `agents.*` catalog the model may read to discover schema and rules.

    This is app code reading `information_schema` to build the allowlist — it is not
    model SQL, so it is unaffected by the model-facing ban on `information_schema`.
    """
    rows = con.execute(
        "select table_catalog, table_schema, table_name "
        "from information_schema.tables where table_schema = 'agents'"
    ).fetchall()
    return {f"{catalog}.{schema}.{name}".lower() for catalog, schema, name in rows}


# Leaf plan operators that read no external data (constants, CTE refs, empty
# results). Any OTHER leaf with no `Table` is treated as a forbidden data source
# and rejected. This is fail-closed on purpose: DuckDB represents file-reading
# table functions such as read_csv/read_parquet as named leaf operators (e.g.
# READ_CSV) that carry neither a `Table` nor a `Function` field, so enumerating
# the benign operators is what actually blocks arbitrary-file reads.
_INTERNAL_LEAF_OPERATORS = {
    "COLUMN_DATA_SCAN",
    "CTE_SCAN",
    "DELIM_GET",
    "DUMMY_SCAN",
    "EMPTY_RESULT",
    "EXPRESSION_GET",
}


def _plan_sources(plan: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    tables: set[str] = set()
    other_sources: set[str] = set()
    stack = list(plan)

    while stack:
        node = stack.pop()
        extra_info = node.get("extra_info") or {}
        children = node.get("children") or []
        table = extra_info.get("Table")
        if table:
            tables.add(str(table).lower())
        if function := extra_info.get("Function"):
            other_sources.add(str(function))
        if (
            not children
            and not table
            and node.get("name") not in _INTERNAL_LEAF_OPERATORS
        ):
            other_sources.add(str(node.get("name", "unknown")))
        stack.extend(children)

    return tables, other_sources


def _validate_sql(con: duckdb.DuckDBPyConnection, sql: str) -> None:
    if not sql or not sql.strip():
        raise ValueError("SQL cannot be empty.")

    try:
        statements = con.extract_statements(sql)
    except duckdb.Error as exc:
        raise ValueError(f"SQL could not be parsed: {exc}") from exc
    if len(statements) != 1 or statements[0].type.name != "SELECT":
        raise ValueError("Only one SELECT statement is allowed.")

    con.execute("set explain_output = 'all'")
    try:
        plans = con.execute(f"explain (format json) {sql}").fetchall()
    except duckdb.Error as exc:
        raise ValueError(f"SQL could not be planned: {exc}") from exc
    logical_plan_json = next(
        (content for plan_type, content in plans if plan_type == "logical_plan"),
        None,
    )
    if logical_plan_json is None:
        raise ValueError("DuckDB did not produce a logical query plan.")

    tables, other_sources = _plan_sources(json.loads(logical_plan_json))
    if other_sources:
        names = ", ".join(sorted(other_sources))
        raise ValueError(f"Non-mart data sources are not allowed: {names}.")
    if not tables:
        raise ValueError("The query must read from at least one exposed relation.")

    # Marts (for analytical answers) plus the curated agents.* catalog (for discovery).
    allowed = _allowed_relations(con) | _agents_metadata_relations(con)
    disallowed = tables - allowed
    if disallowed:
        names = ", ".join(sorted(disallowed))
        raise ValueError(f"Query references non-exposed relations: {names}.")


def _assert_contract_ready(duckdb_path: str | Path) -> None:
    """Fail fast if the governed context the model discovers at runtime is missing."""
    con = _connect(duckdb_path)
    try:
        row = con.execute(
            "select content from agents.root "
            "where provider = 'olist' and key = 'business_context'"
        ).fetchone()
    finally:
        con.close()

    if row is None or not (row[0] or "").strip():
        raise RuntimeError("agents.root is missing a non-empty olist/business_context row.")


def load_contract(duckdb_path: str | Path) -> str:
    """The application-owned instructions passed to the model as its system prompt."""
    _assert_contract_ready(duckdb_path)
    return _INSTRUCTIONS.strip()


def validate_sql_readonly(duckdb_path: str | Path, sql: str) -> None:
    """Validate that one read-only query accesses only exposed marts."""
    con = _connect(duckdb_path)
    try:
        _validate_sql(con, sql)
    finally:
        con.close()


def run_sql_readonly(duckdb_path: str | Path, sql: str) -> list[dict[str, Any]]:
    """Validate and execute one governed query, returning dictionaries."""
    con = _connect(duckdb_path)
    try:
        _validate_sql(con, sql)
        cursor = con.execute(sql)
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        con.close()
