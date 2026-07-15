"""
streamlit_app.py
-------------------
Demo app for the FMCG Deal Intelligence Multi-Agent System.

IMPORTANT: The Groq API key is backend-only. It is loaded from Streamlit
Secrets (or an environment variable) — there is deliberately NO textbox in
this UI to enter it. See utils/backend_config.py.

Deploy free on Streamlit Community Cloud:
  1. Push this repo to GitHub.
  2. Go to https://share.streamlit.io -> New app -> pick this repo ->
     main file: streamlit_app.py.
  3. In "Secrets", add: GROQ_API_KEY = "gsk_xxx"
  4. Deploy.
"""

from __future__ import annotations
import sys
from pathlib import Path
from datetime import date, datetime

sys.path.insert(0, str(Path(__file__).parent))
Path("data/output").mkdir(parents=True, exist_ok=True)

# Load .env for local runs (Streamlit Cloud uses st.secrets instead — see
# utils/backend_config.py, which checks both). Harmless no-op if no .env
# file exists (e.g. on Streamlit Cloud).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import streamlit as st
import pandas as pd

from agents.state import new_state
from agents import (
    news_agent, cleaning_agent, date_filter_agent, dedup_agent,
    relevance_agent, credibility_agent, extraction_agent, newsletter_agent,
)
from utils.backend_config import get_groq_api_key
from utils.date_utils import DATE_MODES
from exporters.data_export import export_json, export_csv
from exporters.docx_export import export_docx
from exporters.xlsx_export import export_xlsx
from exporters.pptx_export import export_pptx
from exporters.pdf_export import export_pdf

st.set_page_config(page_title="FMCG Deal Intelligence Agent", page_icon="📰", layout="wide")

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .main .block-container {padding-top: 2rem; max-width: 1200px;}
    .hero-banner {
        background: linear-gradient(120deg, #1F4E78 0%, #2E6DA4 100%);
        padding: 28px 32px; border-radius: 14px; color: white; margin-bottom: 20px;
    }
    .hero-banner h1 {margin: 0; font-size: 1.7rem;}
    .hero-banner p {margin: 6px 0 0 0; opacity: 0.9; font-size: 0.95rem;}
    .deal-card {
        border: 1px solid #E5E7EB; border-radius: 10px; padding: 14px 18px;
        margin-bottom: 10px; background: #FAFBFC;
    }
    .deal-card h4 {margin: 0 0 6px 0; font-size: 1rem; color: #1F2937;}
    .deal-meta {font-size: 0.82rem; color: #6B7280;}
    .badge {
        display: inline-block; padding: 2px 10px; border-radius: 999px;
        font-size: 0.72rem; font-weight: 600; margin-right: 6px;
    }
    .badge-high {background: #DCFCE7; color: #166534;}
    .badge-med {background: #FEF9C3; color: #854D0E;}
    .badge-low {background: #FEE2E2; color: #991B1B;}
    .key-status {
        display: inline-block; padding: 4px 12px; border-radius: 8px;
        font-size: 0.82rem; font-weight: 600;
    }
    .key-on {background: #DCFCE7; color: #166534;}
    .key-off {background: #F3F4F6; color: #4B5563;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero-banner">
  <h1>📰 FMCG Deal Intelligence — Multi-Agent Newsletter System</h1>
  <p>Supervisor → News Discovery → Cleaning → Date Filter → Deduplication → Relevance →
  Credibility → Deal Extraction → Newsletter, running live on public RSS feeds.</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
GROQ_KEY = get_groq_api_key()  # backend-only, never entered via UI

with st.sidebar:
    st.header("⚙️ Run Settings")

    st.markdown("**📅 News Date Filter**")
    date_mode_label_to_key = {v: k for k, v in DATE_MODES.items()}
    date_mode_choice = st.selectbox(
        "Show news from",
        options=list(DATE_MODES.values()),
        index=list(DATE_MODES.keys()).index("all"),
    )
    date_mode = date_mode_label_to_key[date_mode_choice]

    custom_from, custom_to = None, None
    if date_mode == "custom":
        c1, c2 = st.columns(2)
        custom_from = c1.date_input("From", value=date.today().replace(day=1))
        custom_to = c2.date_input("Till", value=date.today())

    st.divider()
    max_items = st.slider("Max articles per RSS feed", min_value=5, max_value=60, value=25,
                           help="Threshold for how many articles to pull per source before filtering.")
    threshold = st.slider("Relevance threshold", 0.0, 1.0, 0.35, 0.05)
    semantic = st.checkbox("Use semantic (embedding) dedup", value=False,
                            help="Requires sentence-transformers; slower but catches paraphrased duplicates. Falls back automatically if not installed.")

    st.divider()
    st.markdown("**🔑 LLM Extraction (Groq)**")
    if GROQ_KEY:
        st.markdown('<span class="key-status key-on">● Groq LLM: Active (backend key configured)</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="key-status key-off">○ Groq LLM: Off (rule-based fallback in use)</span>', unsafe_allow_html=True)
    st.caption("The key is configured server-side (Streamlit Secrets / environment variable) — it is never entered here, for security.")

    st.divider()
    run_btn = st.button("🚀 Run Pipeline", type="primary", use_container_width=True)

if "state" not in st.session_state:
    st.session_state.state = None

# ---------------------------------------------------------------------------
# Run pipeline
# ---------------------------------------------------------------------------
if run_btn:
    progress = st.progress(0, text="Starting Supervisor Agent...")
    log_box = st.empty()

    state = new_state("FMCG M&A and investment activity")
    stages = [
        ("News Discovery Agent", lambda s: news_agent.run(s, max_items_per_feed=max_items)),
        ("Cleaning Agent", cleaning_agent.run),
        ("Date Filter Agent", lambda s: date_filter_agent.run(s, mode=date_mode, custom_from=custom_from, custom_to=custom_to)),
        ("Deduplication Agent", lambda s: dedup_agent.run(s, use_semantic=semantic)),
        ("Relevance Agent", lambda s: relevance_agent.run(s, threshold=threshold)),
        ("Credibility Agent", credibility_agent.run),
        ("Deal Extraction Agent", lambda s: extraction_agent.run(s, groq_api_key=GROQ_KEY)),
        ("Newsletter Agent", lambda s: newsletter_agent.run(s, groq_api_key=GROQ_KEY)),
    ]
    for i, (name, fn) in enumerate(stages):
        progress.progress(int((i / len(stages)) * 100), text=f"Running {name}...")
        state = fn(state)
        log_box.code("\n".join(state.get("agent_log", [])), language="text")
    progress.progress(100, text="Done!")

    st.session_state.state = state

state = st.session_state.state

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
def _credibility_badge(label: str) -> str:
    if "High" in label and "Medium" not in label:
        return f'<span class="badge badge-high">{label}</span>'
    if "Low" in label:
        return f'<span class="badge badge-low">{label}</span>'
    return f'<span class="badge badge-med">{label}</span>'


if state:
    n_deals = len(state.get("extracted_deals", []))
    date_range = state.get("date_filter_range", {})
    coverage = "All time" if date_mode == "all" else f"{date_range.get('from', '—')[:10]} → {date_range.get('to', '—')[:10]}"
    st.success(f"Pipeline complete — **{n_deals} deals** found · Coverage window: **{coverage}**")

    tab1, tab2, tab3, tab4 = st.tabs(["📰 Newsletter", "📊 Deal Table", "🧾 Pipeline Data", "⬇️ Exports"])

    with tab1:
        newsletter = state.get("newsletter_structured", {})
        st.markdown(f"### Executive Summary")
        st.write(newsletter.get("executive_summary", ""))
        st.markdown("### Top Deals")
        deals = newsletter.get("deals", [])
        if not deals:
            st.info("No deals passed the relevance threshold for this date range. Try widening the date filter or lowering the relevance threshold.")
        for d in deals:
            amount = f" · {d['amount']}" if d.get("amount") and d["amount"] != "—" else ""
            st.markdown(f"""
            <div class="deal-card">
              <h4>{d['title']}</h4>
              <div class="deal-meta">
                🗓️ {d.get('published', 'Date unknown')} &nbsp;|&nbsp;
                {d['deal_type'].replace('_',' ').title()}{amount} &nbsp;|&nbsp;
                Source: {d['source']} {_credibility_badge(d['credibility_label'])}
              </div>
            </div>
            """, unsafe_allow_html=True)

        if newsletter.get("trend_snapshot"):
            st.markdown("### Market Trend Snapshot")
            trend_df = pd.DataFrame(
                [{"Deal Type": k.replace("_", " ").title(), "Count": v} for k, v in newsletter["trend_snapshot"].items()]
            )
            st.bar_chart(trend_df.set_index("Deal Type"))

    with tab2:
        deals = state.get("newsletter_structured", {}).get("deals", [])
        if deals:
            df = pd.DataFrame(deals)
            cols_order = ["title", "published", "deal_type", "amount", "sector", "source", "credibility_label", "relevance_score", "link"]
            df = df[[c for c in cols_order if c in df.columns]]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No deals to show.")

    with tab3:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Raw articles", len(state.get("raw_articles", [])))
        c2.metric("After cleaning", len(state.get("cleaned_articles", [])))
        c3.metric("After date filter", len(state.get("cleaned_articles", [])))
        c4.metric("After dedup", len(state.get("deduped_articles", [])))
        c5.metric("Relevant deals", len(state.get("relevant_articles", [])))
        st.subheader("Agent Execution Log")
        st.code("\n".join(state.get("agent_log", [])), language="text")

    with tab4:
        out_dir = Path("data/output")
        out_dir.mkdir(parents=True, exist_ok=True)
        newsletter = state.get("newsletter_structured", {})

        json_path = export_json(state, str(out_dir / "raw_data.json"))
        csv_path = export_csv(state, str(out_dir / "deals.csv"))
        docx_path = export_docx(newsletter, str(out_dir / "newsletter.docx"))
        xlsx_path = export_xlsx(newsletter, str(out_dir / "newsletter.xlsx"))
        pptx_path = export_pptx(newsletter, str(out_dir / "newsletter.pptx"))
        pdf_path = export_pdf(newsletter, str(out_dir / "newsletter.pdf"), date_filter_label=coverage)

        st.markdown("Download the newsletter / raw data in your preferred format:")
        col1, col2, col3 = st.columns(3)
        col4, col5, col6 = st.columns(3)
        downloads = [
            (col1, pdf_path, "📄 newsletter.pdf", "application/pdf"),
            (col2, docx_path, "📝 newsletter.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            (col3, xlsx_path, "📊 newsletter.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            (col4, pptx_path, "🖥️ newsletter.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
            (col5, csv_path, "🧾 deals.csv", "text/csv"),
            (col6, json_path, "🗂️ raw_data.json", "application/json"),
        ]
        for col, path, label, mime in downloads:
            with open(path, "rb") as f:
                col.download_button(label, f, file_name=Path(path).name, mime=mime, use_container_width=True)
else:
    st.info("👈 Set your date range and options in the sidebar, then click **Run Pipeline** to fetch live FMCG deal news and generate a newsletter.")
    with st.expander("How this works"):
        st.markdown("""
        1. **News Discovery Agent** pulls the latest headlines from ~9 free RSS feeds (Google News, Reuters, Economic Times, Mint, etc.)
        2. **Cleaning Agent** strips HTML and boilerplate.
        3. **Date Filter Agent** keeps only articles published in your chosen window (Today / Last 30 Days / Year-to-Date / Custom Range).
        4. **Deduplication Agent** removes exact and near-duplicate stories.
        5. **Relevance Agent** keeps only FMCG-deal-relevant articles (transparent keyword scoring).
        6. **Credibility Agent** scores each source's editorial track record.
        7. **Deal Extraction Agent** pulls structured fields (acquirer, target, amount...) via Groq LLM (or rule-based fallback).
        8. **Newsletter Agent** assembles everything into a skimmable newsletter — with every deal's publish date shown.
        """)
