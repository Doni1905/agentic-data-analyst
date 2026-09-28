"""State carried through the LangGraph agent loop."""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class AgentState(TypedDict, total=False):
    question: str
    history: list[dict[str, str]]          # prior Q/A turns for follow-ups
    intent: str                            # short intent summary from the LLM
    schema_info: str                       # schema text injected into prompts
    sql: str
    validation_errors: list[str]
    columns: list[str]
    rows: list[list[Any]]
    execution_error: str
    retries: int
    explanation: str
    chart: dict[str, Any]                  # serialised ChartSpec
    answer: str
