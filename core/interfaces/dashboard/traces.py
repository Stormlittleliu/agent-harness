# -*- coding: utf-8 -*-
"""A/B 逐条 case 的执行轨迹：按 trace_id 从本地 trace 文件读取紧凑时间线。

trace 文件按天写入 ``outputs/traces/trace_*.jsonl``。这里按文件路径 + mtime
缓存 trace_id 索引，页面加载时只解析一次；文件更新后缓存自动失效。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from core.interfaces.dashboard.common import ROOT, file_mtime

TRACE_DIR = ROOT / "outputs" / "traces"


def _trace_files() -> tuple[tuple[str, float], ...]:
    files: list[tuple[str, float]] = []
    for path in sorted(TRACE_DIR.glob("trace_*.jsonl")):
        stamp = file_mtime(path)
        if stamp is not None:
            files.append((str(path), stamp))
    return tuple(files)


@st.cache_resource(show_spinner=False, max_entries=4)
def _load_index(files: tuple[tuple[str, float], ...]) -> dict[str, list[dict]]:
    """把 trace 文件解析成 trace_id -> events 的索引。

    使用 cache_resource 避免每次取用时反序列化整份索引；索引只读，
    不会在渲染过程中修改。坏行直接跳过，与 trace_report.load_events 一致。
    """
    index: dict[str, list[dict]] = {}
    for path_str, _stamp in files:
        try:
            lines = Path(path_str).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            trace_id = event.get("trace_id")
            if trace_id:
                index.setdefault(str(trace_id), []).append(event)
    return index


def _load_trace(trace_id: str | None) -> tuple[list[dict] | None, str | None]:
    """返回 ``(events, issue)``；issue 为空表示读取成功。"""
    if not trace_id:
        return None, "no-id"
    files = _trace_files()
    if not files:
        return None, "no-files"
    try:
        index = _load_index(files)
    except Exception as exc:  # noqa: BLE001 - 页面用 caption 兜底，不抛 traceback
        return None, f"{type(exc).__name__}: {exc}"
    events = index.get(str(trace_id))
    if not events:
        return None, "not-found"
    return events, None


def _time_text(value: Any) -> str:
    text = str(value or "")
    if "T" in text:
        return text.split("T", 1)[1][:12]
    if " " in text:
        return text.split(" ", 1)[1][:12]
    return text[-12:]


def _number(value: Any) -> int | float | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


def _total_tokens(event: dict) -> int | None:
    total = _number(event.get("total_tokens"))
    if total is not None:
        return int(total)
    prompt = _number(event.get("prompt_tokens"))
    completion = _number(event.get("completion_tokens"))
    if prompt is None and completion is None:
        return None
    return int((prompt or 0) + (completion or 0))


def _timeline_rows(events: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for event in events:
        name = event.get("event")
        if name == "model_end":
            rows.append({
                "时间": _time_text(event.get("ts")),
                "事件": "模型结束",
                "工具 / 模型": event.get("model") or "—",
                "状态": "—",
                "耗时(ms)": _number(event.get("latency_ms")),
                "Token": _total_tokens(event),
            })
        elif name == "tool_start":
            rows.append({
                "时间": _time_text(event.get("ts")),
                "事件": "工具开始",
                "工具 / 模型": event.get("tool") or "—",
                "状态": "开始",
                "耗时(ms)": None,
                "Token": None,
            })
        elif name == "tool_end":
            rows.append({
                "时间": _time_text(event.get("ts")),
                "事件": "工具结束",
                "工具 / 模型": event.get("tool") or "—",
                "状态": event.get("status") or "—",
                "耗时(ms)": _number(event.get("latency_ms")),
                "Token": None,
            })
        elif name == "run_end":
            rows.append({
                "时间": _time_text(event.get("ts")),
                "事件": "运行结束",
                "工具 / 模型": "—",
                "状态": event.get("status") or "—",
                "耗时(ms)": _number(event.get("duration_ms")),
                "Token": _total_tokens(event),
            })
    return rows


def render_trace_timeline(trace_id: str | None) -> None:
    """在 A/B case 详情中渲染一条 trace；缺失时只显示 caption。"""
    events, issue = _load_trace(trace_id)
    if issue == "no-id":
        st.caption("该结果没有 trace_id（旧版结果或未记录 trace）。")
        return
    if issue == "no-files":
        st.caption("未找到 trace 文件（`outputs/traces/trace_*.jsonl`）。")
        return
    if issue == "not-found":
        st.caption(
            f"未找到 trace `{trace_id}`（可能来自旧版，或 trace 文件已清理）。"
        )
        return
    if issue:
        st.caption(f"trace 读取失败：{issue}")
        return

    events = events or []
    rows = _timeline_rows(events)
    if not rows:
        st.caption("该 trace 中没有模型 / 工具 / 运行结束事件。")
        return

    model_calls = sum(1 for event in events if event.get("event") == "model_end")
    tool_calls = sum(1 for event in events if event.get("event") == "tool_end")
    st.caption(
        f"`{trace_id}` ｜ 模型 {model_calls} 次 · 工具 {tool_calls} 次"
    )
    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
        height=min(320, max(120, 38 + 32 * len(rows))),
    )
