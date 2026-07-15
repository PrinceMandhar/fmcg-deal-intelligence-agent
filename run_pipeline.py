#!/usr/bin/env python3
"""
run_pipeline.py
-----------------
CLI entry point: runs the full multi-agent pipeline end-to-end and writes
all deliverables (CSV, JSON, DOCX, XLSX, PPTX, PDF, newsletter markdown)
to data/output/.

The Groq API key is backend-only — set it via a .env file or environment
variable (GROQ_API_KEY). It is never passed as a CLI argument, so it never
ends up in shell history.

Usage:
    python run_pipeline.py
    python run_pipeline.py --max-items 30 --date-mode last_30_days
    python run_pipeline.py --date-mode custom --from-date 2026-01-01 --to-date 2026-07-15
    python run_pipeline.py --semantic-dedup
"""

from __future__ import annotations
import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from agents.supervisor import run_linear
from utils.backend_config import get_groq_api_key
from utils.date_utils import DATE_MODES, get_date_range
from exporters.data_export import export_json, export_csv
from exporters.docx_export import export_docx
from exporters.xlsx_export import export_xlsx
from exporters.pptx_export import export_pptx
from exporters.pdf_export import export_pdf


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main():
    parser = argparse.ArgumentParser(description="Run the FMCG Deal Intelligence Agent pipeline")
    parser.add_argument("--max-items", type=int, default=25, help="Max items fetched per RSS feed (5-60 recommended)")
    parser.add_argument("--relevance-threshold", type=float, default=0.35)
    parser.add_argument("--semantic-dedup", action="store_true", help="Use sentence-transformers for dedup if installed")
    parser.add_argument("--date-mode", type=str, default="all", choices=list(DATE_MODES.keys()),
                         help="today | last_30_days | ytd | custom | all")
    parser.add_argument("--from-date", type=str, default=None, help="YYYY-MM-DD (required if --date-mode custom)")
    parser.add_argument("--to-date", type=str, default=None, help="YYYY-MM-DD (defaults to today if --date-mode custom)")
    parser.add_argument("--out-dir", type=str, default="data/output")
    args = parser.parse_args()

    groq_key = get_groq_api_key()
    print(f"GROQ_API_KEY configured (backend): {bool(groq_key)}")

    custom_from = _parse_date(args.from_date) if args.from_date else None
    custom_to = _parse_date(args.to_date) if args.to_date else None

    state = run_linear(
        groq_api_key=groq_key,
        use_semantic_dedup=args.semantic_dedup,
        relevance_threshold=args.relevance_threshold,
        max_items_per_feed=args.max_items,
        date_mode=args.date_mode,
        custom_from=custom_from,
        custom_to=custom_to,
    )

    for line in state.get("agent_log", []):
        print(line)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    newsletter = state.get("newsletter_structured", {})
    date_range = state.get("date_filter_range", {})
    date_label = f"{date_range.get('from', 'earliest')} to {date_range.get('to', 'now')}" if args.date_mode != "all" else "All time"

    json_path = export_json(state, str(out_dir / "raw_data.json"))
    csv_path = export_csv(state, str(out_dir / "deals.csv"))
    docx_path = export_docx(newsletter, str(out_dir / "newsletter.docx"))
    xlsx_path = export_xlsx(newsletter, str(out_dir / "newsletter.xlsx"))
    pptx_path = export_pptx(newsletter, str(out_dir / "newsletter.pptx"))
    pdf_path = export_pdf(newsletter, str(out_dir / "newsletter.pdf"), date_filter_label=date_label)

    md_path = out_dir / "newsletter.md"
    md_path.write_text(state.get("newsletter_markdown", ""), encoding="utf-8")

    print("\n=== Deliverables written ===")
    for p in [json_path, csv_path, docx_path, xlsx_path, pptx_path, pdf_path, str(md_path)]:
        print(f" - {p}")

    print("\n=== Newsletter Preview ===\n")
    print(state.get("newsletter_markdown", ""))


if __name__ == "__main__":
    main()
