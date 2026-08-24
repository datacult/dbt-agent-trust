# Agent Layer

**Owner: Joseph Ojo**

This layer connects a configured language model to the governed Olist marts in
DuckDB through MCP.

## What this layer does

1. Takes a natural language question
2. Gives the configured model the generated contract and DuckDB query tool
3. Restricts queries to the mart relations exposed in the contract
4. Returns the answer, final SQL, canonical query result, and run metadata

## What this layer does NOT do

- Evaluate whether the answer is correct (that is the evaluation layer's job)
- Expose staging, intermediate, or other non-mart relations
- Lock to a specific model



## Output format

The evaluation runner writes one JSON record per question to `agent_outputs/`.
The single-question CLI prints the same record to standard output.

```json
{
  "question_id": "rev_001",
  "question": "What was total GMV?",
  "model": "openai:gpt-5-nano",
  "timestamp": "2026-07-14T10:30:00Z",
  "agent_response": "Total GMV was 1,234,567.",
  "agent_sql": "select sum(gmv_amount)  as  total_gmv from fct_order_items where is_completed",
  "agent_result": [{"total_gmv": 1234567}],
  "tool_calls": [
    {"tool": "execute_query", "input": {"sql": "select sum(gmv_amount)  as  total_gmv from fct_order_items where is_completed"}, "output": "..."}
  ],
  "n_requests": 1,
  "metric_queried": "total_revenue",
  "declined_or_clarified": false,
  "tokens": 48339,
  "cost": 0.1152,
  "duration_ms": 45821,
  "error": null,
  "error_type": null
}
```

The evaluation layer reads `agent_sql` and `agent_result`. Everything else is metadata for debugging.

## Setup

1. Build the dbt project so the marts and `agents` schema tables exist in DuckDB.
2. Copy `config.yaml.example` to `config.yaml` and set the model, DuckDB path,
   and MCP executable as needed.
3. Set the matching provider API key in the root `.env` file. See `.env.example`.

## Usage

```bash
# Single question (this layer only answers one question at a time)
python -m agent.custom_orchestrator.agent "What was the total revenue last quarter?"
```

Running the whole golden set is an evaluation-orchestration concern and lives in the
evaluation layer: `python -m evaluation.run_golden_set` (see `evaluation/README.md`).
It imports this layer's public API (`build_agent`, `answer_with`) and writes one
output JSON record per question for evaluation.

To expose the agent to an MCP client over stdio, run:

```bash
python -m agent.custom_orchestrator.mcp_server
```
