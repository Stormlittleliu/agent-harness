# -*- coding: utf-8 -*-
"""trace JSONL → Span 的配对与容错。"""
import json

from core.quality.trace_spans import load_trace_spans


def _write(path, rows):
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_load_trace_spans_pairs_start_end(tmp_path):
    _write(
        tmp_path / "trace_20260101.jsonl",
        [
            {"trace_id": "t1", "event": "tool_start", "run_id": "r1",
             "tool": "search", "node": "retrieve", "input": "q"},
            {"trace_id": "t1", "event": "tool_end", "run_id": "r1",
             "status": "success", "latency_ms": 12, "node": "retrieve"},
            {"trace_id": "t1", "event": "model_start", "run_id": "r2",
             "model": "deepseek", "node": "answer"},
            {"trace_id": "t1", "event": "model_error", "run_id": "r2",
             "error": "timeout", "latency_ms": 30000, "node": "answer"},
            {"trace_id": "other", "event": "tool_start", "run_id": "r3",
             "tool": "ignored", "node": "x"},
        ],
    )

    spans = load_trace_spans("t1", trace_dir=tmp_path)
    by_id = {span.span_id: span for span in spans}
    assert set(by_id) == {"r1", "r2"}

    tool = by_id["r1"]
    assert tool.kind == "tool"
    assert tool.name == "search"
    assert tool.status == "ok"
    assert tool.latency_ms == 12
    assert tool.metadata["node"] == "retrieve"
    assert tool.args_digest

    model = by_id["r2"]
    assert model.kind == "model"
    assert model.status == "error"
    assert "timeout" in model.metadata["error"]


def test_load_trace_spans_returns_empty_for_unknown(tmp_path):
    assert load_trace_spans("missing", trace_dir=tmp_path) == []
    assert load_trace_spans(None, trace_dir=tmp_path) == []
