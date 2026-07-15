"""
agents/newsletter_agent.py
-----------------------------
Newsletter Agent: turns the scored + extracted deals into a short,
structured newsletter draft that "a business user could realistically skim"
(the assignment's own bar).

Two paths, same output shape:
  - LLM path (Groq): writes a punchy 2-3 sentence executive summary.
  - Fallback path: template-based executive summary (still coherent,
    just less stylistically varied) — again, works with zero config.

Output: both a Markdown string (for the demo app / GitHub README-style
preview) AND a structured dict (for the Export Agent to turn into
Word/Excel/PPT).
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.state import PipelineState, Article, log


def _groq_summary(deals: List[Article], api_key: str) -> Optional[str]:
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        bullet_lines = []
        for a in deals[:10]:
            d = a.get("deal", {}) or {}
            bullet_lines.append(
                f"- {a.get('title')} | type={d.get('deal_type')} amount={d.get('amount')}"
            )
        prompt = (
            "Write a crisp 3-sentence executive summary (no headers, no "
            "bullet points, plain prose) for a business newsletter about "
            "recent FMCG M&A/investment activity, based on these deal "
            "headlines:\n" + "\n".join(bullet_lines)
        )
        resp = client.chat.completions.create(
            model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=220,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[newsletter_agent] Groq summary failed, falling back: {e}")
        return None


def _template_summary(deals: List[Article]) -> str:
    n = len(deals)
    deal_types = {}
    for a in deals:
        dt = (a.get("deal", {}) or {}).get("deal_type", "unspecified")
        deal_types[dt] = deal_types.get(dt, 0) + 1
    top_type = max(deal_types, key=deal_types.get) if deal_types else "deal"
    top_companies = []
    for a in deals[:5]:
        title = a.get("title", "")
        top_companies.append(title.split(":")[0][:60])

    return (
        f"This edition tracks {n} notable FMCG deal-related developments, with "
        f"'{top_type.replace('_', ' ')}' activity leading the pack. Highlights include "
        f"movement around {', '.join(top_companies[:3]) if top_companies else 'several major players'}. "
        f"As always, treat lower-credibility items as directional rather than confirmed."
    )


def _deal_row(a: Article) -> Dict[str, Any]:
    d = a.get("deal", {}) or {}
    return {
        "title": a.get("title", ""),
        "deal_type": d.get("deal_type", "unspecified"),
        "acquirer": d.get("acquirer") or "—",
        "target": d.get("target") or "—",
        "amount": d.get("amount") or "—",
        "sector": d.get("sector") or "FMCG",
        "country": d.get("country") or "—",
        "credibility_label": a.get("credibility_label", ""),
        "credibility_score": a.get("credibility_score", 0),
        "relevance_score": a.get("relevance_score", 0),
        "source": a.get("domain", ""),
        "link": a.get("link", ""),
        "published": a.get("published_display") or a.get("published", "") or "Date unknown",
    }


def run(state: PipelineState, groq_api_key: Optional[str] = None, max_deals: int = 15) -> PipelineState:
    from utils.backend_config import get_groq_api_key
    groq_api_key = groq_api_key or get_groq_api_key()
    deals = state.get("extracted_deals", [])[:max_deals]

    exec_summary = None
    if groq_api_key and deals:
        exec_summary = _groq_summary(deals, groq_api_key)
    if not exec_summary:
        exec_summary = _template_summary(deals) if deals else "No FMCG deal activity met the relevance threshold in this run."

    rows = [_deal_row(a) for a in deals]

    # Simple market trend insight: distribution by deal type
    type_counts: Dict[str, int] = {}
    for r in rows:
        type_counts[r["deal_type"]] = type_counts.get(r["deal_type"], 0) + 1

    generated_at = datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")

    md_lines = [
        f"# FMCG Deal Intelligence Newsletter",
        f"*Generated {generated_at} · {len(rows)} deals tracked*",
        "",
        "## Executive Summary",
        exec_summary,
        "",
        "## Top Deals",
    ]
    for r in rows:
        md_lines.append(
            f"- **{r['title']}** — {r['deal_type'].replace('_', ' ').title()}"
            + (f", {r['amount']}" if r['amount'] != '—' else "")
            + f"  \n  _{r['published']} · Source: {r['source']} ({r['credibility_label']})_"
        )
    md_lines += [
        "",
        "## Market Trend Snapshot",
    ]
    for dtype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        md_lines.append(f"- {dtype.replace('_', ' ').title()}: {count} deal(s)")

    md_lines += [
        "",
        "## Methodology & Assumptions",
        "- Sources: free public RSS feeds (see README for full list).",
        "- Relevance: rule-based keyword scoring (FMCG company + deal action co-occurrence).",
        "- Credibility: static publisher-tier table, a proxy for editorial track record, not fact-verification.",
        "- Deduplication: exact URL/title match + TF-IDF cosine similarity on article text.",
    ]

    newsletter_markdown = "\n".join(md_lines)

    state["newsletter_markdown"] = newsletter_markdown
    state["newsletter_structured"] = {
        "generated_at": generated_at,
        "executive_summary": exec_summary,
        "deals": rows,
        "trend_snapshot": type_counts,
    }
    log(state, f"Newsletter Agent: assembled newsletter with {len(rows)} deals")
    return state
