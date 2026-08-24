"""Evaluation pipeline for governed analytics agents.

Reads the per-question JSON files produced by run_golden_set.py, runs expected
SQL against DuckDB to get ground-truth results, compares them through a layered
comparison (strict -> tolerant -> approximate -> LLM judge fallback), and produces
a scorecard and exportable results.

Usage:
    python -m evaluation.eval_pipeline
    python -m evaluation.eval_pipeline --no-judge
    python -m evaluation.eval_pipeline --judge-model openai:gpt-4o
    python -m evaluation.eval_pipeline --agent-outputs agent/agent_outputs

This is an educational reference implementation. It demonstrates the concepts of layered result comparison and 
LLM-as-judge evaluation for analytics agents. A production system would include additional scoring dimensions, calibrated judge prompts, monitoring, and regression detection.
This pipeline can be extended to include that.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUTS = REPO_ROOT / "agent" / "agent_outputs"
DEFAULT_QUESTIONS = REPO_ROOT / "golden_questions" / "olist_golden_questions.csv"
DEFAULT_DUCKDB = REPO_ROOT / "dbt_project" / "olist.duckdb"
DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent / "results"

# Tolerances for approximate numeric comparison.

NUMERIC_RTOL = 1e-3
NUMERIC_ATOL = 0.01

# LLM judge settings.
JUDGE_PASS_THRESHOLD = 0.8

# Default judge model. Override via config.yaml (judge_model key)
# or --judge-model flag. Uses pydantic-ai provider:model syntax.
DEFAULT_JUDGE_MODEL = "anthropic:claude-sonnet-4-6"

JUDGE_PROMPT = """You are evaluating whether two query result sets answer the same business question.

Question: {question}

Expected results (ground truth):
{expected}

Agent results:
{actual}

Do these two result sets give a stakeholder the same answer to the question?

Consider:
- Are the key values the same or within normal rounding?
- Are differences cosmetic (column names, row order) or substantive (wrong numbers)?
- Would a stakeholder reach the same conclusion from both result sets?

Respond with ONLY a single number between 0.0 and 1.0.
1.0 = same answer. 0.0 = completely different answer."""


# ===============================================================================
# Layered result comparison
# ===============================================================================

def _to_str_grid(rows: list[dict]) -> list[list[str]]:
    """Flatten a list-of-dicts into a sorted grid of string values."""
    if not rows:
        return []
    cols = sorted(rows[0].keys())
    grid = [[str(row.get(c, "")).strip() for c in cols] for row in rows]
    grid.sort()
    return grid


def _values_only(rows: list[dict]) -> list[list[str]]:
    """Extract just values (ignoring column names), sorted for comparison."""
    if not rows:
        return []
    grid = [sorted(str(v).strip() for v in row.values()) for row in rows]
    grid.sort()
    return grid


def _approx_equal(a: str, b: str) -> bool:
    """Check if two values are approximately equal as numbers."""
    try:
        fa, fb = float(a), float(b)
    except (ValueError, TypeError):
        return a.strip().upper() == b.strip().upper()
    if fa == fb:
        return True
    denom = max(abs(fa), abs(fb), 1e-12)
    return abs(fa - fb) <= NUMERIC_ATOL + NUMERIC_RTOL * denom


def compare_results(
    expected: list[dict[str, Any]],
    actual: list[dict[str, Any]],
) -> dict:
    """Compare expected and actual results through layered stages.

    Stages:
      1. Strict     - identical values, columns, and row ordering
      2. Tolerant   - same values, different column names or ordering
      3. Approximate - numeric values within a configurable tolerance

    Returns {"passed": bool, "stage": str, "reason": str}
    """
    if not expected and not actual:
        return {"passed": True, "stage": "strict", "reason": "Both empty"}
    if not expected or not actual:
        which = "expected" if not expected else "actual"
        return {"passed": False, "stage": "none", "reason": f"{which} result is empty"}

    # Stage 1: Strict match
    exp_grid = _to_str_grid(expected)
    act_grid = _to_str_grid(actual)
    exp_hash = hashlib.md5("\n".join(",".join(r) for r in exp_grid).encode()).hexdigest()
    act_hash = hashlib.md5("\n".join(",".join(r) for r in act_grid).encode()).hexdigest()

    if exp_hash == act_hash:
        return {"passed": True, "stage": "strict", "reason": ""}

    # Stage 2: Tolerant (ignore column names and ordering)
    if len(expected) == len(actual):
        if _values_only(expected) == _values_only(actual):
            return {
                "passed": True,
                "stage": "tolerant",
                "reason": "Values match; column names or ordering differ",
            }

    # Stage 3: Approximate numeric match
    if len(expected) == len(actual):
        exp_vals = _values_only(expected)
        act_vals = _values_only(actual)

        if len(exp_vals) == len(act_vals):
            all_close = True
            for er, ar in zip(exp_vals, act_vals):
                if len(er) != len(ar):
                    all_close = False
                    break
                if not all(_approx_equal(ev, av) for ev, av in zip(er, ar)):
                    all_close = False
                    break
            if all_close:
                return {
                    "passed": True,
                    "stage": "approximate",
                    "reason": "Values match within numeric tolerance",
                }

    # All stages failed
    if len(expected) != len(actual):
        reason = f"Row count differs: expected {len(expected)}, got {len(actual)}"
    else:
        reason = "Same row count but values differ"
    return {"passed": False, "stage": "none", "reason": reason}


# ===============================================================================
# LLM-as-judge fallback (multi-provider via pydantic-ai)
# ===============================================================================

def _load_judge_model() -> str:
    """Read the judge model from config.yaml if present, else use default."""
    config_path = REPO_ROOT / "agent" / "custom_orchestrator" / "config.yaml"
    if config_path.exists():
        import yaml

        data = yaml.safe_load(config_path.read_text()) or {}
        if "judge_model" in data:
            return data["judge_model"]
    return os.environ.get("JUDGE_MODEL", DEFAULT_JUDGE_MODEL)


def _format_rows(rows: list[dict], max_rows: int = 20) -> str:
    """Render result rows as a text table for the judge prompt."""
    if not rows:
        return "(empty result set)"
    cols = list(rows[0].keys())
    lines = [" | ".join(cols), "-+-".join("-" * len(c) for c in cols)]
    for row in rows[:max_rows]:
        lines.append(" | ".join(str(row.get(c, "")) for c in cols))
    if len(rows) > max_rows:
        lines.append(f"... ({len(rows) - max_rows} more rows)")
    return "\n".join(lines)


def _parse_judge_score(text: str) -> float | None:
    """Extract a 0.0-1.0 score from the judge's response."""
    if not text:
        return None
    m = re.search(r"\b(0(?:\.\d+)?|1(?:\.0+)?)\b", text.strip())
    if m:
        val = float(m.group(1))
        if 0.0 <= val <= 1.0:
            return val
    return None


def run_judge(
    question: str,
    expected: list[dict],
    actual: list[dict],
    model_override: str | None = None,
) -> dict:
    """Call the LLM judge using any pydantic-ai supported model.

    The model string follows pydantic-ai's provider:model convention:
        anthropic:claude-sonnet-4-6
        openai:gpt-4o
        google:gemini-2.0-flash

    The provider reads its API key from the standard env var
    (ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, etc.).

    Returns {"score": float|None, "passed": bool, "error": str|None}
    """
    result = {"score": None, "passed": False, "error": None}

    model = model_override or _load_judge_model()

    prompt = JUDGE_PROMPT.format(
        question=question,
        expected=_format_rows(expected),
        actual=_format_rows(actual),
    )

    try:
        from pydantic_ai import Agent

        judge_agent = Agent(model, output_type=str)
        response = asyncio.run(judge_agent.run(prompt))
        raw = response.output.strip()

        score = _parse_judge_score(raw)
        if score is None:
            result["error"] = f"Could not parse score from: {raw!r}"
            return result

        result["score"] = score
        result["passed"] = score >= JUDGE_PASS_THRESHOLD

    except Exception as e:
        result["error"] = str(e)

    return result


# ===============================================================================
# Data loading
# ===============================================================================

def load_expected(questions_csv: Path, duckdb_path: Path) -> dict[str, dict]:
    """Load golden questions and run expected SQL to get ground-truth results."""
    expected = {}
    con = duckdb.connect(str(duckdb_path), read_only=True)

    with open(questions_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            qid = row["id"].strip()
            sql = row.get("expected_sql", "").strip()
            result_rows = []
            sql_error = None

            if sql:
                try:
                    cursor = con.execute(sql)
                    cols = [d[0] for d in cursor.description]
                    result_rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
                except Exception as e:
                    sql_error = str(e)
                    print(f"  WARNING: expected SQL failed for Q{qid}: {e}")

            expected[qid] = {
                "question": row.get("question", "").strip(),
                "expected_sql": sql,
                "expected_result": result_rows,
                "expected_sql_error": sql_error,
                "category": row.get("Category", "").strip(),
                "difficulty": row.get("Difficulty", "").strip(),
            }

    con.close()
    return expected


def load_agent_outputs(output_dir: Path) -> dict[str, dict]:
    """Load per-question JSON files from the agent run."""
    outputs = {}
    if not output_dir.exists():
        return outputs
    for path in sorted(output_dir.glob("*.json")):
        with open(path) as f:
            record = json.load(f)
        qid = str(record.get("question_id", path.stem))
        outputs[qid] = record
    return outputs


# ===============================================================================
# Core evaluation
# ===============================================================================

def evaluate(
    expected: dict[str, dict],
    agent_outputs: dict[str, dict],
    use_judge: bool = True,
    judge_model: str | None = None,
) -> list[dict]:
    """Evaluate every golden question. Returns a list of per-question result dicts."""
    results = []
    total = len(expected)

    for i, qid in enumerate(
        sorted(expected.keys(), key=lambda x: int(x) if x.isdigit() else x), 1
    ):
        exp = expected[qid]
        agent = agent_outputs.get(qid)

        record = {
            "question_id": qid,
            "question": exp["question"],
            "category": exp["category"],
            "difficulty": exp["difficulty"],
            "expected_sql": exp["expected_sql"],
            "has_expected_sql": bool(exp["expected_sql"]),
            "agent_sql": None,
            "agent_response": None,
            "agent_answered": False,
            "agent_declined": False,
            "passed": False,
            "stage": "none",
            "reason": "",
            "judge_score": None,
            "judge_passed": None,
            "tokens": None,
            "cost": None,
            "duration_ms": None,
            "error": None,
        }

        if not agent:
            record["error"] = "No agent output found"
            print(f"  [{i}/{total}] Q{qid}: SKIP (no agent output)")
            results.append(record)
            continue

        record["agent_sql"] = agent.get("agent_sql")
        record["agent_response"] = agent.get("agent_response")
        record["agent_declined"] = agent.get("declined_or_clarified", False)
        record["agent_answered"] = (
            not record["agent_declined"] and record["agent_sql"] is not None
        )
        record["tokens"] = agent.get("tokens")
        record["cost"] = agent.get("cost")
        record["duration_ms"] = agent.get("duration_ms")

        # Out-of-scope: declining is correct
        if not exp["expected_sql"] and record["agent_declined"]:
            record["passed"] = True
            record["stage"] = "graceful_refusal"
            record["reason"] = "Correctly declined out-of-scope question"
            print(f"  [{i}/{total}] Q{qid}: PASS (graceful refusal)")
            results.append(record)
            continue

        # Out-of-scope but agent answered
        if not exp["expected_sql"] and record["agent_answered"]:
            record["stage"] = "false_answer"
            record["reason"] = "Answered a question it should have declined"
            print(f"  [{i}/{total}] Q{qid}: FAIL (should have declined)")
            results.append(record)
            continue

        # Expected SQL exists but agent declined
        if exp["expected_sql"] and record["agent_declined"]:
            record["stage"] = "false_refusal"
            record["reason"] = "Declined a question it should have answered"
            print(f"  [{i}/{total}] Q{qid}: FAIL (false refusal)")
            results.append(record)
            continue

        # Agent errored
        if agent.get("error"):
            record["error"] = agent["error"]
            print(f"  [{i}/{total}] Q{qid}: ERROR ({agent['error'][:60]})")
            results.append(record)
            continue

        # Both sides have results: compare
        exp_result = exp["expected_result"]
        agent_result = agent.get("agent_result", [])

        comparison = compare_results(exp_result, agent_result)
        record["passed"] = comparison["passed"]
        record["stage"] = comparison["stage"]
        record["reason"] = comparison["reason"]

        # LLM judge for stage="none"
        if not comparison["passed"] and use_judge and exp_result and agent_result:
            print(f"  [{i}/{total}] Q{qid}: running judge...", end=" ")
            judge_result = run_judge(
                exp["question"], exp_result, agent_result, judge_model
            )
            record["judge_score"] = judge_result["score"]
            record["judge_passed"] = judge_result["passed"]
            if judge_result.get("error"):
                record["error"] = f"Judge: {judge_result['error']}"
            if judge_result["passed"]:
                record["passed"] = True
                record["stage"] = "judge_verified"
                record["reason"] = f"LLM judge score: {judge_result['score']:.2f}"

        status = "PASS" if record["passed"] else "FAIL"
        print(f"  [{i}/{total}] Q{qid}: {status} ({record['stage']})")
        results.append(record)

    return results


# ===============================================================================
# Scorecard and results export
# ===============================================================================

def print_scorecard(results: list[dict]) -> None:
    """Print a human-readable scorecard."""
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    pass_rate = passed / total * 100 if total else 0

    answerable = [r for r in results if r["has_expected_sql"]]
    out_of_scope = [r for r in results if not r["has_expected_sql"]]
    answerable_passed = sum(1 for r in answerable if r["passed"])
    oos_passed = sum(1 for r in out_of_scope if r["passed"])
    answerable_rate = answerable_passed / len(answerable) * 100 if answerable else 0

    print("\n" + "=" * 60)
    print("EVALUATION SCORECARD")
    print(f"Run: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    print(f"\n  Pass rate:              {passed}/{total} ({pass_rate:.1f}%)")
    print(f"  Answerable questions:   {answerable_passed}/{len(answerable)} ({answerable_rate:.1f}%)")
    print(f"  Out-of-scope handling:  {oos_passed}/{len(out_of_scope)}")

    # Stage breakdown
    stages = {}
    for r in results:
        stages[r["stage"]] = stages.get(r["stage"], 0) + 1
    print(f"\n  Match breakdown:")
    for s in [
        "strict", "tolerant", "approximate", "judge_verified",
        "graceful_refusal", "false_answer", "false_refusal", "none",
    ]:
        if s in stages:
            print(f"    {s:20s} {stages[s]:>3d}")

    # By difficulty
    by_diff = {}
    for r in results:
        d = r["difficulty"] or "unset"
        by_diff.setdefault(d, {"total": 0, "passed": 0})
        by_diff[d]["total"] += 1
        if r["passed"]:
            by_diff[d]["passed"] += 1
    if by_diff:
        print(f"\n  By difficulty:")
        for d in ["Easy", "Medium", "Hard", "unset"]:
            if d in by_diff:
                t, p = by_diff[d]["total"], by_diff[d]["passed"]
                print(f"    {d:10s} {p}/{t} ({p / t * 100:.0f}%)")

    # By category
    by_cat = {}
    for r in results:
        c = r["category"] or "unset"
        by_cat.setdefault(c, {"total": 0, "passed": 0})
        by_cat[c]["total"] += 1
        if r["passed"]:
            by_cat[c]["passed"] += 1
    if by_cat:
        print(f"\n  By category:")
        for c, v in sorted(by_cat.items()):
            t, p = v["total"], v["passed"]
            print(f"    {c:22s} {p}/{t} ({p / t * 100:.0f}%)")

    # Cost summary
    total_tokens = sum(r.get("tokens") or 0 for r in results)
    total_cost = sum(r.get("cost") or 0 for r in results)
    total_ms = sum(r.get("duration_ms") or 0 for r in results)
    if total_tokens:
        print(f"\n  Agent cost:")
        print(f"    Tokens:    {total_tokens:,}")
        print(f"    Cost:      ${total_cost:.4f}")
        print(f"    Duration:  {total_ms / 1000:.1f}s")

    # Failed questions
    failed = [r for r in results if not r["passed"]]
    if failed:
        print(f"\n  Failed ({len(failed)}):")
        for r in failed:
            reason = r["reason"] or r.get("error") or "unknown"
            print(f"    Q{r['question_id']:>3s}: {reason}")

    print("\n" + "=" * 60)


def export_results(results: list[dict], output_dir: Path) -> Path:
    """Write results to a timestamped JSON file and a CSV for spreadsheet review."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # JSON (full detail)
    json_path = output_dir / f"eval_{ts}.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    # CSV (spreadsheet-friendly for comparing runs)
    csv_path = output_dir / f"eval_{ts}.csv"
    if results:
        cols = [
            "question_id", "question", "category", "difficulty",
            "passed", "stage", "reason",
            "agent_sql", "expected_sql", "agent_response",
            "judge_score", "tokens", "cost", "duration_ms", "error",
        ]
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)

    print(f"\n  Results: {json_path}")
    print(f"  CSV:     {csv_path}")
    return json_path


# ===============================================================================
# Entry point
# ===============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate agent outputs against golden questions."
    )
    parser.add_argument(
        "--agent-outputs",
        type=Path,
        default=DEFAULT_OUTPUTS,
        help=f"Directory of per-question JSON files (default: {DEFAULT_OUTPUTS})",
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=DEFAULT_QUESTIONS,
        help=f"Golden questions CSV (default: {DEFAULT_QUESTIONS})",
    )
    parser.add_argument(
        "--duckdb",
        type=Path,
        default=DEFAULT_DUCKDB,
        help=f"Path to DuckDB database (default: {DEFAULT_DUCKDB})",
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Skip the LLM judge (faster, no API cost)",
    )
    parser.add_argument(
        "--judge-model",
        default=None,
        help=(
            "Override judge model using pydantic-ai provider:model syntax "
            "(e.g. openai:gpt-4o, google:gemini-2.0-flash). "
            "Defaults to judge_model in config.yaml or anthropic:claude-sonnet-4-6."
        ),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help=f"Where to write evaluation results (default: {DEFAULT_RESULTS_DIR})",
    )
    args = parser.parse_args()

    print(f"Loading expected results from {args.questions}...")
    expected = load_expected(args.questions, args.duckdb)
    print(f"  {len(expected)} golden questions loaded")

    questions_with_sql = sum(1 for e in expected.values() if e["expected_sql"])
    questions_without = len(expected) - questions_with_sql
    print(f"  {questions_with_sql} with expected SQL, {questions_without} out-of-scope")

    print(f"\nLoading agent outputs from {args.agent_outputs}...")
    agent_outputs = load_agent_outputs(args.agent_outputs)
    print(f"  {len(agent_outputs)} agent outputs loaded")

    if not agent_outputs:
        print("\nNo agent outputs found. Run the agent first:")
        print("  python -m agent.custom_orchestrator.run_golden_set")
        sys.exit(1)

    missing = set(expected.keys()) - set(agent_outputs.keys())
    if missing:
        print(f"  WARNING: {len(missing)} questions have no agent output: {sorted(missing)}")

    print("\nRunning evaluation...\n")
    results = evaluate(
        expected,
        agent_outputs,
        use_judge=not args.no_judge,
        judge_model=args.judge_model,
    )

    print_scorecard(results)
    export_results(results, args.results_dir)


if __name__ == "__main__":
    main()