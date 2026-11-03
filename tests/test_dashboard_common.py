# -*- coding: utf-8 -*-
"""Dashboard 数据选择逻辑：优先完整报告，而不是最新的 smoke run。"""
import json
import os
import time

from core.interfaces.dashboard import common


def _write_report(path, total: int, passed: int) -> None:
    path.write_text(
        json.dumps(
            {
                "summary": {"total": total, "passed": passed},
                "results": [{"id": f"case-{index}", "passed": True} for index in range(total)],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_latest_agent_report_prefers_expected_total(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "AGENT_OUT", tmp_path)
    full = tmp_path / "agent_test_demo_20260101_000000.json"
    smoke = tmp_path / "agent_test_demo_20260102_000000.json"
    _write_report(full, 13, 10)
    _write_report(smoke, 1, 1)
    now = time.time()
    os.utime(full, (now - 100, now - 100))
    os.utime(smoke, (now, now))

    data, path = common.latest_agent_report("demo", expected_total=13)
    assert path == full
    assert data["summary"]["total"] == 13


def test_latest_agent_report_falls_back_to_largest_then_latest(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "AGENT_OUT", tmp_path)
    full = tmp_path / "agent_test_demo_20260101_000000.json"
    smoke = tmp_path / "agent_test_demo_20260102_000000.json"
    _write_report(full, 13, 10)
    _write_report(smoke, 1, 1)
    now = time.time()
    os.utime(full, (now - 100, now - 100))
    os.utime(smoke, (now, now))

    # 没有 5 条的报告时，退回结果条数最多的完整报告。
    data, path = common.latest_agent_report("demo", expected_total=5)
    assert path == full
    assert data["summary"]["total"] == 13

    # 不传 expected_total 时保持“最新一份”的语义。
    data, path = common.latest_agent_report("demo")
    assert path == smoke
    assert data["summary"]["total"] == 1
