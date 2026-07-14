# Agent Layer

**Owner: Joseph Ojo**

This layer connects a language model to the dbt semantic layer via MCP so it can answer natural language business questions against the governed data.

## What this layer does

1. Takes a natural language question
2. Sends it to Claude with the dbt MCP server available as a tool
3. Claude uses the MCP tools to query the governed metrics and dimensions
4. Captures the response (the answer, any SQL generated, the raw result)
5. Writes the output to a structured file the evaluation layer can read

## What this layer does NOT do

- Evaluate whether the answer is correct (that is the evaluation layer's job)
- Implement any custom agent logic beyond connecting Claude to the dbt MCP tools
- Lock to a specific model (the config should make it easy to swap Claude for another model)



## Output format

Each question produces one JSON file in `agent_outputs/`:

```json
{
  "question_id": "rev_001",
  "question": "What was the total revenue last quarter?",
  "model": "claude-sonnet-4-6",
  "timestamp": "2026-07-14T10:30:00Z",
  "agent_response": "The total revenue last quarter was $1,234,567.",
  "agent_sql": "SELECT SUM(revenue) FROM ...",
  "agent_result": [{"total_revenue": 1234567}],
  "tool_calls": [
    {"tool": "query_metric", "input": {"metric": "total_revenue", "grain": "quarter"}, "output": "..."}
  ],
  "n_turns": 1,
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

1. Ensure the dbt project is built and the semantic layer is serving
2. Configure the dbt MCP server (see [dbt MCP docs](https://github.com/dbt-labs/dbt-mcp))
3. Copy `config.yaml.example` to `config.yaml` and set your model and MCP server details
4. Set `ANTHROPIC_API_KEY` in the root `.env` file

## Usage

```bash
# Single question
python agent.py "What was the total revenue last quarter?"

# All golden questions
python run_golden_set.py
```