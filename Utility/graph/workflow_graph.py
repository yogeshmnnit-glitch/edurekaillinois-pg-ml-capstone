"""LangGraph StateGraph wiring the five agents with a conditional entry point.

Entry point depends on state['trigger']:
- "new_query"        -> planner -> retrieval -> reasoning -> validation
- "doc_added_retry"  -> ingestion -> retrieval -> reasoning -> validation (planner skipped)
- "new_upload_only"  -> ingestion -> END
Any node that sets status="error" short-circuits the remaining pipeline to END.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from Utility.agents.ingestion_agent import ingestion_node
from Utility.agents.planner_agent import planner_node
from Utility.agents.reasoning_agent import reasoning_node
from Utility.agents.retrieval_agent import retrieval_node
from Utility.agents.validation_agent import validation_node
from Utility.graph.state import GraphState


def _route_entry(state: GraphState) -> str:
    trigger = state.get("trigger", "new_query")
    return "ingestion" if trigger in ("doc_added_retry", "new_upload_only") else "planner"


def _route_after_ingestion(state: GraphState) -> str:
    return END if state.get("trigger") == "new_upload_only" else "retrieval"


def _continue_if_ok(next_node: str):
    def _router(state: GraphState) -> str:
        return END if state.get("status") == "error" else next_node

    return _router


def build_graph() -> StateGraph:
    """Construct (uncompiled) StateGraph wiring the five agents together."""
    graph = StateGraph(GraphState)

    graph.add_node("planner", planner_node)
    graph.add_node("ingestion", ingestion_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("reasoning", reasoning_node)
    graph.add_node("validation", validation_node)

    graph.add_conditional_edges(START, _route_entry, {"planner": "planner", "ingestion": "ingestion"})
    graph.add_conditional_edges("ingestion", _route_after_ingestion, {"retrieval": "retrieval", END: END})
    graph.add_conditional_edges("planner", _continue_if_ok("retrieval"), {"retrieval": "retrieval", END: END})
    graph.add_conditional_edges("retrieval", _continue_if_ok("reasoning"), {"reasoning": "reasoning", END: END})
    graph.add_conditional_edges(
        "reasoning", _continue_if_ok("validation"), {"validation": "validation", END: END}
    )
    graph.add_edge("validation", END)

    return graph


_compiled_graph: CompiledStateGraph | None = None


def get_compiled_graph() -> CompiledStateGraph:
    """Return a lazily-built, module-cached compiled graph instance."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph().compile()
    return _compiled_graph


def run_workflow(state: GraphState) -> GraphState:
    """Invoke the compiled graph with the given initial state and return the final state."""
    return get_compiled_graph().invoke(state)
