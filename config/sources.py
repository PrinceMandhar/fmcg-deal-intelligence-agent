"""
config/sources.py
------------------
Central registry of free, no-API-key news sources (RSS feeds) used by the
News Discovery Agent, and a transparent credibility scoring table used by
the Credibility Agent.

Design principle: every assumption here is EXPLICIT and editable, so the
newsletter's credibility logic is auditable by a business user.
"""

from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# RSS FEEDS
# Each feed is tagged with a `default_tier` so that even before we look at
# the individual article's domain, we know roughly how trustworthy the feed
# itself is. The Credibility Agent still re-checks the *article* domain
# (Google News RSS, for example, redirects to many different publishers).
# ---------------------------------------------------------------------------
RSS_FEEDS = [
    # name, url, default_tier (1=highest, 3=lowest)
    {
        "name": "Google News - FMCG India",
        "url": "https://news.google.com/rss/search?q=FMCG+acquisition+OR+merger+OR+investment+India&hl=en-IN&gl=IN&ceid=IN:en",
        "default_tier": 2,
    },
    {
        "name": "Google News - Consumer Goods Deals",
        "url": "https://news.google.com/rss/search?q=%22consumer+goods%22+deal+OR+stake+OR+funding&hl=en-IN&gl=IN&ceid=IN:en",
        "default_tier": 2,
    },
    {
        "name": "Economic Times - Industry",
        "url": "https://economictimes.indiatimes.com/industry/rssfeeds/13352306.cms",
        "default_tier": 1,
    },
    {
        "name": "Mint - Companies",
        "url": "https://www.livemint.com/rss/companies",
        "default_tier": 1,
    },
    {
        "name": "Business Standard - Companies",
        "url": "https://www.business-standard.com/rss/companies-101.rss",
        "default_tier": 1,
    },
    {
        "name": "Reuters - Business",
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "default_tier": 1,
    },
    {
        "name": "CNBC TV18 - Business",
        "url": "https://www.cnbctv18.com/commonfeeds/v1/cne/rss/business.xml",
        "default_tier": 1,
    },
    {
        "name": "Financial Express - Industry",
        "url": "https://www.financialexpress.com/industry/feed/",
        "default_tier": 1,
    },
    {
        "name": "Yahoo Finance - Headlines",
        "url": "https://finance.yahoo.com/news/rssindex",
        "default_tier": 2,
    },
]

# ---------------------------------------------------------------------------
# CREDIBILITY TABLE (by publisher domain)
# Score is on a 0.0-1.0 scale. This is a *transparent, editable assumption*
# — not a claim of objective truth. Business users can tune this table.
# ---------------------------------------------------------------------------
DOMAIN_CREDIBILITY = {
    "reuters.com": 0.95,
    "economictimes.indiatimes.com": 0.90,
    "livemint.com": 0.88,
    "business-standard.com": 0.88,
    "cnbctv18.com": 0.85,
    "financialexpress.com": 0.82,
    "moneycontrol.com": 0.82,
    "thehindubusinessline.com": 0.85,
    "bloomberg.com": 0.95,
    "ft.com": 0.93,
    "wsj.com": 0.93,
    "finance.yahoo.com": 0.75,
    "yahoo.com": 0.72,
    "news.google.com": 0.60,  # aggregator wrapper; real score comes from resolved source
    "prnewswire.com": 0.65,   # press releases: factual but self-promotional
    "businesswire.com": 0.65,
}

DEFAULT_CREDIBILITY_UNKNOWN = 0.45  # unknown/unverified domain
DEFAULT_CREDIBILITY_PRESS_RELEASE_HINT = 0.60  # domains containing "pr"/"wire"


def get_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc.replace("www.", "")
    except Exception:
        return "unknown"


def credibility_for_url(url: str) -> float:
    domain = get_domain(url)
    if domain in DOMAIN_CREDIBILITY:
        return DOMAIN_CREDIBILITY[domain]
    if "wire" in domain or "pr" in domain:
        return DEFAULT_CREDIBILITY_PRESS_RELEASE_HINT
    return DEFAULT_CREDIBILITY_UNKNOWN
