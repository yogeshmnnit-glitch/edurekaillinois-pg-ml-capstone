"""Observability panel: today vs session token usage, last turn's latency/similarity breakdown."""
from __future__ import annotations

import streamlit as st

from Utility.metrics.observability import get_token_dashboard, summarize_turn
from Utility.storage.db import ChatStore


def render_observability(store: ChatStore) -> None:
    st.subheader("Observability")

    thread_id = st.session_state.get("thread_id")
    if not thread_id:
        st.caption("Start a chat to see token usage and performance metrics.")
        return

    dashboard = get_token_dashboard(store, thread_id)
    col1, col2 = st.columns(2)
    col1.metric("Tokens today", dashboard.today_tokens)
    col2.metric("Tokens this session", dashboard.session_tokens)

    last_result = st.session_state.get("last_turn_summary")
    if not last_result:
        st.caption("Ask a question to see per-agent timing and similarity for that turn.")
        return

    summary = summarize_turn(last_result)
    st.caption(f"Last turn: {summary.total_tokens} tokens, {summary.total_latency_ms:.0f} ms total")

    for node in summary.per_node:
        st.text(f"{node['node']}: {node['latency_ms']:.0f} ms, {node['total_tokens']} tokens")

    if summary.similarity.count:
        st.caption(
            f"Similarity - avg {summary.similarity.average:.2f}, "
            f"min {summary.similarity.minimum:.2f}, max {summary.similarity.maximum:.2f} "
            f"({summary.similarity.count} chunks)"
        )
