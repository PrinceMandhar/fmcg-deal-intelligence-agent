"""
agents/supervisor.py
-----------------------
Supervisor Agent: orchestrates the full pipeline as an explicit LangGraph
StateGraph. This is what makes it a genuine multi-agent *workflow* rather
than a sequential script — each node is independently testable, the graph
is inspectable, and it's trivial to add branches later (e.g. a human-review
node, or a parallel fan-out over multiple query contexts).

Graph:

    START
      -> news_discovery
      -> cleaning
      -> deduplication
      -> relevance
      -> credibility
      -> deal_extraction
      -> newsletter
      -> END

If LangGraph isn't installed for some reason, `run_linear()` provides a
pure-Python fallback with the identical node sequence, so the pipeline
never hard-fails on that dependency.
"""

from __future__ import annotations
from typing import Optional
from functools import partial

from datetime import date as date_type

from agents.state import PipelineState, new_state, log
from agents import (
    news_agent, cleaning_agent, date_filter_agent, dedup_agent,
    relevance_agent, credibility_agent, extraction_agent, newsletter_agent,
)


def run_linear(
    query_context: str = "FMCG M&A and investment activity",
    groq_api_key: Optional[str] = None,
    use_semantic_dedup: bool = False,
    max_items_per_feed: int = 25,
    relevance_threshold: float = 0.35,
    date_mode: str = "all",
    custom_from: Optional[date_type] = None,
    custom_to: Optional[date_type] = None,
) -> PipelineState:
    """Pure-Python sequential fallback (no LangGraph dependency required)."""
    state = new_state(query_context)
    state = news_agent.run(state, max_items_per_feed=max_items_per_feed)
    state = cleaning_agent.run(state)
    state = date_filter_agent.run(state, mode=date_mode, custom_from=custom_from, custom_to=custom_to)
    state = dedup_agent.run(state, use_semantic=use_semantic_dedup)
    state = relevance_agent.run(state, threshold=relevance_threshold)
    state = credibility_agent.run(state)
    state = extraction_agent.run(state, groq_api_key=groq_api_key)
    state = newsletter_agent.run(state, groq_api_key=groq_api_key)
    log(state, "Supervisor Agent: pipeline complete")
    return state


def build_graph(
    groq_api_key: Optional[str] = None,
    use_semantic_dedup: bool = False,
    relevance_threshold: float = 0.35,
    date_mode: str = "all",
    custom_from: Optional[date_type] = None,
    custom_to: Optional[date_type] = None,
):
    """Build a LangGraph StateGraph mirroring run_linear(), node-for-node."""
    from langgraph.graph import StateGraph, END

    graph = StateGraph(dict)

    graph.add_node("news_discovery", lambda s: news_agent.run(s))
    graph.add_node("cleaning", lambda s: cleaning_agent.run(s))
    graph.add_node("date_filter", lambda s: date_filter_agent.run(s, mode=date_mode, custom_from=custom_from, custom_to=custom_to))
    graph.add_node("deduplication", lambda s: dedup_agent.run(s, use_semantic=use_semantic_dedup))
    graph.add_node("relevance", lambda s: relevance_agent.run(s, threshold=relevance_threshold))
    graph.add_node("credibility", lambda s: credibility_agent.run(s))
    graph.add_node("deal_extraction", lambda s: extraction_agent.run(s, groq_api_key=groq_api_key))
    graph.add_node("newsletter", lambda s: newsletter_agent.run(s, groq_api_key=groq_api_key))

    graph.set_entry_point("news_discovery")
    graph.add_edge("news_discovery", "cleaning")
    graph.add_edge("cleaning", "date_filter")
    graph.add_edge("date_filter", "deduplication")
    graph.add_edge("deduplication", "relevance")
    graph.add_edge("relevance", "credibility")
    graph.add_edge("credibility", "deal_extraction")
    graph.add_edge("deal_extraction", "newsletter")
    graph.add_edge("newsletter", END)

    return graph.compile()


def run_graph(
    query_context: str = "FMCG M&A and investment activity",
    groq_api_key: Optional[str] = None,
    use_semantic_dedup: bool = False,
    relevance_threshold: float = 0.35,
    date_mode: str = "all",
    custom_from: Optional[date_type] = None,
    custom_to: Optional[date_type] = None,
) -> PipelineState:
    """Run via LangGraph if available, else transparently fall back to run_linear()."""
    try:
        app = build_graph(groq_api_key, use_semantic_dedup, relevance_threshold, date_mode, custom_from, custom_to)
        state = new_state(query_context)
        result = app.invoke(state)
        log(result, "Supervisor Agent (LangGraph): pipeline complete")
        return result
    except ImportError:
        print("[supervisor] langgraph not installed, using linear fallback")
        return run_linear(
            query_context, groq_api_key, use_semantic_dedup,
            relevance_threshold=relevance_threshold,
            date_mode=date_mode, custom_from=custom_from, custom_to=custom_to,
        )
