"""Streamlit entrypoint for the multi-agent enterprise knowledge assistant."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import extra_streamlit_components as stx
import streamlit as st

from Utility.config.settings import settings
from Utility.storage.db import ChatStore
from Utility.ui.chat_panel import render_chat
from Utility.ui.observability_panel import render_observability
from Utility.ui.sidebar import render_sidebar


def get_store(session_id: str) -> ChatStore:
    session_db = settings.project_root / "Utility" / "storage" / "sessions" / f"{session_id}.db"
    return ChatStore(db_path=session_db)


def _is_valid_session_id(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value) is not None


def get_persistent_session_id(current_session_id: str | None = None) -> str:
    """Restore the browser identity from a cookie or create it on first visit."""
    cookie_manager = stx.CookieManager(key="browser_session_cookie")
    incoming_cookie = st.context.cookies.get("browser_session_id")
    component_cookie = cookie_manager.get("browser_session_id")

    if _is_valid_session_id(current_session_id):
        # Preserve the ID used by an already-running tab, including pre-cookie sessions.
        session_id = current_session_id
    elif _is_valid_session_id(incoming_cookie):
        # This is available immediately for a new tab or a browser reconnect.
        session_id = incoming_cookie
    elif _is_valid_session_id(component_cookie):
        session_id = component_cookie
    else:
        session_id = uuid4().hex

    if session_id != incoming_cookie:
        cookie_manager.set(
            "browser_session_id",
            session_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=3650),
        )
    return session_id


def main() -> None:
    st.set_page_config(page_title="3GPP Knowledge Assistant", page_icon="\U0001F4E1", layout="wide")

    logo_col, title_col = st.columns([1, 5])
    with logo_col:
        st.image("UI Images/3gpp_logo.svg", width=100)
    with title_col:
        st.title("3rd Generation Partnership Project (3GPP) Knowledge Assistant")
        st.caption(
            "Ask questions about your uploaded telecom/3GPP documents. "
            "Answers are grounded in retrieved evidence only."
        )

    st.session_state["session_id"] = get_persistent_session_id(st.session_state.get("session_id"))
    store = get_store(st.session_state["session_id"])
    st.session_state.setdefault("thread_id", None)
    st.session_state.setdefault("last_turn_summary", None)
    st.session_state.setdefault("reset_confirm_pending", False)

    render_sidebar(store)

    chat_col, obs_col = st.columns([3, 1])
    with chat_col:
        render_chat(store)
    with obs_col:
        render_observability(store)


if __name__ == "__main__":
    main()
