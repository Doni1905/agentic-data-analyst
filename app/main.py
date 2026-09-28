"""FastAPI backend: runs the agent loop and keeps per-conversation memory.

Run:  uvicorn app.main:app --reload
"""
from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.agent.graph import ask
from app.db import get_schema

app = FastAPI(title="Agentic Data Analyst", version="0.1.0")

# In-memory conversation store: {conversation_id: [{"question":..,"answer":..}]}
_conversations: dict[str, list[dict[str, str]]] = {}
_MAX_TURNS = 10


class AskRequest(BaseModel):
    question: str
    conversation_id: str | None = None


class AskResponse(BaseModel):
    conversation_id: str
    answer: str
    sql: str = ""
    columns: list[str] = Field(default_factory=list)
    rows: list[list] = Field(default_factory=list)
    chart: dict = Field(default_factory=dict)
    retries: int = 0


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/schema")
def schema() -> dict:
    return get_schema()


@app.post("/ask", response_model=AskResponse)
def ask_endpoint(req: AskRequest) -> AskResponse:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question is empty")
    conv_id = req.conversation_id or uuid.uuid4().hex
    history = _conversations.setdefault(conv_id, [])
    try:
        state = ask(req.question, history=history)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    answer = state.get("answer", "")
    history.append({"question": req.question, "answer": answer})
    del history[:-_MAX_TURNS]
    return AskResponse(
        conversation_id=conv_id,
        answer=answer,
        sql=state.get("sql", ""),
        columns=state.get("columns", []),
        rows=state.get("rows", []),
        chart=state.get("chart", {}),
        retries=state.get("retries", 0),
    )
