# -*- coding: utf-8 -*-
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_starts_without_exception():
    app = AppTest.from_file(str(ROOT / "app_agent.py"), default_timeout=120)
    app.run()
    assert not app.exception, [item.value for item in app.exception]
    assert len(app.tabs) >= 7
