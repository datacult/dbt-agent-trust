"""The custom orchestrator: a Pydantic AI agent over a DuckDB MCP server.
    python -m agent.custom_orchestrator.agent "What was total GMV for Q1 2018?"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from typing import Any

from pydantic_ai import Agent, ModelRetry
from pydantic_ai.mcp import CallToolFunc, MCPToolset, StdioTransport, ToolResult
from pydantic_ai.usage import UsageLimits

from .config import AgentConfig, load_config
from .contract import load_contract, run_sql_readonly, validate_sql_readonly
from .schema import AgentAnswer, build_output_record


def build_agent(cfg: AgentConfig) -> Agent:
    """Wire the model, governed instructions, and DuckDB MCP toolset.

    The provider reads its own standard API-key env var (OPENAI_API_KEY,
    ANTHROPIC_API_KEY, GEMINI_API_KEY, ...), loaded from the root .env by
    load_config(). Set the one that matches your configured model.
    """

    async def process_tool_call(
        _ctx: Any,
        call_tool: CallToolFunc,
        name: str,
        args: dict[str, Any],
    ) -> ToolResult:
        if name != "execute_query":
            raise ModelRetry(f"DuckDB MCP tool {name!r} is not allowed.")

        try:
            validate_sql_readonly(cfg.duckdb_path, args.get("sql"))
        except (RuntimeError, ValueError) as exc:
            raise ModelRetry(f"Query rejected by governance rules: {exc}") from exc

        return await call_tool(name, args)

    duckdb_mcp = MCPToolset(
        StdioTransport(command=cfg.mcp_command, args=cfg.duckdb_mcp_args()),
        process_tool_call=process_tool_call,
    )
    return Agent(
        cfg.model,
        toolsets=[duckdb_mcp],
        output_type=AgentAnswer,
        instructions=load_contract(cfg.duckdb_path),
        retries=cfg.max_sql_retries,
    )


def _extract_query_calls(messages) -> list[dict]:
    """Pull DuckDB query calls and their returns from the message history."""
    returns: dict[str, object] = {}
    for msg in messages:
        for part in msg.parts:
            if part.part_kind == "tool-return":
                returns[part.tool_call_id] = part.content

    calls: list[dict] = []
    for msg in messages:
        for part in msg.parts:
            if part.part_kind != "tool-call" or part.tool_name != "execute_query":
                continue
            output = returns.get(part.tool_call_id)
            calls.append(
                {
                    "tool": part.tool_name,
                    "input": part.args_as_dict(),
                    "output": str(output)[:2000] if output is not None else None,
                }
            )
    return calls


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Best-effort USD cost via genai-prices; None if it can't be priced"""
    try:
        from genai_prices import Usage as GUsage, calc_price

        provider_id, _, model_ref = model.partition(":")
        price = calc_price(
            GUsage(input_tokens=input_tokens, output_tokens=output_tokens),
            model_ref or provider_id,
            provider_id=provider_id or None,
        )
        return float(price.total_price)
    except Exception:
        return None


async def answer_with(
    agent: Agent,
    cfg: AgentConfig,
    question: str,
    question_id: str,
) -> dict:
    """Run one question through an already-open agent, return the contract dict."""
    started = time.perf_counter()
    error = error_type = None
    result = None
    try:
        result = await agent.run(
            question,
            usage_limits=UsageLimits(request_limit=cfg.max_requests),
        )
    except Exception as exc:  # model / MCP / limit failure
        error, error_type = str(exc), type(exc).__name__

    duration_ms = int((time.perf_counter() - started) * 1000)
    timestamp = datetime.now(timezone.utc).isoformat()

    if result is None:
        record = build_output_record(
            question_id=question_id,
            question=question,
            model=cfg.model,
            timestamp=timestamp,
            answer=None,
            agent_result=[],
            tool_calls=[],
            n_requests=0,
            tokens=None,
            cost=None,
            duration_ms=duration_ms,
            error=error,
            error_type=error_type,
        )
        return record

    ans: AgentAnswer = result.output
    usage = result.usage
    tool_calls = _extract_query_calls(result.all_messages())

    # run_sql_readonly re-validates on purpose: final_sql is model-controlled and
    # need not match any SQL the model actually executed as a tool call, so the
    # governance checks must run again on the exact query we execute here.
    agent_result: list[dict] = []
    if ans.final_sql is not None:
        try:
            agent_result = run_sql_readonly(cfg.duckdb_path, ans.final_sql)
        except Exception as exc:
            error, error_type = str(exc), f"sql:{type(exc).__name__}"

    record = build_output_record(
        question_id=question_id,
        question=question,
        model=cfg.model,
        timestamp=timestamp,
        answer=ans,
        agent_result=agent_result,
        tool_calls=tool_calls,
        n_requests=usage.requests,
        tokens=usage.total_tokens,
        cost=_estimate_cost(cfg.model, usage.input_tokens, usage.output_tokens),
        duration_ms=duration_ms,
        error=error,
        error_type=error_type,
    )
    return record


async def answer_one(
    question: str,
    cfg: AgentConfig | None = None,
    question_id: str = "adhoc",
) -> dict:
    """open the MCP connection, answer one question."""
    cfg = cfg or load_config()
    agent = build_agent(cfg)
    async with agent:
        return await answer_with(agent, cfg, question, question_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the governed analytics agent one question.")
    parser.add_argument("question", help="Natural-language business question.")
    parser.add_argument("--id", default="adhoc", help="Question id for the output record.")
    parser.add_argument("--model", default=None, help="Override the model (e.g. anthropic:claude-opus-4-8).")
    args = parser.parse_args()

    cfg = load_config()
    if args.model:
        cfg.model = args.model

    record = asyncio.run(answer_one(args.question, cfg, args.id))
    json.dump(record, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
