# -*- coding: utf-8 -*-
"""独立启动的复核页（控制台里也有同一个视图：🧾 复核）。

    streamlit run app_review.py

逻辑在 ``core/interfaces/dashboard/review.py``，这里只是入口，避免两套 UI 漂移。
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.interfaces.dashboard.review import render_review  # noqa: E402

st.set_page_config(page_title="自建集人工复核", layout="wide")
render_review()
