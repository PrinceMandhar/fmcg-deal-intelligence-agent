"""
exporters/data_export.py
--------------------------
Raw data exporters: CSV and JSON, as required by the assignment's
"Raw data in CSV/JSON" deliverable.
"""

from __future__ import annotations
import json
import csv
from pathlib import Path
from typing import Dict, Any


def export_json(state: Dict[str, Any], out_path: str) -> str:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "query_context": state.get("query_context"),
        "run_started_at": state.get("run_started_at"),
        "counts": {
            "raw": len(state.get("raw_articles", [])),
            "cleaned": len(state.get("cleaned_articles", [])),
            "deduped": len(state.get("deduped_articles", [])),
            "relevant": len(state.get("relevant_articles", [])),
            "scored": len(state.get("scored_articles", [])),
            "extracted_deals": len(state.get("extracted_deals", [])),
        },
        "agent_log": state.get("agent_log", []),
        "newsletter": state.get("newsletter_structured", {}),
        "articles": state.get("extracted_deals", []),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
    return out_path


CSV_FIELDNAMES = [
    "title", "published", "deal_type", "acquirer", "target", "amount", "sector",
    "country", "credibility_label", "credibility_score", "relevance_score",
    "source", "link",
]


def export_csv(state: Dict[str, Any], out_path: str) -> str:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    rows = state.get("newsletter_structured", {}).get("deals", [])
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in CSV_FIELDNAMES})
    return out_path


def export_csv_string(state: Dict[str, Any]) -> str:
    """In-memory CSV — used by the stateless Vercel API."""
    import io
    rows = state.get("newsletter_structured", {}).get("deals", [])
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDNAMES)
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k, "") for k in CSV_FIELDNAMES})
    return buffer.getvalue()
