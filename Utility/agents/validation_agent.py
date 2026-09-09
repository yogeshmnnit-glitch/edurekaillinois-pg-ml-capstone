"""Validation agent - scores confidence and gates the final answer against weak evidence."""
from __future__ import annotations

import re

from Utility.config.prompts import INSUFFICIENT_EVIDENCE_MESSAGE, SAFETY_VIOLATION_MESSAGE, VALIDATION_SYSTEM_PROMPT
from Utility.config.settings import settings
from Utility.graph.state import GraphState, NodeMetric
from Utility.llm.openai_client import LLMClientError, OpenAIClient
from Utility.security.sanitizer import is_suspicious_text

_STOP_WORDS = {"a", "about", "an", "and", "are", "is", "me", "of", "tell", "the", "what"}
_INSUFFICIENT_ANSWER_PHRASES = (
    "don't have enough information",
    "do not have enough information",
    "not enough information",
    "cannot answer",
    "can't answer",
    "unable to answer",
)


def _compute_confidence(state: GraphState) -> float:
    chunks = state.get("retrieved_chunks", [])
    if not chunks:
        return 0.0
    similarities = [chunk["similarity"] for chunk in chunks]
    semantic_score = max(similarities)

    query = (state.get("pending_query") or state.get("query", "")).lower()
    query_terms = {term for term in re.findall(r"[a-z0-9]+", query) if term not in _STOP_WORDS}
    context = " ".join(chunk["text"] for chunk in chunks).lower()
    context_terms = set(re.findall(r"[a-z0-9]+", context))
    lexical_score = len(query_terms & context_terms) / len(query_terms) if query_terms else 0.0

    return max(0.0, min(1.0, max(semantic_score, lexical_score)))


def _answer_declines_evidence(state: GraphState) -> bool:
    answer = (state.get("answer") or "").lower()
    return any(phrase in answer for phrase in _INSUFFICIENT_ANSWER_PHRASES)


def validation_node(state: GraphState, client: OpenAIClient | None = None) -> dict:
    """Decide whether the generated answer is sufficiently grounded and safe to show."""
    answer = state.get("answer", "")
    query = (state.get("pending_query") or state.get("query", "")).strip()

    if is_suspicious_text(answer):
        return {
            "confidence": 0.0,
            "status": "safety_violation",
            "answer": SAFETY_VIOLATION_MESSAGE,
            "pending_query": query or None,
        }

    confidence = _compute_confidence(state)
    has_citations = bool(state.get("citations"))

    if confidence < settings.confidence_threshold or not has_citations or _answer_declines_evidence(state):
        return {
            "confidence": 0.0 if _answer_declines_evidence(state) else confidence,
            "status": "insufficient_evidence",
            "answer": INSUFFICIENT_EVIDENCE_MESSAGE,
            "pending_query": query or None,
        }

    verdict = _llm_verify(state, client)
    if verdict == "UNSAFE":
        return {
            "confidence": 0.0,
            "status": "safety_violation",
            "answer": SAFETY_VIOLATION_MESSAGE,
            "pending_query": query or None,
        }
    if verdict == "UNGROUNDED":
        return {
            "confidence": confidence * 0.5,
            "status": "insufficient_evidence",
            "answer": INSUFFICIENT_EVIDENCE_MESSAGE,
            "pending_query": query or None,
        }

    return {
        "confidence": confidence,
        "status": "answered",
        "pending_query": None,
    }


def _llm_verify(state: GraphState, client: OpenAIClient | None) -> str:
    """LLM-based safety/grounding check. Returns SAFE, UNSAFE, or UNGROUNDED."""
    try:
        llm = client or OpenAIClient()
    except LLMClientError:
        return "SAFE"

    query = (state.get("pending_query") or state.get("query", "")).strip()
    answer = state.get("answer", "")
    chunks_text = "\n".join(c["text"] for c in state.get("retrieved_chunks", []))

    user_msg = f"user_query: {query}\nanswer: {answer}\ncontext_chunks: {chunks_text}"

    import time
    start = time.perf_counter()
    try:
        result = llm.chat(
            messages=[
                {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0,
        )
    except LLMClientError:
        return "SAFE"
    latency_ms = (time.perf_counter() - start) * 1000

    metric: NodeMetric = {
        "node": "validation",
        "latency_ms": latency_ms,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "total_tokens": result.total_tokens,
    }
    state.setdefault("metrics", []).append(metric)

    label = result.content.strip().upper()
    return label if label in ("SAFE", "UNSAFE", "UNGROUNDED") else "SAFE"
