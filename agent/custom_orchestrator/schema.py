from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class AgentAnswer(BaseModel):
    """The agent's structured answer to one question."""

    answer: str = Field(description="Short natural-language answer for a stakeholder.")
    final_sql: str | None = Field(
        default=None,
        description="The single DuckDB SQL query you trust. Empty if declining.",
    )
    declined_or_clarified: bool = Field(
        default=False,
        description="True if the question is out of scope / unanswerable from the marts.",
    )
    metric_queried: str | None = Field(
        default=None,
        description="Main metric or entity queried, e.g. 'total_gmv'. Optional.",
    )

    @model_validator(mode="after")
    def require_sql_for_answer(self) -> AgentAnswer:
        """Keep answered and declined output states mutually exclusive."""
        if self.final_sql is not None:
            self.final_sql = self.final_sql.strip() or None

        if self.declined_or_clarified:
            # A declined answer never carries SQL
            self.final_sql = None
        elif self.final_sql is None:
            raise ValueError("A non-declined answer requires final_sql.")

        return self


def build_output_record(
    *,
    question_id: str,
    question: str,
    model: str,
    timestamp: str,
    answer: AgentAnswer | None,
    agent_result: list[dict],
    tool_calls: list[dict],
    n_requests: int,
    tokens: int | None,
    cost: float | None,
    duration_ms: int,
    error: str | None = None,
    error_type: str | None = None,
) -> dict[str, Any]:
    """Assemble the JSON contract for one question."""
    return {
        "question_id": question_id,
        "question": question,
        "model": model,
        "timestamp": timestamp,
        "agent_response": answer.answer if answer else f"Agent run failed: {error}",
        "agent_sql": answer.final_sql if answer else None,
        "agent_result": agent_result,
        "tool_calls": tool_calls,
        "n_requests": n_requests,
        "metric_queried": answer.metric_queried if answer else None,
        "declined_or_clarified": answer.declined_or_clarified if answer else False,
        "tokens": tokens,
        "cost": cost,
        "duration_ms": duration_ms,
        "error": error,
        "error_type": error_type,
    }
