"""Streamlit UI for the Agentic Data Analyst.

Run:  streamlit run ui/streamlit_app.py
(Talks to the FastAPI backend; override with API_URL in .env.)
"""
from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Agentic Data Analyst", page_icon="chart_with_upwards_trend")
st.title("Agentic Data Analyst")
st.caption("Ask questions about the demo sales database in plain English. "
           "The agent writes SQL, checks it, runs it, charts and explains the result.")

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "turns" not in st.session_state:
    st.session_state.turns = []


def render_result(turn: dict) -> None:
    resp = turn["response"]
    if resp.get("sql"):
        with st.expander("Generated SQL" + (f" (self-corrected {resp['retries']}x)"
                                           if resp.get("retries") else "")):
            st.code(resp["sql"], language="sql")
    if resp.get("rows"):
        df = pd.DataFrame(resp["rows"], columns=resp["columns"])
        chart = resp.get("chart") or {}
        ctype = chart.get("type", "table")
        if ctype != "table" and chart.get("x") and chart.get("y"):
            x, y, title = chart["x"], chart["y"], chart.get("title", "")
            if ctype == "bar":
                st.plotly_chart(px.bar(df, x=x, y=y, title=title), use_container_width=True)
            elif ctype == "line":
                st.plotly_chart(px.line(df, x=x, y=y, title=title, markers=True),
                                use_container_width=True)
            elif ctype == "pie":
                st.plotly_chart(px.pie(df, names=x, values=y, title=title),
                                use_container_width=True)
            elif ctype == "scatter":
                st.plotly_chart(px.scatter(df, x=x, y=y, title=title),
                                use_container_width=True)
            if chart.get("reason"):
                st.caption(f"Chart choice: {chart['reason']}")
        with st.expander("Result table"):
            st.dataframe(df, use_container_width=True)
    st.markdown(resp.get("answer", ""))


for turn in st.session_state.turns:
    with st.chat_message("user"):
        st.markdown(turn["question"])
    with st.chat_message("assistant"):
        render_result(turn)

question = st.chat_input(
    "e.g. Which product generated the highest revenue? / Show me the monthly sales trend"
)
if question:
    with st.spinner("Agent is thinking (understand -> SQL -> validate -> run -> chart)..."):
        try:
            r = requests.post(
                f"{API_URL}/ask",
                json={"question": question,
                      "conversation_id": st.session_state.conversation_id},
                timeout=120,
            )
            r.raise_for_status()
            resp = r.json()
        except Exception as exc:
            st.error(f"Backend error: {exc}")
            st.stop()
    st.session_state.conversation_id = resp["conversation_id"]
    st.session_state.turns.append({"question": question, "response": resp})
    st.rerun()

with st.sidebar:
    st.header("Try these")
    for q in [
        "What were the total sales in Tamil Nadu last year?",
        "Which product generated the highest revenue?",
        "Show me the monthly sales trend.",
        "Which region has the lowest sales?",
        "Compare sales between Tamil Nadu and Kerala as a bar chart.",
        "Show it as a pie chart.",
    ]:
        st.markdown(f"- {q}")
    if st.button("New conversation"):
        st.session_state.conversation_id = None
        st.session_state.turns = []
        st.rerun()
