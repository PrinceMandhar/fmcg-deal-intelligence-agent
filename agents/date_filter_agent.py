"""
agents/date_filter_agent.py
------------------------------
Date Filter Agent: keeps only articles published within the user-chosen
window. Runs right after Cleaning, before Deduplication — no point running
dedup/relevance/credibility/LLM-extraction on articles that will be
filtered out anyway (saves time + LLM cost).

Modes (see utils/date_utils.py):
  "today"         -> only today's news
  "last_30_days"  -> last month till date
  "ytd"           -> Jan 1 (this year) till date
  "custom"        -> explicit from_date / to_date
  "all"           -> no filtering (default, matches old behaviour)
"""

from __future__ import annotations
import sys
from pathlib import Path
from datetime import date, datetime
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.state import PipelineState, Article, log
from utils.date_utils import get_date_range, is_within_range


def run(
    state: PipelineState,
    mode: str = "all",
    custom_from: Optional[date] = None,
    custom_to: Optional[date] = None,
) -> PipelineState:
    cleaned = state.get("cleaned_articles", [])
    from_dt, to_dt = get_date_range(mode, custom_from, custom_to)

    kept: List[Article] = []
    unknown_date_count = 0
    for a in cleaned:
        pub_dt_str = a.get("published_dt")
        pub_dt = datetime.fromisoformat(pub_dt_str) if pub_dt_str else None
        if pub_dt is None:
            unknown_date_count += 1
        if is_within_range(pub_dt, from_dt, to_dt):
            kept.append(a)

    state["cleaned_articles"] = kept  # pipeline continues from the filtered set
    state["date_filter_mode"] = mode
    state["date_filter_range"] = {
        "from": from_dt.isoformat() if from_dt else None,
        "to": to_dt.isoformat() if to_dt else None,
    }

    label = "no filter (all time)" if mode == "all" else f"mode={mode}, {from_dt} -> {to_dt}"
    log(
        state,
        f"Date Filter Agent: {len(cleaned)} -> {len(kept)} articles within range "
        f"({label}); {unknown_date_count} had unknown dates and were kept",
    )
    return state
