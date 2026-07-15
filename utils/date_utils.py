"""
utils/date_utils.py
----------------------
Computes (from_datetime, to_datetime) windows for the News Date Filter.

Supported modes (shown in both the Streamlit UI and the Vercel API):
  - "today"        : 00:00 today  -> now
  - "last_30_days"  : now - 30 days -> now
  - "ytd"          : Jan 1 of current year -> now  ("Jan se till date")
  - "custom"       : caller-supplied from_date / to_date (inclusive)

All datetimes are timezone-naive UTC for simplicity, since RSS feed
timestamps are normalized to UTC on ingestion (see agents/news_agent.py).
"""

from __future__ import annotations
from datetime import datetime, timedelta, date
from typing import Optional, Tuple

DATE_MODES = {
    "today": "Today",
    "last_30_days": "Last 30 Days (Last Month till Date)",
    "ytd": "This Year (Jan till Date)",
    "custom": "Custom Range",
    "all": "All Time (no filter)",
}


def get_date_range(
    mode: str,
    custom_from: Optional[date] = None,
    custom_to: Optional[date] = None,
    now: Optional[datetime] = None,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Returns (from_dt, to_dt). Either can be None meaning 'no bound'."""
    now = now or datetime.utcnow()

    if mode == "today":
        start = datetime(now.year, now.month, now.day)
        return start, now

    if mode == "last_30_days":
        return now - timedelta(days=30), now

    if mode == "ytd":
        start = datetime(now.year, 1, 1)
        return start, now

    if mode == "custom":
        from_dt = datetime.combine(custom_from, datetime.min.time()) if custom_from else None
        to_dt = datetime.combine(custom_to, datetime.max.time()) if custom_to else now
        return from_dt, to_dt

    # "all" or unknown mode -> no filtering
    return None, None


def is_within_range(published_dt: Optional[datetime], from_dt: Optional[datetime], to_dt: Optional[datetime]) -> bool:
    """
    Articles with an unparseable/missing date are KEPT rather than dropped
    silently — losing a genuinely relevant deal because of a bad date
    string is worse than showing one extra article with 'Date unknown'.
    """
    if published_dt is None:
        return True
    if from_dt and published_dt < from_dt:
        return False
    if to_dt and published_dt > to_dt:
        return False
    return True
