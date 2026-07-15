"""
utils/backend_config.py
-------------------------
Backend-only secret loading. The Groq API key is NEVER entered through any
UI textbox — it must be configured as:
  - a local `.env` file (loaded via python-dotenv) for CLI/local runs,
  - a Streamlit Cloud "Secret" (st.secrets) for the Streamlit deployment,
  - a Vercel Environment Variable for the Vercel/FastAPI deployment.

This keeps the key out of browser devtools, screenshots, and shared demo
links — standard practice for any deployed app.
"""

from __future__ import annotations
import os
from typing import Optional


def get_groq_api_key() -> Optional[str]:
    # 1. Plain environment variable (works for CLI, Vercel, Render, etc.)
    key = os.environ.get("GROQ_API_KEY")
    if key:
        return key

    # 2. Streamlit secrets.toml (Streamlit Cloud "Secrets" panel)
    try:
        import streamlit as st
        if "GROQ_API_KEY" in st.secrets:
            return st.secrets["GROQ_API_KEY"]
    except Exception:
        pass

    return None


def get_groq_model() -> str:
    return os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
