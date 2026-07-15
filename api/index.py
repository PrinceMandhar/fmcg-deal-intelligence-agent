"""
api/index.py
--------------
FastAPI backend for the Vercel deployment. Vercel's Python runtime
auto-detects an ASGI app named `app` in this file and serves it as a
serverless function — no extra adapter needed.

Endpoints:
  GET /api/health
  GET /api/run    -> runs the pipeline, returns structured newsletter JSON
  GET /api/pdf    -> runs the pipeline, streams back a PDF file

The Groq API key is backend-only: set GROQ_API_KEY as a Vercel
Environment Variable (Project Settings -> Environment Variables). It is
never accepted as a request parameter.

Note on scope: this API intentionally serves CSV/JSON/PDF only (not
DOCX/XLSX/PPTX) to keep the serverless bundle small — see
requirements-vercel.txt. Use the Streamlit app (or `python run_pipeline.py`
locally) for the full DOCX/XLSX/PPTX export set.
"""

from __future__ import annotations
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agents.supervisor import run_linear
from utils.backend_config import get_groq_api_key
from utils.date_utils import DATE_MODES
from exporters.data_export import export_csv_string
from exporters.pdf_export import export_pdf_bytes

app = FastAPI(title="FMCG Deal Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your frontend's domain in production
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _parse_iso_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def _run(max_items: int, threshold: float, date_mode: str, from_date: Optional[str], to_date: Optional[str]):
    groq_key = get_groq_api_key()  # backend-only
    state = run_linear(
        groq_api_key=groq_key,
        use_semantic_dedup=False,  # sklearn not bundled in the Vercel-lite deployment
        relevance_threshold=threshold,
        max_items_per_feed=max_items,
        date_mode=date_mode,
        custom_from=_parse_iso_date(from_date),
        custom_to=_parse_iso_date(to_date),
    )
    return state


@app.get("/api/health")
def health():
    return {"status": "ok", "groq_configured": bool(get_groq_api_key())}


@app.get("/api/date-modes")
def date_modes():
    return DATE_MODES


@app.get("/api/run")
def run_pipeline_api(
    max_items: int = Query(25, ge=5, le=60, description="Max articles per RSS feed (5-60)"),
    threshold: float = Query(0.35, ge=0.0, le=1.0),
    date_mode: str = Query("all", description="today | last_30_days | ytd | custom | all"),
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD, required if date_mode=custom"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD, defaults to today"),
):
    state = _run(max_items, threshold, date_mode, from_date, to_date)
    newsletter = state.get("newsletter_structured", {})
    return JSONResponse({
        "newsletter_markdown": state.get("newsletter_markdown", ""),
        "newsletter": newsletter,
        "date_filter_range": state.get("date_filter_range", {}),
        "counts": {
            "raw": len(state.get("raw_articles", [])),
            "cleaned": len(state.get("cleaned_articles", [])),
            "deduped": len(state.get("deduped_articles", [])),
            "relevant": len(state.get("relevant_articles", [])),
            "deals": len(state.get("extracted_deals", [])),
        },
        "agent_log": state.get("agent_log", []),
        "groq_active": bool(get_groq_api_key()),
    })


@app.get("/api/csv")
def download_csv(
    max_items: int = Query(25, ge=5, le=60),
    threshold: float = Query(0.35, ge=0.0, le=1.0),
    date_mode: str = Query("all"),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
):
    state = _run(max_items, threshold, date_mode, from_date, to_date)
    csv_text = export_csv_string(state)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=fmcg_deals.csv"},
    )


@app.get("/api/pdf")
def download_pdf(
    max_items: int = Query(25, ge=5, le=60),
    threshold: float = Query(0.35, ge=0.0, le=1.0),
    date_mode: str = Query("all"),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
):
    state = _run(max_items, threshold, date_mode, from_date, to_date)
    newsletter = state.get("newsletter_structured", {})
    date_range = state.get("date_filter_range", {})
    label = "All time" if date_mode == "all" else f"{date_range.get('from', '—')} to {date_range.get('to', '—')}"

    pdf_bytes = export_pdf_bytes(newsletter, date_filter_label=label)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=fmcg_newsletter.pdf"},
    )
