"""
agents/credibility_agent.py
------------------------------
Credibility Agent: assigns each article a transparent 0-1 credibility score
based on its resolved publisher domain (config/sources.py:DOMAIN_CREDIBILITY).

Design assumption (stated explicitly, per the assignment's ask for
"transparent assumptions"): credibility here is a proxy for *editorial
track record / wire-service standard*, not a fact-check of the specific
claim. It answers "how much should a busy exec trust this source in
general?", not "is this specific deal 100% confirmed?". The newsletter
surfaces the credibility label so the reader can calibrate accordingly.
"""

from __future__ import annotations
from typing import List
from config.sources import credibility_for_url
from agents.state import PipelineState, Article, log


def _label_for_score(score: float) -> str:
    if score >= 0.85:
        return "High (Tier-1 wire/financial press)"
    if score >= 0.65:
        return "Medium-High (established business media)"
    if score >= 0.50:
        return "Medium (aggregator / press release)"
    return "Low (unverified source — treat as unconfirmed)"


def run(state: PipelineState, min_credibility: float = 0.0) -> PipelineState:
    relevant = state.get("relevant_articles", [])
    scored: List[Article] = []
    for a in relevant:
        link = a.get("link", "")
        score = credibility_for_url(link)
        a["credibility_score"] = score
        a["credibility_label"] = _label_for_score(score)
        scored.append(a)

    # Sort by (relevance, credibility) so the newsletter naturally leads
    # with the most relevant AND most credible deals.
    scored.sort(key=lambda x: (x.get("relevance_score", 0), x.get("credibility_score", 0)), reverse=True)

    if min_credibility > 0:
        scored = [a for a in scored if a["credibility_score"] >= min_credibility]

    state["scored_articles"] = scored
    avg_cred = round(sum(a["credibility_score"] for a in scored) / len(scored), 2) if scored else 0
    log(state, f"Credibility Agent: scored {len(scored)} articles, avg credibility={avg_cred}")
    return state
