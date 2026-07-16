# 📰 FMCG Deal Intelligence — Multi-Agent Newsletter System

An agentic pipeline that watches public news for **FMCG M&A and investment
activity**, cleans and deduplicates it, filters by date range, filters for
relevance, scores source credibility, extracts structured deal fields, and
publishes a short, skimmable newsletter — as CSV, JSON, PDF, Word, Excel,
and PowerPoint — with **two live demo options: Streamlit and Vercel**.

**Streamlit demo:** https://fmcg-deal-intelligence-agent.streamlit.app/


---

## 1. What's new in this version

| Feature | Details |
|---|---|
| 📅 **News date filter** | Today / Last 30 Days / Year-to-Date (Jan → today) / Custom From–Till range |
| 🗓️ **Publish date on every article** | Shown in the UI, the newsletter, and every export format |
| 📄 **PDF export** | Downloadable, formatted PDF newsletter (in addition to DOCX/XLSX/PPTX/CSV/JSON) |
| 🔑 **Backend-only Groq key** | No textbox anywhere — key lives in Streamlit Secrets / a Vercel Environment Variable only |
| 🎚️ **Wider article threshold** | Max-articles-per-feed slider now runs 5–60 |
| 🌐 **Vercel deployment** | A lightweight FastAPI + static HTML frontend, deployable directly on Vercel |
| 🎨 **Improved UI** | Card-based deal layout, credibility badges, trend chart, cleaner styling on both frontends |

---

## 2. Why this architecture

The pipeline is a **Supervisor-orchestrated multi-agent workflow** built on
[LangGraph](https://github.com/langchain-ai/langgraph). Each stage is an
independent agent with a single responsibility, reading from and writing
to one shared `PipelineState` dict — so the whole run is auditable
end-to-end.

```
User → Supervisor Agent (LangGraph)
         → News Discovery Agent   (9 free RSS feeds)
         → Cleaning Agent         (HTML strip, normalize)
         → Date Filter Agent      (Today / Last 30 Days / YTD / Custom)
         → Deduplication Agent    (exact + TF-IDF/semantic/difflib similarity)
         → Relevance Agent        (FMCG + deal keyword scoring)
         → Credibility Agent      (publisher-tier scoring)
         → Deal Extraction Agent  (Groq Llama 3.3 70B + regex fallback)
         → Newsletter Agent       (exec summary + deal table + trends, dated)
         → Export Agent           (CSV / JSON / PDF / DOCX / XLSX / PPTX)
```

Full diagram + design rationale: [`architecture/architecture.md`](architecture/architecture.md)

**Same Python core, two front-ends.** `agents/` and `exporters/` are
framework-agnostic — `streamlit_app.py` and `api/index.py` (Vercel) both
call the exact same pipeline code. Nothing is duplicated or reimplemented.

---

## 3. Quickstart (local)

```bash
git clone <your-repo-url>
cd fmcg-deal-intelligence-agent
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Optional: enables LLM-based extraction/summary. Free key: https://console.groq.com
cp .env.example .env   # then edit .env and add GROQ_API_KEY (backend-only, see section 5)

# Run the full pipeline once, writes everything to data/output/
python run_pipeline.py
python run_pipeline.py --date-mode last_30_days --max-items 30
python run_pipeline.py --date-mode custom --from-date 2026-01-01 --to-date 2026-07-15

# Or launch the interactive Streamlit demo
streamlit run streamlit_app.py
```

The pipeline **works with zero configuration** — no Groq key required.
Without a key, deal extraction and the executive summary fall back to
rule-based logic instead of the LLM.

---

## 4. What changes with vs. without a Groq API key

| | **Without key** (default) | **With key** |
|---|---|---|
| Deal extraction | Regex + keyword heuristics (`agents/extraction_agent.py::_heuristic_extract`) — picks up currency amounts and classifies deal type from keywords | Groq Llama 3.3 70B reads the article and returns structured `acquirer`, `target`, `deal_type`, `amount`, `currency`, `sector`, `country` as JSON — catches things regex can't (e.g. "the FMCG major" instead of a named company, implied deal types) |
| Executive summary | Template sentence built from counts (`agents/newsletter_agent.py::_template_summary`) — accurate but generic phrasing | A genuinely written 3-sentence summary in natural prose, referencing specific companies and deal types |
| Reliability | 100% deterministic, zero external calls, never fails | Depends on Groq API availability; automatically falls back to the non-LLM path if the call fails, times out, or the key is invalid — **the pipeline never breaks either way** |
| Cost | Free, always | Free tier on Groq is generous, but it's an external paid-capable service |

**Practical takeaway:** the key upgrades output *quality*, not the
pipeline's *correctness or completeness*. Every deliverable listed in the
problem statement (dedup, relevance, credibility, structured newsletter)
works fully either way.

---

## 5. Groq API key — backend-only, by design

The key is **never** entered through any UI textbox. Configure it as:

- **Local/CLI:** `.env` file (see `.env.example`), loaded via `python-dotenv`.
- **Streamlit Cloud:** App → Settings → Secrets:
  ```toml
  GROQ_API_KEY = "gsk_xxx"
  ```
- **Vercel:** Project → Settings → Environment Variables → add
  `GROQ_API_KEY` (mark it as a Production/Preview secret).

`utils/backend_config.py` centralizes this lookup (env var first, then Streamlit
secrets) so every agent gets the key the same way regardless of where it's
deployed. The sidebar/UI only ever shows a read-only status badge —
**Active** or **Off** — never the key itself.

---

## 6. Deployment

### Option A — Streamlit Community Cloud (full feature set, recommended primary demo)

1. Push this repo to GitHub.
2. [share.streamlit.io](https://share.streamlit.io) → **New app** → this repo → main file `streamlit_app.py`.
3. Add `GROQ_API_KEY` under **Secrets** (optional).
4. Deploy — full CSV/JSON/PDF/DOCX/XLSX/PPTX exports, TF-IDF/semantic dedup.

### Option B — Vercel (as requested)

1. Push this repo to GitHub.
2. [vercel.com/new](https://vercel.com/new) → import the repo.
3. Vercel auto-detects `vercel.json`, which builds:
   - `api/index.py` (FastAPI, using **`requirements-vercel.txt`**) as a serverless function
   - `public/index.html` as the static frontend
4. Project → Settings → Environment Variables → add `GROQ_API_KEY` (optional).
5. Deploy. Your frontend calls `/api/run`, `/api/pdf`, `/api/csv` on the same domain.

**Honest tradeoff, stated up front:** to fit Vercel's serverless function
size limit, the Vercel deployment uses `requirements-vercel.txt`, which
**excludes scikit-learn/numpy/pandas** (and therefore Streamlit, DOCX,
XLSX, PPTX generation too — those aren't included in the API). Practically:
- Deduplication on Vercel automatically uses the pure-stdlib `difflib`
  fallback in `agents/dedup_agent.py` instead of TF-IDF — same job, done
  with zero extra dependencies, verified in testing to correctly catch
  duplicate/near-duplicate stories.
- The Vercel API serves **CSV, JSON, and PDF** (the core "structured
  newsletter" deliverables). For DOCX/XLSX/PPTX, use the Streamlit
  deployment or run `python run_pipeline.py` locally — same underlying
  pipeline, just the fuller export set.

This is a deliberate engineering tradeoff (documented, not hidden) rather
than a limitation of the agent logic itself — every agent (ingestion,
cleaning, date filter, dedup, relevance, credibility, extraction,
newsletter) runs identically on both platforms.

### Scheduled runs (keep the newsletter always fresh)

`.github/workflows/scheduled_run.yml` runs the pipeline daily via GitHub
Actions and commits fresh outputs back to `data/output/` — free, no extra
infra.

---

## 7. Pipeline logic explained (as required by the brief)

### Date filtering
`agents/date_filter_agent.py` runs right after cleaning, before dedup —
no point scoring/extracting from articles outside the requested window.
Modes: `today`, `last_30_days`, `ytd` (Jan 1 → now), `custom` (explicit
from/to), `all` (no filter). Dates are parsed from each RSS entry's
structured `published_parsed` field first (most reliable), falling back to
`dateutil` string parsing, then to "Date unknown" — articles with an
unparseable date are **kept** rather than silently dropped, since losing a
genuinely relevant deal is worse than showing one extra "Date unknown" item.

### De-duplication
1. **Exact pass:** drop identical URLs and identical normalized titles.
2. **Near-duplicate pass:** similarity-score the remaining articles' text
   and drop anything above threshold, keeping the first-seen copy. Three
   tiers, auto-selected by what's installed:
   - `sentence-transformers` embeddings (opt-in, `use_semantic=True`) — threshold 0.80
   - TF-IDF + cosine similarity (default when scikit-learn is available) — threshold 0.72
   - Pure-stdlib `difflib.SequenceMatcher` (zero-dependency fallback, used automatically on Vercel) — threshold 0.70

### Relevance
Rule-based, fully transparent scorer (`agents/relevance_agent.py`):
`score = 0.40·(FMCG company mentioned) + 0.35·(deal keyword present) +
0.10·(sector hint present) + 0.15·(keyword density)`, halved if it lacks a
deal-action word. Default threshold: **0.35** (tunable in the UI/CLI).

### Credibility
A static, editable publisher-tier table (`config/sources.py`) maps each
article's resolved domain to a 0–1 score. **Explicit assumption:** this
scores *editorial track record*, not fact-verification of the specific
claim — the newsletter surfaces the label so readers calibrate trust
themselves.

### Deal extraction
Primary: Groq Llama 3.3 70B, strict JSON schema. Fallback: regex for
currency amounts + keyword-based `deal_type` classification. See section 4
for the full behavioral comparison.

---

## 8. Repo structure

```
fmcg-deal-intelligence-agent/
├── agents/
│   ├── state.py              # shared pipeline state schema
│   ├── news_agent.py          # Ingestion (with robust date parsing)
│   ├── cleaning_agent.py
│   ├── date_filter_agent.py   # NEW — date range filtering
│   ├── dedup_agent.py         # NEW — tiered fallback (semantic/TF-IDF/difflib)
│   ├── relevance_agent.py
│   ├── credibility_agent.py
│   ├── extraction_agent.py    # Groq LLM + fallback
│   ├── newsletter_agent.py    # now includes publish dates
│   └── supervisor.py          # LangGraph orchestration
├── exporters/
│   ├── data_export.py         # CSV + JSON (file + in-memory variants)
│   ├── docx_export.py
│   ├── xlsx_export.py
│   ├── pptx_export.py
│   └── pdf_export.py          # NEW — file + in-memory (Vercel) variants
├── utils/
│   ├── date_utils.py          # NEW — date range computation
│   └── backend_config.py       # NEW — backend-only Groq key loading
├── config/
│   ├── sources.py              # RSS feeds + credibility table
│   └── fmcg_keywords.py        # relevance taxonomy
├── api/
│   └── index.py                # NEW — FastAPI backend for Vercel
├── public/
│   └── index.html               # NEW — static frontend for Vercel
├── architecture/architecture.md
├── .github/workflows/scheduled_run.yml
├── run_pipeline.py             # CLI (full export set)
├── streamlit_app.py            # Streamlit demo (full export set)
├── vercel.json                 # NEW — Vercel build/route config
├── requirements.txt            # full deps (Streamlit/local)
├── requirements-vercel.txt     # NEW — lightweight deps (Vercel)
└── .env.example
```

---

## 9. Known limitations & next steps

- RSS-only ingestion (no paywalled scraping) — by design, for legal safety.
- Rule-based relevance/credibility are intentionally simple/explainable;
  swapping in an ML classifier is a drop-in change to `relevance_agent.py`.
- No persistent database yet (flat file export per run). Add Postgres/
  Supabase (see `architecture/architecture.md`) if cross-run historical
  querying becomes a requirement.
- Vercel API skips DOCX/XLSX/PPTX to control serverless bundle size (see
  section 6) — use the Streamlit deployment for those formats.
- LLM extraction quality depends on Groq model availability/pricing at
  request time — the heuristic fallback guarantees the pipeline never
  breaks even if Groq is down or unconfigured.

---

## 10. Alignment with the assignment brief

| Brief requirement | Where it's satisfied |
|---|---|
| Aggregate FMCG deal news, real-time sourcing | `news_agent.py` — 9 live RSS feeds, re-fetched every run |
| Remove duplicates/near-duplicates | `dedup_agent.py` — exact + near-dup, explained in §7 |
| Filter for FMCG-deal relevance | `relevance_agent.py`, transparent scoring, explained in §7 |
| Check basic source credibility | `credibility_agent.py`, transparent table, explained in §7 |
| Short structured newsletter | `newsletter_agent.py` → CSV/JSON/PDF/DOCX/XLSX/PPTX |
| Demo app (Vercel/Streamlit) | Both — §6 |
| GitHub + architecture diagram + README | This repo — `architecture/architecture.md` + this file |
| Raw data in CSV/JSON | `exporters/data_export.py` |
| Pipeline explanation (dedup + relevance logic) | §7 above |
