"""Run every golden question through the agent and write per-question JSON.

Usage:
    python -m agent.custom_orchestrator.run_golden_set
    python -m agent.custom_orchestrator.run_golden_set --questions path/to/questions.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .agent import answer_with, build_agent
from .config import AgentConfig, load_config, REPO_ROOT

DEFAULT_GOLDEN = REPO_ROOT / "golden_questions" / "olist_golden_questions.csv"


def load_golden_questions(path: Path) -> list[dict]:
    """Read the golden questions CSV into a list of dicts."""
    questions = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            questions.append(
                {
                    "id": row["id"].strip(),
                    "question": row["question"].strip(),
                    "category": row.get("Category", "").strip(),
                    "difficulty": row.get("Difficulty", "").strip(),
                    "domain": row.get("domain", "").strip(),
                }
            )
    return questions


async def run_golden_set(
    cfg: AgentConfig,
    questions: list[dict],
    resume: bool = True,
) -> list[dict]:
    """Send every question through the agent, write JSON per question.

    If resume=True, skip questions whose output file already exists.
    This lets you restart a partial run without re-spending tokens.
    """
    output_dir = cfg.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    agent = build_agent(cfg)
    results = []
    total = len(questions)

    async with agent:
        for i, q in enumerate(questions, 1):
            qid = q["id"]
            out_path = output_dir / f"{qid}.json"

            if resume and out_path.exists():
                print(f"[{i}/{total}] {qid} — skipped (output exists)")
                with open(out_path) as f:
                    results.append(json.load(f))
                continue

            print(f"[{i}/{total}] {qid} — {q['question'][:80]}...")

            record = await answer_with(agent, cfg, q["question"], qid)

            # Attach question metadata the evaluation layer needs
            record["category"] = q["category"]
            record["difficulty"] = q["difficulty"]

            with open(out_path, "w") as f:
                json.dump(record, f, indent=2, default=str)

            status = "DECLINED" if record.get("declined_or_clarified") else "OK"
            if record.get("error"):
                status = f"ERROR: {record['error_type']}"

            print(
                f"         {status} | "
                f"{record.get('tokens', '?')} tokens | "
                f"{record.get('duration_ms', '?')}ms | "
                f"${record.get('cost', 0) or 0:.4f}"
            )

            results.append(record)

    return results


def print_summary(results: list[dict]) -> None:
    """Print a summary table after the run."""
    total = len(results)
    answered = sum(1 for r in results if not r.get("declined_or_clarified") and not r.get("error"))
    declined = sum(1 for r in results if r.get("declined_or_clarified"))
    errored = sum(1 for r in results if r.get("error"))
    total_tokens = sum(r.get("tokens", 0) or 0 for r in results)
    total_cost = sum(r.get("cost", 0) or 0 for r in results)
    total_duration = sum(r.get("duration_ms", 0) or 0 for r in results)

    print("\n" + "=" * 60)
    print(f"Golden set run complete: {total} questions")
    print(f"  Answered:  {answered}")
    print(f"  Declined:  {declined}")
    print(f"  Errors:    {errored}")
    print(f"  Tokens:    {total_tokens:,}")
    print(f"  Cost:      ${total_cost:.4f}")
    print(f"  Duration:  {total_duration / 1000:.1f}s")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run all golden questions through the governed analytics agent."
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=DEFAULT_GOLDEN,
        help=f"Path to golden questions CSV (default: {DEFAULT_GOLDEN})",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the model (e.g. anthropic:claude-sonnet-4-6)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Re-run all questions even if output files exist",
    )
    args = parser.parse_args()

    cfg = load_config()
    if args.model:
        cfg.model = args.model

    if not args.questions.exists():
        print(f"Golden questions file not found: {args.questions}", file=sys.stderr)
        sys.exit(1)

    questions = load_golden_questions(args.questions)
    print(f"Loaded {len(questions)} golden questions from {args.questions}")
    print(f"Model: {cfg.model}")
    print(f"Output: {cfg.output_dir}")
    print()

    results = asyncio.run(run_golden_set(cfg, questions, resume=not args.no_resume))
    print_summary(results)


if __name__ == "__main__":
    main()