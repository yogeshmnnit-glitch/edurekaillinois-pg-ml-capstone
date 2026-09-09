"""Main chat interface: renders history, handles new questions, shows citations/confidence."""
from __future__ import annotations

import streamlit as st

from Utility.config.prompts import INSUFFICIENT_EVIDENCE_MESSAGE, SAFETY_VIOLATION_MESSAGE
from Utility.graph.workflow_graph import run_workflow
from Utility.metrics.observability import persist_turn_metrics
from Utility.storage.db import ChatStore

_HISTORY_TURNS = 6


def _render_message(role: str, content: str, citations: list[str] | None = None, confidence: float | None = None) -> None:
    with st.chat_message(role):
        st.markdown(content)
        if citations:
            st.caption("Sources: " + ", ".join(citations))
        if confidence is not None:
            st.progress(min(max(confidence, 0.0), 1.0), text=f"Confidence: {confidence:.0%}")


def render_chat(store: ChatStore) -> None:
    thread_id = st.session_state.get("thread_id")
    history_for_graph: list[dict] = []

    if thread_id:
        thread, messages = store.load_thread(thread_id)
        for msg in messages:
            _render_message(msg.role, msg.content, msg.citations, msg.confidence)
        history_for_graph = [{"role": m.role, "content": m.content} for m in messages[-_HISTORY_TURNS:]]
    else:
        st.info("Ask a question about your telecom documents to get started.")

    query = st.chat_input("Ask a question about your uploaded documents...")
    if not query or not query.strip():
        return
    query = query.strip()

    if not thread_id:
        thread_id = store.create_thread(query[:60])
        st.session_state["thread_id"] = thread_id

    store.append_message(thread_id, "user", query)
    _render_message("user", query)

    state = {
        "trigger": "new_query",
        "session_id": st.session_state["session_id"],
        "query": query,
        "history": history_for_graph,
        "metrics": [],
    }

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                result = run_workflow(state)
            except Exception as exc:  # pragma: no cover - defensive UI guard
                st.error(f"Something went wrong answering your question: {exc}")
                return

        status = result.get("status")
        if status == "error":
            answer = f"[Error] {result.get('error', 'An unexpected error occurred.')}"
            citations: list[str] = []
            confidence = None
            st.error(answer)
        elif status == "safety_violation":
            answer = result.get("answer") or SAFETY_VIOLATION_MESSAGE
            citations = []
            confidence = None
            st.error(answer)
        else:
            answer = result.get("answer") or INSUFFICIENT_EVIDENCE_MESSAGE
            citations = result.get("citations", [])
            confidence = result.get("confidence")
            st.markdown(answer)
            if citations:
                st.caption("Sources: " + ", ".join(citations))
            if confidence is not None:
                st.progress(min(max(confidence, 0.0), 1.0), text=f"Confidence: {confidence:.0%}")
            if status == "insufficient_evidence":
                st.warning("Please upload additional documents relevant to this question using the sidebar.")

    store.append_message(thread_id, "assistant", answer, citations=citations, confidence=confidence)
    store.update_thread_state(thread_id, result.get("pending_query"), status)
    persist_turn_metrics(store, thread_id, result)
    st.session_state["last_turn_summary"] = result
    st.rerun()
