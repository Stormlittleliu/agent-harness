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


def test_latency_breakdown_model_tool_and_other():
    events = [
        _event("run-a", "model_start", "2026-01-01T00:00:00.000",
               run_id="m1", model="deepseek-flash"),
        _event("run-a", "model_end", "2026-01-01T00:00:00.500",
               run_id="m1", model="deepseek-flash", latency_ms=500,
               prompt_tokens=10, completion_tokens=5, total_tokens=15),
        _event("run-a", "tool_start", "2026-01-01T00:00:00.600",
               run_id="t1", tool="read_file"),
        _event("run-a", "tool_end", "2026-01-01T00:00:01.000",
               run_id="t1", tool="read_file", latency_ms=400, status="success"),
        _event("run-a", "run_end", "2026-01-01T00:00:02.000",
               status="completed", duration_ms=2000,
               model_calls=1, tool_calls=1, total_tokens=15),
    ]
    run = group_runs(events, pricing=PRICING)[0]
    breakdown = run["latency_breakdown"]
    assert breakdown["model_ms"] == pytest.approx(500)
    assert breakdown["tool_ms"] == pytest.approx(400)
    assert breakdown["overlap_ms"] == pytest.approx(0)
    assert breakdown["other_ms"] == pytest.approx(1100)
    assert run["model_latency"]["deepseek-flash"] == pytest.approx(500)
    assert run["tool_latency"]["read_file"] == pytest.approx(400)

    summary = summarize([run])
    assert summary["latency_breakdown"]["model_pct"] == pytest.approx(0.25)
    assert summary["latency_breakdown"]["tool_pct"] == pytest.approx(0.2)
    assert summary["by_tool_latency"]["read_file"]["calls"] == 1


def test_model_error_run_uses_model_start_name_and_breakdown():
    events = [
        _event("run-e", "model_start", "2026-01-01T00:00:00.000",
               run_id="m1", model="deepseek-chat"),
        _event("run-e", "model_error", "2026-01-01T00:00:01.000",
               run_id="m1", error="Connection error."),
        _event("run-e", "model_start", "2026-01-01T00:00:02.000",
               run_id="m2", model="deepseek-chat"),
        _event("run-e", "model_error", "2026-01-01T00:00:03.000",
               run_id="m2", error="Connection error."),
        _event("run-e", "run_end", "2026-01-01T00:00:03.500",
               status="completed", duration_ms=3500,
               model_calls=2, tool_calls=0, total_tokens=0),
    ]
    run = group_runs(events, pricing=PRICING)[0]
    assert run["model"] == "deepseek-chat"
    assert run["model_calls"] == 2
    assert run["has_errors"] is True
    assert run["latency_breakdown"]["model_ms"] == pytest.approx(2000)
    assert run["latency_breakdown"]["other_ms"] == pytest.approx(1500)

    summary = summarize([run])
    assert summary["by_model"].get("unknown") is None
    assert summary["by_model"]["deepseek-chat"]["runs"] == 1
    assert summary["model_error_runs"] == 1


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
