"""LangGraph nodes: understand -> schema -> SQL -> validate -> execute
-> (self-correct on error) -> analyze -> visualize."""
from __future__ import annotations

import re
from dataclasses import asdict

from app.agent.state import AgentState
from app.charts import choose_chart
from app.config import settings
from app.db import run_query, schema_text
from app.sql_validator import validate_sql

_SQL_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.S | re.I)


def _clean_sql(text: str) -> str:
    m = _SQL_FENCE.search(text)
    sql = m.group(1) if m else text
    return sql.strip().strip(";")


def understand(state: AgentState, llm) -> AgentState:
    history = "\n".join(
        f"Q: {h['question']}\nA: {h['answer']}" for h in state.get("history", [])[-4:]
    )
    prompt = (
        "You are part of a data analyst agent. Summarise what the user wants in "
        "one or two short sentences: the metric, the grouping, any filters "
        "(place, date range), and the desired output. Resolve follow-up "
        "references ('it', 'that', 'show as chart') using the conversation.\n\n"
        f"Conversation so far:\n{history or '(none)'}\n\n"
        f"New question: {state['question']}"
    )
    resp = llm.invoke(prompt)
    return {**state, "intent": resp.content}


def fetch_schema(state: AgentState, llm) -> AgentState:
    return {**state, "schema_info": schema_text()}


def generate_sql(state: AgentState, llm) -> AgentState:
    prompt = (
        "You are a PostgreSQL expert. Write ONE read-only SELECT query that "
        "answers the question. Rules:\n"
        "- Output ONLY the SQL, no explanation, no markdown fences.\n"
        "- Use only the tables and columns listed below.\n"
        "- Always alias computed columns clearly (e.g. AS total_sales).\n"
        "- For 'top N' use ORDER BY ... DESC LIMIT n.\n"
        "- For monthly trends use date_trunc('month', sale_date).\n"
        "- 'last year' means the previous calendar year.\n\n"
        f"{state['schema_info']}\n\n"
        f"What the user wants: {state['intent']}\n"
        f"Original question: {state['question']}"
    )
    resp = llm.invoke(prompt)
    return {**state, "sql": _clean_sql(resp.content)}


def validate(state: AgentState, llm) -> AgentState:
    from app.db import get_schema

    result = validate_sql(state["sql"], get_schema())
    return {**state, "validation_errors": result.errors}


def execute(state: AgentState, llm) -> AgentState:
    try:
        cols, rows = run_query(state["sql"])
        return {**state, "columns": cols, "rows": [list(r) for r in rows],
                "execution_error": ""}
    except Exception as exc:  # DB errors feed the self-correction loop
        return {**state, "execution_error": str(exc)}


def correct_sql(state: AgentState, llm) -> AgentState:
    problem = state.get("execution_error") or "; ".join(state.get("validation_errors", []))
    prompt = (
        "A PostgreSQL SELECT query failed. Fix it. Output ONLY the corrected "
        "SQL, no explanation, no markdown fences.\n\n"
        f"Schema:\n{state['schema_info']}\n\n"
        f"Question: {state['question']}\n"
        f"Broken SQL:\n{state['sql']}\n\n"
        f"Error:\n{problem}"
    )
    resp = llm.invoke(prompt)
    return {**state, "sql": _clean_sql(resp.content),
            "retries": state.get("retries", 0) + 1,
            "execution_error": "", "validation_errors": []}


def analyze(state: AgentState, llm) -> AgentState:
    preview = [state["columns"]] + state["rows"][:20]
    prompt = (
        "You are a data analyst explaining a result in simple language. "
        "Use ONLY the numbers below - never invent values. Indian formats "
        "like lakh are fine. 2-4 sentences. If the result is empty, say so "
        "plainly.\n\n"
        f"Question: {state['question']}\n"
        f"SQL used: {state['sql']}\n"
        f"Result (header + first rows):\n{preview}"
    )
    resp = llm.invoke(prompt)
    explanation = resp.content
    return {**state, "explanation": explanation, "answer": explanation}


def visualize(state: AgentState, llm) -> AgentState:
    spec = choose_chart(
        state["question"],
        state.get("columns", []),
        state.get("rows", []),
    )
    return {**state, "chart": asdict(spec)}


def failed(state: AgentState, llm) -> AgentState:
    problem = state.get("execution_error") or "; ".join(state.get("validation_errors", []))
    answer = (
        "I could not get a correct query after "
        f"{settings.max_sql_retries} attempts. Last error: {problem}. "
        "Try rephrasing the question with the exact table or column names."
    )
    return {**state, "answer": answer, "explanation": answer}
