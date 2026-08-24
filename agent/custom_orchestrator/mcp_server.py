"""Expose the governed Olist analytics agent through MCP."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, TypedDict

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession
from mcp.types import ToolAnnotations
from pydantic_ai import Agent

from .agent import answer_with, build_agent
from .config import AgentConfig, load_config


@dataclass
class AppContext:
    """Resources initialized once for the lifetime of the MCP server."""

    agent: Agent
    config: AgentConfig


class AnalyticsResponse(TypedDict):
    """Structured result returned by the analytics tool."""

    answer: str
    sql: str | None
    result: list[dict[str, Any]]
    declined: bool
    metric: str | None


@asynccontextmanager
async def lifespan(_server: FastMCP) -> AsyncIterator[AppContext]:
    """Open one agent and DuckDB MCP connection for the server session."""
    config = load_config()
    agent = build_agent(config)

    async with agent:
        yield AppContext(agent=agent, config=config)


mcp = FastMCP(
    "olist-analytics",
    instructions="Answer governed analytics questions about the Olist dataset.",
    lifespan=lifespan,
)


@mcp.tool(
    title="Ask Olist analytics",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        openWorldHint=False,
    ),
)
async def ask_analytics(
    question: str,
    ctx: Context[ServerSession, AppContext],
) -> AnalyticsResponse:
    """Answer a business question using the governed Olist analytics agent."""
    question = question.strip()
    if not question:
        raise ValueError("Question cannot be empty.")

    app = ctx.request_context.lifespan_context
    record = await answer_with(
        app.agent,
        app.config,
        question,
        str(ctx.request_id),
    )

    if record["error"]:
        raise RuntimeError(record["error"])

    return {
        "answer": record["agent_response"],
        "sql": record["agent_sql"],
        "result": record["agent_result"],
        "declined": record["declined_or_clarified"],
        "metric": record["metric_queried"],
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
