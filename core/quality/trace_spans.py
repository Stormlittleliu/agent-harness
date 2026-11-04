# -*- coding: utf-8 -*-
"""把现有 trace JSONL 读成 ``Span`` 列表。

tracer 写入的是扁平的 ``model_start/model_end/tool_start/tool_end`` 事件；
这里按 ``run_id`` 配对，转成轨迹挖掘需要的 span。原始 trace 不动。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from core.quality.paths import TRACE_OUT
from core.quality.records import Span


def _iter_trace_events(trace_dir: Path) -> Iterable[dict[str, Any]]:
    for path in sorted(Path(trace_dir).glob("trace_*.jsonl")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                yield event


def _digest(value: Any) -> str | None:
    if value is None:
        return None
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def load_trace_spans(
    trace_id: str | None,
    *,
    trace_dir: Path | None = None,
) -> list[Span]:
    """读取一个 trace_id 的 span；找不到时返回空列表，不影响评测。"""
    if not trace_id:
        return []
    trace_dir = Path(trace_dir) if trace_dir is not None else TRACE_OUT
    spans: dict[str, Span] = {}

    for event in _iter_trace_events(trace_dir):
        if event.get("trace_id") != trace_id:
            continue
        kind = str(event.get("event") or "")
        run_id = str(event.get("run_id") or "")
        if not run_id:
            continue
        node = event.get("node")
        if kind in {"model_start", "tool_start"}:
            spans[run_id] = Span(
                span_id=run_id,
                name=str(event.get("tool") or event.get("model") or kind),
                kind="tool" if kind == "tool_start" else "model",
                status="running",
                parent_id=event.get("parent_run_id"),
                args_digest=_digest(event.get("input")),
                metadata={"node": node},
            )
            continue

        span = spans.get(run_id)
        if span is None:
            # 只有 end 没有 start（trace 被截断）也保留一条，便于发现异常。
            span = Span(
                span_id=run_id,
                name=str(event.get("tool") or event.get("model") or kind),
                kind="tool" if kind.startswith("tool") else "model",
                status="unknown",
                parent_id=event.get("parent_run_id"),
                metadata={"node": node, "orphan": True},
            )
            spans[run_id] = span

        if kind in {"model_end", "tool_end"}:
            span.status = "ok"
            span.latency_ms = event.get("latency_ms")
            span.tokens = event.get("total_tokens")
        elif kind in {"model_error", "tool_error"}:
            span.status = "error"
            span.latency_ms = event.get("latency_ms")
            span.metadata["error"] = str(event.get("error") or "")
        else:
            continue
        if node:
            span.metadata["node"] = node

    return list(spans.values())
