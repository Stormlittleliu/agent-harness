# -*- coding: utf-8 -*-
"""质量页「范式」视图：空状态、列表与采纳动作的可用性。"""
import json
import os
from pathlib import Path

from streamlit.testing.v1 import AppTest

from core.interfaces.console import routes
from core.interfaces.dashboard import patterns as patterns_view

ROOT = Path(__file__).resolve().parents[1]


def _app(state: dict | None = None) -> AppTest:
    app = AppTest.from_file(str(ROOT / "app_agent.py"), default_timeout=300)
    app.session_state["console:route"] = routes.Route("quality")
    for key, value in (state or {}).items():
        app.session_state[key] = value
    app.run()
    return app


def _group(app: AppTest, key: str):
    return next(group for group in app.button_group if group.key == key)


def _payload() -> dict:
    return {
        "mining_id": "mine-test",
        "created_at": "2026-11-04T20:00:00",
        "line_count": 4,
        "baseline": {"demo": 0.75},
        "patterns": [
            {
                "pattern_id": "pat-1",
                "name": "retrieve → llm_answer",
                "kind": "sequence",
                "scope": {"scenario": "demo"},
                "steps": ["retrieve", "llm_answer"],
                "support": 3,
                "total": 4,
                "success_rate": 1.0,
                "baseline": 0.75,
                "lift": 0.25,
                "cost": {"avg_tokens": 120, "avg_latency_ms": 900},
                "evidence": ["run-a:1", "run-a:2"],
                "counterexamples": ["run-b:1"],
                "status": "candidate",
            }
        ],
    }


def _open_patterns(app: AppTest) -> AppTest:
    _group(app, "quality:group").set_value(["看资产"])
    app.run()
    _group(app, "quality:view").set_value(["范式"])
    app.run()
    return app


def test_patterns_view_renders_candidate(tmp_path, monkeypatch):
    (tmp_path / "mine-test").mkdir()
    (tmp_path / "mine-test" / "patterns.json").write_text(
        json.dumps(_payload(), ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(patterns_view, "PATTERN_ROOT", tmp_path)
    monkeypatch.setattr(patterns_view, "SHADOW_ROOT", tmp_path / "shadow")

    app = _open_patterns(_app())
    assert not app.exception, [item.value for item in app.exception]
    assert any("retrieve" in str(markdown.value) for markdown in app.markdown)
    labels = [button.label for button in app.button]
    assert "编译成候选" in labels
    assert "试运行 shadow" in labels
    assert "采纳" in labels
    assert "回退" in labels
    assert "拒绝这条范式" in labels

    adopt = next(button for button in app.button if button.label == "采纳")
    assert adopt.disabled  # 没有 shadow 证据时不可采纳


def test_patterns_view_empty_state(tmp_path, monkeypatch):
    monkeypatch.setattr(patterns_view, "PATTERN_ROOT", tmp_path / "missing")
    monkeypatch.setattr(patterns_view, "SHADOW_ROOT", tmp_path / "shadow")
    app = _open_patterns(_app())
    assert not app.exception, [item.value for item in app.exception]
    assert any("还没有范式" in str(info.value) for info in app.info)


def test_latest_patterns_picks_newest(tmp_path):
    for name in ("old", "new"):
        directory = tmp_path / name
        directory.mkdir()
        (directory / "patterns.json").write_text(
            json.dumps({**_payload(), "mining_id": name}), encoding="utf-8"
        )
    os.utime(tmp_path / "old" / "patterns.json", (1000, 1000))
    payload, path = patterns_view.latest_patterns(tmp_path)
    assert payload is not None
    assert path is not None
    assert payload["mining_id"] == "new"
