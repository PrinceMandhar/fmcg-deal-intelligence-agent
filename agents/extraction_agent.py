"""
agents/extraction_agent.py
-----------------------------
Deal Extraction Agent: converts unstructured article text into structured
deal fields (acquirer, target, deal_type, amount, sector, country, ...).

Primary path: Groq-hosted Llama 3.3 70B (fast + free-tier friendly) with a
strict JSON-only prompt.

Fallback path (NO API key required — the demo must work out-of-the-box):
lightweight regex/heuristics that pull out a currency amount if present and
classify deal_type from keywords. This keeps the pipeline fully functional
even with zero configuration, which matters for a reviewer just cloning the
repo and hitting "Run".
"""

from __future__ import annotations
import os
import re
import json
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any

# Defensive bootstrap: guarantees the project root is importable even if
# this module is loaded in an unusual way (some IDE "Run" buttons, certain
# antivirus/quarantine scenarios that delay module discovery, etc.) rather
# than relying solely on the entry-point script having done this already.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.state import PipelineState, Article, log
from utils.backend_config import get_groq_model

GROQ_MODEL = get_groq_model()

DEAL_TYPE_KEYWORDS = {
    "acquisition": ["acquire", "acquisition", "acquired", "buyout", "takeover"],
    "stake_purchase": ["stake", "equity stake", "minority stake", "majority stake"],
    "merger": ["merger", "merges", "merge with"],
    "investment": ["invest", "investment", "funding", "raises", "series a", "series b", "series c"],
    "joint_venture": ["joint venture", " jv "],
    "divestment": ["divest", "divestment", "stake sale", "sells stake"],
    "ipo": ["ipo", "public offering", "initial public offering"],
}

AMOUNT_RE = re.compile(
    r"(?:(?:rs\.?|inr|₹)\s?[\d,]+(?:\.\d+)?\s?(?:crore|lakh|cr|bn|billion|million|mn)?"
    r"|(?:usd|\$)\s?[\d,]+(?:\.\d+)?\s?(?:billion|million|bn|mn)?"
    r"|[\d,]+(?:\.\d+)?\s?(?:crore|lakh|billion|million))",
    flags=re.IGNORECASE,
)


def _heuristic_extract(text: str) -> Dict[str, Any]:
    lower = text.lower()
    deal_type = "unspecified"
    for dtype, kws in DEAL_TYPE_KEYWORDS.items():
        if any(kw in lower for kw in kws):
            deal_type = dtype
            break

    amount_match = AMOUNT_RE.search(text)
    amount = amount_match.group(0).strip() if amount_match else None

    return {
        "acquirer": None,
        "target": None,
        "deal_type": deal_type,
        "amount": amount,
        "currency": None,
        "sector": "FMCG",
        "country": None,
        "extraction_method": "heuristic_fallback",
    }


def _groq_extract(text: str, api_key: str) -> Optional[Dict[str, Any]]:
    try:
        from groq import Groq
    except ImportError:
        return None

    system_prompt = (
        "You extract structured M&A/investment deal data from a short FMCG "
        "news snippet. Respond with ONLY a compact JSON object, no prose, "
        "no markdown fences. Schema: "
        '{"acquirer": string|null, "target": string|null, '
        '"deal_type": "acquisition"|"stake_purchase"|"merger"|"investment"|'
        '"joint_venture"|"divestment"|"ipo"|"unspecified", '
        '"amount": string|null, "currency": string|null, '
        '"sector": string|null, "country": string|null, '
        '"one_line_summary": string}. '
        "If a field is not mentioned, use null. Do not invent facts."
    )

    try:
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text[:1500]},
            ],
            temperature=0.1,
            max_tokens=300,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.MULTILINE).strip()
        data = json.loads(raw)
        data["extraction_method"] = "groq_llm"
        return data
    except Exception as e:
        print(f"[extraction_agent] Groq extraction failed, falling back: {e}")
        return None


def extract_deal(article: Article, api_key: Optional[str]) -> Dict[str, Any]:
    text = article.get("cleaned_text", "")
    if api_key:
        result = _groq_extract(text, api_key)
        if result:
            return result
    return _heuristic_extract(text)


def run(state: PipelineState, groq_api_key: Optional[str] = None, top_n: int = 30) -> PipelineState:
    from utils.backend_config import get_groq_api_key
    groq_api_key = groq_api_key or get_groq_api_key()
    scored = state.get("scored_articles", [])[:top_n]  # cap LLM calls for cost/speed control

    extracted: List[Article] = []
    llm_count = 0
    for a in scored:
        deal = extract_deal(a, groq_api_key)
        a["deal"] = deal
        if deal.get("extraction_method") == "groq_llm":
            llm_count += 1
        extracted.append(a)

    state["extracted_deals"] = extracted
    method = f"{llm_count}/{len(extracted)} via Groq LLM, rest heuristic fallback" if groq_api_key else "heuristic fallback only (no GROQ_API_KEY set)"
    log(state, f"Deal Extraction Agent: extracted structured fields for {len(extracted)} articles ({method})")
    return state
