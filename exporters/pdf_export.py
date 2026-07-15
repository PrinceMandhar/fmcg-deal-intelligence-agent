"""
exporters/pdf_export.py
--------------------------
PDF newsletter exporter using reportlab — pure Python, no system-level
dependencies (unlike WeasyPrint/wkhtmltopdf), so it works reliably on
serverless platforms like Vercel as well as Streamlit Cloud/local.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)
from reportlab.lib.enums import TA_CENTER

NAVY = colors.HexColor("#1F4E78")
LIGHT_GREY = colors.HexColor("#F0F2F6")


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="NewsletterTitle", parent=styles["Title"], textColor=NAVY,
        fontSize=22, alignment=TA_CENTER, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="Meta", parent=styles["Normal"], alignment=TA_CENTER,
        textColor=colors.grey, fontSize=9, spaceAfter=14,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading", parent=styles["Heading2"], textColor=NAVY,
        spaceBefore=14, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="DealTitle", parent=styles["Normal"], fontSize=10.5,
        fontName="Helvetica-Bold", spaceAfter=1,
    ))
    styles.add(ParagraphStyle(
        name="DealMeta", parent=styles["Normal"], fontSize=8.5,
        textColor=colors.grey, spaceAfter=8,
    ))
    return styles


def _build_story(newsletter: Dict[str, Any], styles, date_filter_label: str = "") -> list:
    story = []

    story.append(Paragraph("FMCG Deal Intelligence Newsletter", styles["NewsletterTitle"]))
    meta_line = f"Generated {newsletter.get('generated_at', '')}"
    if date_filter_label:
        meta_line += f" &nbsp;·&nbsp; Coverage window: {date_filter_label}"
    story.append(Paragraph(meta_line, styles["Meta"]))
    story.append(HRFlowable(width="100%", color=NAVY, thickness=1))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Executive Summary", styles["SectionHeading"]))
    story.append(Paragraph(newsletter.get("executive_summary", ""), styles["Normal"]))

    story.append(Paragraph("Top Deals", styles["SectionHeading"]))
    deals = newsletter.get("deals", [])
    if not deals:
        story.append(Paragraph("No deals met the relevance threshold in this run.", styles["Normal"]))
    else:
        for d in deals:
            story.append(Paragraph(d.get("title", "")[:140], styles["DealTitle"]))
            deal_type = d.get("deal_type", "").replace("_", " ").title()
            amount = d.get("amount") or "—"
            line = f"{deal_type}" + (f" · {amount}" if amount != "—" else "")
            line += f" &nbsp;|&nbsp; {d.get('published', 'Date unknown')}"
            line += f" &nbsp;|&nbsp; Source: {d.get('source', '')} ({d.get('credibility_label', '')})"
            story.append(Paragraph(line, styles["DealMeta"]))

    story.append(Paragraph("Market Trend Snapshot", styles["SectionHeading"]))
    trend = newsletter.get("trend_snapshot", {})
    if trend:
        table_data = [["Deal Type", "Count"]]
        for dtype, count in sorted(trend.items(), key=lambda x: -x[1]):
            table_data.append([dtype.replace("_", " ").title(), str(count)])
        t = Table(table_data, colWidths=[10 * cm, 4 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GREY]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No trend data available.", styles["Normal"]))

    story.append(Paragraph("Methodology & Assumptions", styles["SectionHeading"]))
    for line in [
        "Sources: free public RSS feeds (Google News, Reuters, ET, Mint, Business Standard, CNBC, Financial Express, Yahoo Finance).",
        "Relevance: rule-based keyword scoring (FMCG company + deal-action co-occurrence).",
        "Credibility: static publisher-tier table — a proxy for editorial track record, not a fact-check of the specific claim.",
        "Deduplication: exact URL/title match, then similarity scoring on cleaned article text.",
    ]:
        story.append(Paragraph(f"• {line}", styles["Normal"]))

    return story


def export_pdf(newsletter: Dict[str, Any], out_path: str, date_filter_label: str = "") -> str:
    """File-based export — used by run_pipeline.py and streamlit_app.py."""
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()
    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
    )
    doc.build(_build_story(newsletter, styles, date_filter_label))
    return out_path


def export_pdf_bytes(newsletter: Dict[str, Any], date_filter_label: str = "") -> bytes:
    """In-memory export — used by the stateless Vercel API (api/index.py),
    which cannot rely on a persistent filesystem between requests."""
    import io
    buffer = io.BytesIO()
    styles = _styles()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
    )
    doc.build(_build_story(newsletter, styles, date_filter_label))
    return buffer.getvalue()
