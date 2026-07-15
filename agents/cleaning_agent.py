"""
agents/cleaning_agent.py
--------------------------
Cleaning Agent: strips HTML tags/entities from RSS summaries, normalizes
whitespace, drops boilerplate ("Read more", "Continue reading..."), and
removes articles missing essential fields.
"""

from __future__ import annotations
import re
import html
import warnings
from typing import List
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

from agents.state import PipelineState, Article, log

BOILERPLATE_PATTERNS = [
    r"read more.*$",
    r"continue reading.*$",
    r"click here.*$",
    r"\[.*?\]",          # [Reuters], [ET Bureau] style tags at end
    r"the post .* appeared first on .*$",
]

_BOILERPLATE_RE = re.compile("|".join(BOILERPLATE_PATTERNS), flags=re.IGNORECASE)


def strip_html(raw: str) -> str:
    if not raw:
        return ""
    text = BeautifulSoup(html.unescape(raw), "html.parser").get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    text = _BOILERPLATE_RE.sub("", text).strip()
    return text


def clean_article(article: Article) -> Article:
    cleaned = dict(article)
    title = strip_html(article.get("title", ""))
    summary = strip_html(article.get("summary", ""))
    cleaned["title"] = title
    cleaned["summary"] = summary
    cleaned["cleaned_text"] = f"{title}. {summary}".strip()
    return cleaned  # type: ignore


def run(state: PipelineState) -> PipelineState:
    raw = state.get("raw_articles", [])
    cleaned: List[Article] = []
    dropped = 0
    for a in raw:
        c = clean_article(a)
        if not c.get("title") or len(c.get("cleaned_text", "")) < 15:
            dropped += 1
            continue
        cleaned.append(c)

    state["cleaned_articles"] = cleaned
    log(state, f"Cleaning Agent: cleaned {len(cleaned)} articles, dropped {dropped} empty/malformed")
    return state
