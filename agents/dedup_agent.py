"""
agents/dedup_agent.py
-----------------------
Deduplication Agent — two layers:

1. EXACT dedup: same URL, or same normalized title (many outlets republish
   wire-service stories verbatim, and Google News RSS often returns the
   same story from multiple mirrors).

2. NEAR-duplicate dedup: different outlets covering the same underlying
   deal with different wording ("HUL acquires D2C brand" vs "Hindustan
   Unilever buys stake in D2C startup"). We use TF-IDF + cosine similarity
   over the cleaned text, which is lightweight, deterministic, and needs no
   model download — good for a demo/serverless environment.

   If `sentence-transformers` is installed, we optionally upgrade to
   semantic embeddings for better recall on paraphrased headlines (toggle
   via `use_semantic=True`). This mirrors the "Embedding Agent" in the
   original architecture, but folded into dedup rather than kept as a
   separate always-on agent — fewer moving parts for the same result.
"""

from __future__ import annotations
import re
from typing import List, Optional

from agents.state import PipelineState, Article, log

NEAR_DUP_THRESHOLD = 0.72       # cosine similarity threshold for TF-IDF
SEMANTIC_DUP_THRESHOLD = 0.80   # threshold if semantic embeddings are used
DIFFLIB_DUP_THRESHOLD = 0.70    # threshold for the pure-stdlib fallback (no numpy/sklearn)


def _normalize_title(title: str) -> str:
    t = title.lower().strip()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t


def _exact_dedup(articles: List[Article]) -> List[Article]:
    seen_links = set()
    seen_titles = set()
    unique: List[Article] = []
    for a in articles:
        link = a.get("link", "")
        norm_title = _normalize_title(a.get("title", ""))
        if link in seen_links or norm_title in seen_titles:
            continue
        seen_links.add(link)
        seen_titles.add(norm_title)
        unique.append(a)
    return unique


def _try_semantic_embeddings(texts: List[str]):
    """Best-effort: use sentence-transformers if available, else None."""
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return np.array(embeddings)
    except Exception:
        return None


def _try_tfidf_similarity(texts: List[str]):
    """Best-effort: use scikit-learn TF-IDF if available, else None.
    (Deliberately optional — scikit-learn/numpy add ~40MB+, which is fine
    for Streamlit Cloud/local but can push a Vercel serverless function
    bundle past its size limit. See requirements-vercel.txt.)"""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
        matrix = vectorizer.fit_transform(texts).toarray()
        return cosine_similarity(matrix)
    except Exception:
        return None


def _difflib_similarity_matrix(texts: List[str]):
    """Pure Python standard-library fallback — zero extra dependencies.
    O(n^2) string comparison; fine for the article counts this pipeline
    deals with per run (tens to low hundreds)."""
    import difflib
    n = len(texts)
    sim = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            ratio = difflib.SequenceMatcher(None, texts[i], texts[j]).ratio()
            sim[i][j] = ratio
            sim[j][i] = ratio
    return sim


def _near_dedup(articles: List[Article], use_semantic: bool = False) -> List[Article]:
    if len(articles) <= 1:
        for a in articles:
            a["is_duplicate"] = False
            a["duplicate_of"] = None
        return articles, "n/a (fewer than 2 articles)"

    texts = [a.get("cleaned_text", "") or a.get("title", "") for a in articles]

    sim_matrix = None
    threshold = DIFFLIB_DUP_THRESHOLD
    method = "difflib (stdlib fallback)"

    if use_semantic:
        embeddings = _try_semantic_embeddings(texts)
        if embeddings is not None:
            from sklearn.metrics.pairwise import cosine_similarity as _cs  # sentence-transformers implies sklearn present
            sim_matrix = _cs(embeddings)
            threshold = SEMANTIC_DUP_THRESHOLD
            method = "semantic embeddings"

    if sim_matrix is None:
        tfidf_sim = _try_tfidf_similarity(texts)
        if tfidf_sim is not None:
            sim_matrix = tfidf_sim
            threshold = NEAR_DUP_THRESHOLD
            method = "TF-IDF cosine"

    if sim_matrix is None:
        sim_matrix = _difflib_similarity_matrix(texts)
        threshold = DIFFLIB_DUP_THRESHOLD
        method = "difflib (stdlib fallback)"

    n = len(articles)
    is_dup = [False] * n
    dup_of = [None] * n

    # Keep the article from the most credible-looking / earliest source,
    # mark later, more-similar ones as duplicates of it.
    for i in range(n):
        if is_dup[i]:
            continue
        for j in range(i + 1, n):
            if is_dup[j]:
                continue
            if sim_matrix[i][j] >= threshold:
                is_dup[j] = True
                dup_of[j] = articles[i]["id"]

    for idx, a in enumerate(articles):
        a["is_duplicate"] = is_dup[idx]
        a["duplicate_of"] = dup_of[idx]

    return articles, method


def run(state: PipelineState, use_semantic: bool = False) -> PipelineState:
    cleaned = state.get("cleaned_articles", [])
    exact_unique = _exact_dedup(cleaned)
    scored, method = _near_dedup(exact_unique, use_semantic=use_semantic)
    final = [a for a in scored if not a.get("is_duplicate")]

    state["deduped_articles"] = final
    log(
        state,
        f"Deduplication Agent: {len(cleaned)} -> {len(exact_unique)} after exact dedup "
        f"-> {len(final)} after near-duplicate removal (method: {method})",
    )
    return state
