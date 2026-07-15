"""
agents/state.py
----------------
Shared state object that flows through the LangGraph pipeline. Every agent
reads from and writes to this single dict-like state (this is the standard
LangGraph pattern), which makes the pipeline auditable end-to-end: at any
point you can dump `state` to JSON and see exactly what each agent did.
"""

from __future__ import annotations
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime


class Article(TypedDict, total=False):
    id: str                      # stable hash id
    title: str
    link: str
    summary: str
    published: str                     # raw string as given by the RSS feed
    published_dt: Optional[str]        # ISO-8601 parsed datetime (UTC), or None if unparseable
    published_display: str             # human-readable, e.g. "14 Jul 2026"
    source_feed: str
    domain: str
    cleaned_text: str
    is_duplicate: bool
    duplicate_of: Optional[str]
    relevance_score: float
    is_relevant: bool
    credibility_score: float
    credibility_label: str
    deal: Optional[Dict[str, Any]]  # extracted structured deal fields


class PipelineState(TypedDict, total=False):
    query_context: str
    run_started_at: str
    raw_articles: List[Article]
    cleaned_articles: List[Article]
    deduped_articles: List[Article]
    relevant_articles: List[Article]
    scored_articles: List[Article]
    extracted_deals: List[Article]
    newsletter_markdown: str
    newsletter_structured: Dict[str, Any]
    agent_log: List[str]
    errors: List[str]
    date_filter_mode: str
    date_filter_range: Dict[str, Any]


def new_state(query_context: str = "FMCG M&A and investment activity") -> PipelineState:
    return PipelineState(
        query_context=query_context,
        run_started_at=datetime.utcnow().isoformat(),
        raw_articles=[],
        cleaned_articles=[],
        deduped_articles=[],
        relevant_articles=[],
        scored_articles=[],
        extracted_deals=[],
        newsletter_markdown="",
        newsletter_structured={},
        agent_log=[],
        errors=[],
    )


def log(state: PipelineState, message: str) -> None:
    stamp = datetime.utcnow().strftime("%H:%M:%S")
    state.setdefault("agent_log", []).append(f"[{stamp}] {message}")
