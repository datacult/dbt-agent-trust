# Evaluation Framework: Trust by Design

The core contribution of this project. A practical framework for evaluating whether an analytics agent's answers are correct.

## How it works

The evaluation pipeline (`eval_pipeline.py`) reads the per-question JSON files produced by the agent's batch runner, runs each golden question's expected SQL against DuckDB to get ground-truth results, and compares them against what the agent produced.

The comparison happens in two layers.

### Layer 1: Deterministic comparison

Compares actual query results, not SQL text. Many different SQL queries produce identical correct answers, so comparing query text tells you nothing about correctness. The comparison starts strict and relaxes deliberately through three stages:

1. **Strict**: results are identical in values, columns, and ordering
2. **Tolerant**: same values, but column names or ordering differ
3. **Approximate**: numeric values match within a configurable tolerance (default: 0.1% relative, 0.01 absolute)

If any stage concludes the results are equivalent, the question passes. If all three stages fail, the question goes to Layer 2.

### Layer 2: LLM-as-judge fallback

For cases where the deterministic comparison cannot reach a verdict, a second model reviews both result sets and the original question, then scores whether they convey the same business answer.

The judge supports any model provider via pydantic-ai's `provider:model` syntax. Configure in `config.yaml`:

```yaml
judge_model: anthropic:claude-sonnet-4-6
```

Or override per run:

```bash
python -m evaluation.eval_pipeline --judge-model openai:gpt-4o
```

The judge runs only when Layer 1 is inconclusive. Most questions are settled deterministically.

### Out-of-scope question handling

Golden questions without expected SQL (questions 38-40 in the default set) test whether the agent correctly declines questions it should not answer. The evaluation distinguishes four outcomes:

- **Graceful refusal**: agent correctly declined an out-of-scope question (pass)
- **False answer**: agent answered a question it should have declined (fail)
- **False refusal**: agent declined a question it should have answered (fail)
- **Correct answer**: agent answered and the result matches expected (pass)

## Running the evaluation

```bash
# Step 1: generate agent outputs (run once, or re-run after agent changes)
python -m agent.custom_orchestrator.run_golden_set

# Step 2: evaluate
python -m evaluation.eval_pipeline
```

Options:

```bash
# Skip the LLM judge (faster, no API cost)
python -m evaluation.eval_pipeline --no-judge

# Use a different judge model
python -m evaluation.eval_pipeline --judge-model openai:gpt-4o

# Point to a different agent outputs directory
python -m evaluation.eval_pipeline --agent-outputs path/to/outputs

# Use a different DuckDB file
python -m evaluation.eval_pipeline --duckdb path/to/olist.duckdb
```

## Output

The pipeline produces three things:

1. **Terminal scorecard**: pass rate overall, by difficulty, by category, with a list of failed questions and their failure reasons
2. **JSON file** in `evaluation/results/`: full per-question detail for programmatic analysis
3. **CSV file** in `evaluation/results/`: spreadsheet-friendly view for comparing runs after enrichment changes

The CSV includes question, category, difficulty, pass/fail, comparison stage, agent SQL, expected SQL, agent response, judge score, tokens, cost, and duration. Open it in a spreadsheet to review failures and track accuracy across enrichment iterations.

## Scope and limits

This is an educational reference implementation demonstrating the concepts of layered result comparison and LLM-as-judge evaluation for analytics agents.

A production evaluation system would include additional scoring dimensions, calibrated judge prompts tuned to specific domains, regression detection, monitoring, and alerting. Those are outside the scope of this reference.

The goal is to teach the approach clearly enough for a practitioner to understand it, adapt it to their own data, and build on it.

## Files

| File | Purpose |
|---|---|
| `eval_pipeline.py` | The full evaluation pipeline: comparison, judge, scorecard, and results export |
| `results/` | Output directory for evaluation runs (gitignored) |

## Configuration

The evaluation reads its settings from:

- **`config.yaml`** (in `agent/custom_orchestrator/`): `judge_model` key sets the default LLM judge model
- **`.env`** (repo root): API keys for the judge model provider (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.)