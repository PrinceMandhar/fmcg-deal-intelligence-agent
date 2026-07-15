"""
agents/news_agent.py
---------------------
Ingestion Agent: pulls the latest articles from a set of free, no-API-key
RSS feeds (config/sources.py). No scraping of paywalled content — only
publicly syndicated headlines/summaries, which keeps this legally safe.

Real-time behaviour: RSS feeds update continuously, so every pipeline run
naturally reflects the latest developments — no separate "freshness" logic
is needed beyond re-running the pipeline (or scheduling it, see README).
"""

from __future__ import annotations
import hashlib
import time
from datetime import datetime
from typing import List, Optional
import feedparser

from config.sources import RSS_FEEDS, get_domain
from agents.state import PipelineState, Article, log


def _make_id(link: str, title: str) -> str:
    return hashlib.sha256(f"{link}|{title}".encode("utf-8")).hexdigest()[:16]


def _parse_published(entry) -> tuple[Optional[str], str]:
    """
    Returns (iso_datetime_or_None, human_display_string).

    Prefers feedparser's pre-parsed `published_parsed` (a struct_time,
    already normalized) — this is far more reliable than regexing the raw
    string, since RSS feeds use inconsistent date formats. Falls back to
    `dateutil` on the raw string, and finally to "Date unknown" if nothing
    works (article is still kept — see utils/date_utils.is_within_range).
    """
    struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if struct:
        try:
            dt = datetime(*struct[:6])
            return dt.isoformat(), dt.strftime("%d %b %Y")
        except Exception:
            pass

    raw = entry.get("published", "") or entry.get("updated", "")
    if raw:
        try:
            from dateutil import parser as dateutil_parser
            dt = dateutil_parser.parse(raw, ignoretz=True)
            return dt.isoformat(), dt.strftime("%d %b %Y")
        except Exception:
            pass

    return None, "Date unknown"


def fetch_feed(feed_url: str, feed_name: str, max_items: int = 25) -> List[Article]:
    articles: List[Article] = []
    try:
        parsed = feedparser.parse(feed_url)
        for entry in parsed.entries[:max_items]:
            link = entry.get("link", "")
            title = entry.get("title", "").strip()
            if not title or not link:
                continue
            summary = entry.get("summary", "") or entry.get("description", "")
            published_raw = entry.get("published", "") or entry.get("updated", "")
            published_dt, published_display = _parse_published(entry)
            articles.append(
                Article(
                    id=_make_id(link, title),
                    title=title,
                    link=link,
                    summary=summary,
                    published=published_raw,
                    published_dt=published_dt,
                    published_display=published_display,
                    source_feed=feed_name,
                    domain=get_domain(link),
                )
            )
    except Exception as e:
        # A single feed failing (timeout, feed moved, etc.) should never
        # crash the whole pipeline.
        print(f"[news_agent] WARNING: failed to fetch '{feed_name}': {e}")
    return articles


def run(state: PipelineState, feeds=None, max_items_per_feed: int = 25, polite_delay_s: float = 0.0) -> PipelineState:
    feeds = feeds or RSS_FEEDS
    all_articles: List[Article] = []
    for feed in feeds:
        items = fetch_feed(feed["url"], feed["name"], max_items=max_items_per_feed)
        all_articles.extend(items)
        if polite_delay_s:
            time.sleep(polite_delay_s)

    state["raw_articles"] = all_articles
    log(state, f"News Discovery Agent: fetched {len(all_articles)} raw articles from {len(feeds)} feeds")
    return state
