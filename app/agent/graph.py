"""The LangGraph workflow.

    understand -> fetch_schema -> generate_sql -> validate
        -> execute -> analyze -> visualize -> END
        -> correct_sql -> execute   (self-correction loop, capped)
        -> failed                   (retries exhausted)
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agent import nodes
from app.agent.state import AgentState
from app.config import settings
from app.llm import build_llm


def _after_validate(state: AgentState) -> str:
    if not state.get("validation_errors"):
        return "execute"
    return "correct" if state.get("retries", 0) < settings.max_sql_retries else "failed"


def _after_execute(state: AgentState) -> str:
    if not state.get("execution_error"):
        return "analyze"
    return "correct" if state.get("retries", 0) < settings.max_sql_retries else "failed"


def build_graph(llm=None):
    llm = llm or build_llm()
    g = StateGraph(AgentState)

    g.add_node("understand", lambda s: nodes.understand(s, llm))
    g.add_node("fetch_schema", lambda s: nodes.fetch_schema(s, llm))
    g.add_node("generate_sql", lambda s: nodes.generate_sql(s, llm))
    g.add_node("validate", lambda s: nodes.validate(s, llm))
    g.add_node("execute", lambda s: nodes.execute(s, llm))
    g.add_node("correct_sql", lambda s: nodes.correct_sql(s, llm))
    g.add_node("analyze", lambda s: nodes.analyze(s, llm))
    g.add_node("visualize", lambda s: nodes.visualize(s, llm))
    g.add_node("failed", lambda s: nodes.failed(s, llm))

    g.set_entry_point("understand")
    g.add_edge("understand", "fetch_schema")
    g.add_edge("fetch_schema", "generate_sql")
    g.add_edge("generate_sql", "validate")
    g.add_conditional_edges("validate", _after_validate,
                            {"execute": "execute", "correct": "correct_sql",
                             "failed": "failed"})
    g.add_conditional_edges("execute", _after_execute,
                            {"analyze": "analyze", "correct": "correct_sql",
                             "failed": "failed"})
    g.add_edge("correct_sql", "validate")
    g.add_edge("analyze", "visualize")
    g.add_edge("visualize", END)
    g.add_edge("failed", END)
    return g.compile()


def ask(question: str, history: list[dict[str, str]] | None = None, llm=None) -> AgentState:
    graph = build_graph(llm)
    return graph.invoke({"question": question, "history": history or [], "retries": 0})
