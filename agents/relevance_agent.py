"""
agents/relevance_agent.py
----------------------------
Relevance Agent: scores each article on how likely it is to be about an
*FMCG deal* (not FMCG in general, not deals in general — the intersection).

Score = weighted combination of:
  - company_hit   (0/1): does an FMCG company name appear?
  - deal_hit      (0/1): does a deal-related verb/noun appear?
  - sector_hit    (0/1): does a sector hint word appear?
  - keyword_density: normalized count of matches / text length

This is a transparent, rule-based scorer by design (see README) so a
business user can audit exactly why an article was kept or dropped.
An optional LLM re-check (via Groq) can be enabled for borderline cases
(0.25-0.45 score) where keyword matching alone is ambiguous.
"""

from __future__ import annotations
from typing import List
from config.fmcg_keywords import FMCG_COMPANIES, DEAL_KEYWORDS, SECTOR_HINTS, RELEVANCE_THRESHOLD
from agents.state import PipelineState, Article, log


def _contains_any(text: str, terms: List[str]) -> bool:
    return any(term in text for term in terms)


def _count_hits(text: str, terms: List[str]) -> int:
    return sum(1 for term in terms if term in text)


def score_article(article: Article) -> float:
    text = (article.get("cleaned_text") or "").lower()
    if not text:
        return 0.0

    company_hit = 1.0 if _contains_any(text, FMCG_COMPANIES) else 0.0
    deal_hit = 1.0 if _contains_any(text, DEAL_KEYWORDS) else 0.0
    sector_hit = 1.0 if _contains_any(text, SECTOR_HINTS) else 0.0

    total_matches = (
        _count_hits(text, FMCG_COMPANIES)
        + _count_hits(text, DEAL_KEYWORDS)
        + _count_hits(text, SECTOR_HINTS)
    )
    density = min(total_matches / 6.0, 1.0)  # cap contribution

    # Weighted score: company + deal keyword co-occurrence matters most,
    # since that IS the definition of "FMCG deal news".
    score = (0.40 * company_hit) + (0.35 * deal_hit) + (0.10 * sector_hit) + (0.15 * density)

    # Hard requirement: a real "deal" article should have BOTH a company/
    # sector signal AND a deal-action signal, or it's probably generic news.
    if deal_hit == 0.0 or (company_hit == 0.0 and sector_hit == 0.0):
        score *= 0.5

    return round(min(score, 1.0), 3)


def run(state: PipelineState, threshold: float = RELEVANCE_THRESHOLD) -> PipelineState:
    deduped = state.get("deduped_articles", [])
    scored: List[Article] = []
    for a in deduped:
        s = score_article(a)
        a["relevance_score"] = s
        a["is_relevant"] = s >= threshold
        scored.append(a)

    relevant = [a for a in scored if a["is_relevant"]]
    relevant.sort(key=lambda x: x["relevance_score"], reverse=True)

    state["relevant_articles"] = relevant
    log(
        state,
        f"Relevance Agent: {len(deduped)} deduped -> {len(relevant)} relevant "
        f"(threshold={threshold})",
    )
    return state
