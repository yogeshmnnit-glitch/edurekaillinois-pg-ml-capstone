"""Sidebar: knowledge base document list, uploader, chat history, retention reset."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from Utility.config.settings import settings
from Utility.graph.workflow_graph import run_workflow
from Utility.metrics.observability import persist_turn_metrics
from Utility.storage.db import ChatStore

def _upload_dir() -> Path:
    return settings.project_root / "Input Data" / st.session_state["session_id"]


def _list_session_files() -> list[str]:
    folder = _upload_dir()
    if not folder.exists():
        return []
    return sorted(p.name for p in folder.iterdir() if p.is_file() and not p.name.startswith("."))


def _validate_upload(uploaded_file) -> str | None:
    """Return a guardrail error message if the file fails validation, else None."""
    ext = Path(uploaded_file.name).suffix.lower().lstrip(".")
    if ext not in settings.allowed_extensions:
        return f"'{uploaded_file.name}': unsupported file type '.{ext}'."
    if uploaded_file.size > settings.max_upload_bytes:
        return f"'{uploaded_file.name}': exceeds the {settings.max_upload_mb}MB upload limit."
    return None


def _save_uploaded_file(uploaded_file) -> Path:
    upload_dir = _upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / uploaded_file.name
    dest.write_bytes(uploaded_file.getbuffer())
    return dest


def _handle_uploads(store: ChatStore, uploaded_files) -> None:
    # file_uploader keeps returning the same files across reruns, so track what we already ingested
    processed = st.session_state.setdefault("processed_uploads", set())
    new_paths: list[str] = []

    for uploaded_file in uploaded_files:
        signature = f"{uploaded_file.name}:{uploaded_file.size}"
        if signature in processed:
            continue
        error = _validate_upload(uploaded_file)
        processed.add(signature)
        if error:
            st.error(error)
            continue
        new_paths.append(str(_save_uploaded_file(uploaded_file)))

    if not new_paths:
        return

    thread_id = st.session_state.get("thread_id")
    pending_query = None
    if thread_id:
        thread, _ = store.load_thread(thread_id)
        if thread and thread.status == "insufficient_evidence":
            pending_query = thread.pending_query

    trigger = "doc_added_retry" if pending_query else "new_upload_only"
    state = {
        "trigger": trigger,
        "session_id": st.session_state["session_id"],
        "pending_query": pending_query,
        "new_files": new_paths,
        "metrics": [],
    }

    with st.spinner(f"Indexing {len(new_paths)} document(s)..."):
        try:
            result = run_workflow(state)
        except Exception as exc:  # pragma: no cover - defensive UI guard
            st.error(f"Failed to index document(s): {exc}")
            return

    if result.get("error"):
        st.warning(f"Some files could not be indexed: {result['error']}")

    if thread_id:
        persist_turn_metrics(store, thread_id, result)

    if trigger == "doc_added_retry" and thread_id:
        if result.get("status") == "error":
            st.error(f"Indexed the document(s), but couldn't re-answer: {result.get('error')}")
        else:
            answer = result.get("answer") or ""
            store.append_message(
                thread_id, "assistant", answer,
                citations=result.get("citations", []), confidence=result.get("confidence"),
            )
            store.update_thread_state(thread_id, result.get("pending_query"), result.get("status"))
            st.toast(f"Indexed {len(new_paths)} document(s) and re-answered your pending question.")
    else:
        st.toast(f"Indexed {len(new_paths)} document(s) into the knowledge base.")

    st.session_state["last_turn_summary"] = result
    st.rerun()


def render_sidebar(store: ChatStore) -> None:
    with st.sidebar:
        st.header("Your documents")
        files = _list_session_files()
        with st.expander(f"{len(files)} document(s) uploaded in this session", expanded=False):
            for name in files or ["Upload a document to begin"]:
                st.caption(name)
        st.caption("This assistant cannot change its safety rules or reveal internal configuration, even if asked.")

        uploaded_files = st.file_uploader(
            "Upload PDF / Word / Excel / CSV / TXT",
            type=sorted(settings.allowed_extensions),
            accept_multiple_files=True,
        )
        if uploaded_files:
            _handle_uploads(store, uploaded_files)

        st.divider()
        st.header("Chats")
        if st.button("+ New chat", use_container_width=True):
            st.session_state["thread_id"] = None
            st.session_state["last_turn_summary"] = None
            st.rerun()

        for thread in store.list_threads():
            label = thread.title[:40] + ("..." if len(thread.title) > 40 else "")
            is_active = thread.thread_id == st.session_state.get("thread_id")
            if st.button(
                ("* " if is_active else "") + label,
                key=f"thread_{thread.thread_id}",
                use_container_width=True,
            ):
                st.session_state["thread_id"] = thread.thread_id
                st.session_state["last_turn_summary"] = None
                st.rerun()

        st.divider()
        st.header("Retention")
        st.session_state.setdefault("retention_days", settings.default_retention_days)
        days = st.number_input(
            "Clear chats older than (days)", min_value=1, max_value=365, key="retention_days"
        )

        confirm_pending = st.session_state.get("reset_confirm_pending", False)
        cols = st.columns(2) if confirm_pending else st.columns(1)
        clear_label = "Confirm delete?" if confirm_pending else "Clear old chats"
        if cols[0].button(clear_label, use_container_width=True):
            if confirm_pending:
                deleted = store.delete_threads_older_than(
                    int(days), exclude_thread_id=st.session_state.get("thread_id")
                )
                st.session_state["reset_confirm_pending"] = False
                st.toast(f"Cleared {deleted} old chat(s).")
            else:
                st.session_state["reset_confirm_pending"] = True
            st.rerun()
        if confirm_pending and cols[1].button("Cancel", use_container_width=True):
            st.session_state["reset_confirm_pending"] = False
            st.rerun()
