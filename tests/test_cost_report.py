# -*- coding: utf-8 -*-
from pathlib import Path

import pytest

from core.observability.cost_report import (
    build_report,
    estimate_cost,
    group_runs,
    percentile,
    summarize,
    write_markdown,
)

PRICING = {"deepseek-flash": {"input_per_1m": 2.0, "output_per_1m": 8.0}}


def _event(trace_id, event, ts, **fields):
    return {"trace_id": trace_id, "event": event, "ts": ts, **fields}


def _run(trace_id, duration, status, prompt=100, completion=50, model="deepseek-flash"):
    return [
        _event(trace_id, "model_end", "2026-01-01T00:00:00.000", model=model,
               prompt_tokens=prompt, completion_tokens=completion,
               total_tokens=prompt + completion),
        _event(trace_id, "tool_end", "2026-01-01T00:00:01.000", tool="read_file"),
        _event(trace_id, "run_end", "2026-01-01T00:00:02.000", status=status,
               duration_ms=duration, prompt_tokens=prompt, completion_tokens=completion,
               total_tokens=prompt + completion),
    ]


def test_percentile_interpolates():
    assert percentile([1, 2, 3, 4], 0.5) == 2.5
    assert percentile([1, 2, 3, 4], 0.95) == pytest.approx(3.85)
    assert percentile([], 0.5) is None


def test_estimate_cost_uses_deepseek_fallback():
    assert estimate_cost("deepseek-flash", 1_000_000, 0, PRICING) == 2.0
    assert estimate_cost("custom-model", 1_000_000, 0, PRICING) == 0.0


def test_group_runs_and_summary():
    events = (
        _run("run-a", 1000, "completed")
        + _run("run-b", 3000, "completed", prompt=200, completion=100)
        + _run("run-c", 500, "error")
    )
    runs = group_runs(events, pricing=PRICING)
    assert len(runs) == 3
    summary = summarize(runs)
    assert summary["runs"] == 3
    assert summary["completed"] == 2
    assert summary["failed"] == 1
    assert summary["success_rate"] == 0.6667
    assert summary["cost_est"] > 0
    assert summary["by_model"]["deepseek-flash"]["runs"] == 3
    assert summary["by_tool"]["read_file"] == 3


def test_build_report_and_markdown(tmp_path: Path):
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    lines = []
    for event in _run("run-a", 1000, "completed"):
        lines.append(__import__("json").dumps(event, ensure_ascii=False))
    (trace_dir / "trace_20260101.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = build_report(trace_dir, pricing=PRICING)
    out = tmp_path / "report.md"
    write_markdown(out, report)
    text = out.read_text(encoding="utf-8")
    assert "Agent 成本 / 时延报告" in text
    assert "run-a" in text
    assert "¥" in text
