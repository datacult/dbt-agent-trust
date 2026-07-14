# Evaluation Framework: Trust by Design

**Owner: Opeyemi Fabiyi**

The core contribution of this project. A practical framework for evaluating whether an analytics agent's answers are correct.

## How it works

### Layer 1: Deterministic comparison (`comparison.py`)

Compares actual query results, not SQL text. Staged from strict to tolerant:

1. **Strict match**: identical values, columns, and ordering
2. **Column-tolerant match**: same values, different column names or ordering
3. **Approximate numeric match**: values within a defined tolerance

If any stage concludes equivalence, the question passes. If all fail, the question goes to Layer 2.

### Layer 2: LLM-as-judge fallback (`judge.py`)

For cases where the deterministic comparison cannot reach a verdict. A second model reviews both results and the original question, scores whether they convey the same business answer.

Runs only when Layer 1 is inconclusive. Most questions are settled deterministically.

### Output

A scorecard showing per-question results and an aggregate pass rate: the percentage of golden questions where the agent's answer is functionally correct regardless of SQL or formatting differences.

## Scope and limits

This is an educational reference implementation demonstrating the concepts of layered result comparison and LLM-as-judge evaluation for analytics agents.

A production evaluation system would include additional scoring dimensions, calibrated judge prompts tuned to specific domains, regression detection, monitoring, and alerting. Those are outside the scope of this reference.

The goal is to teach the approach clearly enough for a practitioner to understand it, adapt it to their own data, and build on it.

## Files

| File | Purpose |
|---|---|
| `run_eval.py` | Orchestrator: loads agent outputs + expected results, runs comparison |
| `comparison.py` | Layered deterministic comparison |
| `judge.py` | LLM-as-judge fallback |
| `judge_prompt.txt` | Judge prompt template |
| `scorecard.py` | Human-readable scorecard generator |
| `results/` | Output directory (gitignored) |