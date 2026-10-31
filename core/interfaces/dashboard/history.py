# -*- coding: utf-8 -*-
"""评测记录视图：浏览 outputs/ 下已有的报告、Markdown 与 trace。

这里只读取落盘结果，不触发任何评测或模型调用。JSON 文件按 path + mtime
缓存；超大 JSON 只尝试读取顶层的 ``summary``，不会把完整文件读进页面。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import streamlit as st

from core.interfaces.dashboard.common import (
    MAX_ROWS,
    ROOT,
    file_mtime,
    format_mtime,
    load_json,
    load_jsonl,
    load_text,
    short_text,
)
from core.interfaces.dashboard.traces import _timeline_rows

OUTPUTS = ROOT / "outputs"

# 页面内完整解析 / 内嵌展示 / 下载的体积上限。超大 JSON（例如重新生成的
# 全量检索报告）不能在页面加载时直接 json.loads；超过解析上限时退化为 summary 预览。
MAX_JSON_PARSE_BYTES = 10 * 1024 * 1024
MAX_RAW_JSON_BYTES = 2 * 1024 * 1024
MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024
SUMMARY_SEARCH_BYTES = 2 * 1024 * 1024

TYPE_LABELS = {
    "agent": "Agent 测试",
    "rag": "RAG 评测",
    "public": "公开基准",
    "bfcl": "BFCL",
    "tau2": "τ²-bench",
    "demo": "优化循环 / 实验",
    "trace": "Trace",
}
TYPE_ORDER = tuple(TYPE_LABELS)

FILE_PATTERNS = (
    ("agent", "agent", "agent_test_*.json"),
    ("agent", "agent", "agent_test_*.md"),
    ("rag", "rag", "eval_*.json"),
    ("rag", "rag", "eval_*.md"),
    ("public", "public", "*.json"),
    ("public", "public", "*.md"),
    ("bfcl", "bfcl", "eval_bfcl.json"),
    ("bfcl", "bfcl", "eval_bfcl.md"),
    ("tau2", "tau2", "results.json"),
    ("demo", "demo*", "iteration_*.json"),
    ("demo", "demo*", "report.md"),
    ("trace", "traces", "trace_*.jsonl"),
)

FIELD_LABELS = {
    "category": "类别",
    "kind": "类型",
    "question_type": "问题类型",
    "benchmark": "来源 / Benchmark",
    "source": "来源",
    "dataset": "数据集",
    "mode": "模式",
    "type": "类型",
}
STATUS_KEYS = ("passed", "hit", "success", "ok")
PREFERRED_RESULT_KEYS = (
    "数据集",
    "id",
    "task_id",
    "benchmark",
    "category",
    "kind",
    "question_type",
    "source",
    "question",
    "passed",
    "hit",
    "exact",
    "coverage",
    "mrr",
    "failure_type",
    "expected_name",
    "actual",
    "name_ok",
    "args_ok",
    "tool_names",
    "error",
    "reward",
    "duration",
)
HEAVY_RESULT_KEYS = {
    "answer",
    "retrieved_context",
    "expected_context",
    "messages",
    "ticks",
    "effect_timeline",
    "policy",
    "review",
    "user_only_review",
    "info",
    "config",
    "judge",
    "expected_args",
    "expected_points",
    "matched_points",
    "calls",
}


def _format_size(size: int) -> str:
    if size >= 1024 ** 3:
        return f"{size / 1024 ** 3:.1f} GB"
    if size >= 1024 ** 2:
        return f"{size / 1024 ** 2:.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def _digest(path_str: str) -> str:
    return hashlib.md5(path_str.encode("utf-8")).hexdigest()[:8]


def _discover_files() -> list[dict]:
    """扫描固定的报告路径，返回按 mtime 倒序排列的文件元数据。"""
    found: dict[str, dict] = {}
    for kind, subdir, pattern in FILE_PATTERNS:
        # subdir 支持通配，例如 demo* 同时覆盖 demo / demo_bfcl / demo_rag_confirm
        directories = OUTPUTS.glob(subdir) if "*" in subdir else [OUTPUTS / subdir]
        for directory in directories:
            if not directory.is_dir():
                continue
            for path in directory.glob(pattern):
                if not path.is_file():
                    continue
                stamp = file_mtime(path)
                if stamp is None:
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                try:
                    relpath = path.relative_to(ROOT).as_posix()
                except ValueError:
                    relpath = path.as_posix()
                found[str(path)] = {
                    "path": path,
                    "path_str": str(path),
                    "kind": kind,
                    "type_label": TYPE_LABELS[kind],
                    "name": path.name,
                    "relpath": relpath,
                    "mtime": stamp,
                    "size": size,
                }
    return sorted(
        found.values(),
        key=lambda item: (item["mtime"], item["relpath"]),
        reverse=True,
    )


@st.cache_data(show_spinner=False)
def _summary_prefix_cached(path_str: str, mtime: float) -> tuple[Any | None, str | None]:
    """只解析 JSON 顶层 summary，避免把超大文件整体读入内存。

    summary 在这些报告中通常是第一个键。这里先读一小段定位 ``"summary"``，
    再用 ``JSONDecoder.raw_decode`` 增量补读，直到 summary 值完整或到达
    ``SUMMARY_SEARCH_BYTES`` 上限。
    """
    path = Path(path_str)
    try:
        with path.open("r", encoding="utf-8") as handle:
            buffer = handle.read(65536)
            idx = buffer.find('"summary"')
            while idx < 0 and len(buffer) < SUMMARY_SEARCH_BYTES:
                chunk = handle.read(65536)
                if not chunk:
                    break
                buffer += chunk
                idx = buffer.find('"summary"')
            if idx < 0:
                return None, None
            start = buffer.find(":", idx) + 1
            if start <= 0:
                return None, None
            while start < len(buffer) and buffer[start].isspace():
                start += 1
            decoder = json.JSONDecoder()
            while True:
                try:
                    value, _end = decoder.raw_decode(buffer[start:])
                    return value, None
                except json.JSONDecodeError as exc:
                    if len(buffer) >= SUMMARY_SEARCH_BYTES:
                        return None, f"{type(exc).__name__}: summary 超过预览上限"
                    chunk = handle.read(65536)
                    if not chunk:
                        return None, f"{type(exc).__name__}: {exc}"
                    buffer += chunk
    except (OSError, UnicodeError) as exc:  # noqa: BLE001 - 页面兜底
        return None, f"{type(exc).__name__}: {exc}"


def _top_level_hint(data: dict) -> str:
    parts: list[str] = []
    for key, value in data.items():
        if isinstance(value, list):
            parts.append(f"{key} {len(value)}")
        if len(parts) >= 3:
            break
    if parts:
        return " · ".join(parts)
    keys = [str(key) for key in list(data.keys())[:3]]
    return "keys: " + ", ".join(keys) if keys else "JSON 对象"


@st.cache_data(show_spinner=False)
def _summary_meta(path_str: str, mtime: float, size: int) -> tuple[str, str | None]:
    """表格“摘要”列：小 JSON 读 summary，超大 JSON 只读 summary 前缀。"""
    path = Path(path_str)
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return "JSONL · 选中后选择 trace_id", None
    if suffix == ".md":
        text, error = load_text(path)
        if error:
            return "读取失败", error
        if text is None:
            return "文件不存在", None
        for line in text.splitlines():
            line = line.strip()
            if line:
                heading = line.lstrip("# ").strip()
                return f"Markdown · {short_text(heading, 80)}" if heading else "Markdown", None
        return "空 Markdown", None
    if suffix != ".json":
        return "", None

    if size > MAX_JSON_PARSE_BYTES:
        summary, error = _summary_prefix_cached(path_str, mtime)
        if error:
            return "大文件 · summary 读取失败", error
        if summary is None:
            return "大文件 · 未发现 summary", None
        if isinstance(summary, dict):
            text = _summary_text(summary)
            return f"大文件 · {text}" if text else "大文件 · summary 为空", None
        return f"大文件 · {short_text(json.dumps(summary, ensure_ascii=False), 100)}", None

    data, error = load_json(path)
    if error:
        return "读取失败", error
    if data is None:
        return "文件不存在", None
    if isinstance(data, dict):
        summary = data.get("summary")
        if isinstance(summary, dict):
            text = _summary_text(summary)
            return text or "summary 为空", None
        if summary is not None:
            return short_text(json.dumps(summary, ensure_ascii=False), 100), None
        return _top_level_hint(data), None
    if isinstance(data, list):
        return f"列表 · {len(data)} 条", None
    return short_text(data, 100), None


def _summary_pairs(
    value: Any,
    prefix: str = "",
    out: list[tuple[str, Any]] | None = None,
    depth: int = 0,
) -> list[tuple[str, Any]]:
    if out is None:
        out = []
    if len(out) >= MAX_ROWS or depth > 6:
        return out
    if isinstance(value, dict):
        for key, item in value.items():
            label = f"{prefix}.{key}" if prefix else str(key)
            _summary_pairs(item, label, out, depth + 1)
    else:
        out.append((prefix or "value", value))
    return out


def _display_value(value: Any, key: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "✅" if value else "❌"
    if isinstance(value, (dict, list)):
        return short_text(json.dumps(value, ensure_ascii=False), 180)
    if isinstance(value, float):
        lower = key.lower()
        if 0 <= value <= 1 and any(
            word in lower for word in ("rate", "acc", "coverage", "hit", "mean")
        ):
            return f"{value:.1%}"
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return f"{value:,}"
    return short_text(value, 180)


def _summary_text(summary: dict) -> str:
    """给表格摘要列用的短文本；完整指标仍在选中文件后展示。"""
    if not isinstance(summary, dict) or not summary:
        return ""
    values = list(summary.values())
    if values and all(isinstance(value, dict) for value in values) and any(
        "hit_at_4" in value or "hit_at_k" in value for value in values
    ):
        parts = []
        for name, item in summary.items():
            metrics = [
                f"{key} {_display_value(item[key], key)}"
                for key in ("hit_at_4", "hit_at_k", "mrr", "scored")
                if key in item
            ]
            parts.append(f"{name}: " + ", ".join(metrics[:3]))
        return " ｜ ".join(parts[:3])

    if "bfcl_pass" in summary and "bfcl_total" in summary:
        parts = [f"BFCL {summary.get('bfcl_pass')}/{summary.get('bfcl_total')}"]
        if summary.get("bfcl_mean") is not None:
            parts[-1] += f" ({_display_value(summary['bfcl_mean'], 'bfcl_mean')})"
        if "rag_pass" in summary and "rag_total" in summary:
            rag = f"RAG {summary.get('rag_pass')}/{summary.get('rag_total')}"
            if summary.get("rag_mean") is not None:
                rag += f" ({_display_value(summary['rag_mean'], 'rag_mean')})"
            parts.append(rag)
        return " · ".join(parts)

    if "simple_exact" in summary or "simple_total" in summary:
        parts = []
        if "simple_exact" in summary:
            parts.append(
                f"simple exact {summary.get('simple_exact')}/{summary.get('simple_total')}"
            )
        if "irrelevance_no_call" in summary:
            parts.append(
                "irrelevance "
                f"{summary.get('irrelevance_no_call')}/{summary.get('irrelevance_total')}"
            )
        if summary.get("errors") is not None:
            parts.append(f"errors {summary.get('errors')}")
        if parts:
            return " · ".join(parts)

    if "total" in summary and "passed" in summary:
        parts = [f"passed {summary.get('passed')}/{summary.get('total')}"]
        for key in ("scenario", "mode", "answer_avg_coverage", "refusal_correct", "refusal_count"):
            if key in summary:
                parts.append(f"{key} {_display_value(summary[key], key)}")
        return " · ".join(parts[:4])

    pairs = _summary_pairs(summary)
    interesting = [
        pair
        for pair in pairs
        if any(
            word in pair[0].lower()
            for word in (
                "pass",
                "total",
                "score",
                "hit",
                "mrr",
                "mean",
                "acc",
                "coverage",
                "error",
                "count",
                "reward",
                "mode",
                "scenario",
            )
        )
    ]
    chosen = (interesting or pairs)[:4]
    return " · ".join(f"{label}={_display_value(value, label)}" for label, value in chosen)


def _render_summary(summary: dict) -> None:
    rows = [
        {"指标": label, "值": _display_value(value, label)}
        for label, value in _summary_pairs(summary)
    ]
    if not rows:
        st.caption("summary 为空。")
        return
    if len(rows) > MAX_ROWS:
        st.caption(f"summary 共 {len(rows)} 项；仅展示前 {MAX_ROWS} 项。")
    st.dataframe(rows[:MAX_ROWS], use_container_width=True, hide_index=True)


def _extract_results(data: Any) -> tuple[str | None, list[dict]]:
    if isinstance(data, list):
        return "list", [row for row in data if isinstance(row, dict)]
    if not isinstance(data, dict):
        return None, []
    results = data.get("results")
    if isinstance(results, list):
        return "results", [row for row in results if isinstance(row, dict)]
    bfcl_rows = data.get("bfcl_results")
    rag_rows = data.get("rag_results")
    if isinstance(bfcl_rows, list) or isinstance(rag_rows, list):
        combined: list[dict] = []
        for label, values in (("BFCL", bfcl_rows), ("RAG", rag_rows)):
            if not isinstance(values, list):
                continue
            for row in values:
                if isinstance(row, dict):
                    item = dict(row)
                    item.setdefault("数据集", label)
                    combined.append(item)
        return "bfcl_results + rag_results", combined
    return None, []


def _find_status_key(rows: list[dict]) -> str | None:
    for key in STATUS_KEYS:
        if any(isinstance(row.get(key), bool) for row in rows):
            return key
    return None


def _field_values(rows: list[dict], key: str) -> list[str]:
    values = {
        str(row.get(key))
        for row in rows
        if row.get(key) not in (None, "")
        and not isinstance(row.get(key), (dict, list))
    }
    return sorted(values)


def _pick_filter_fields(rows: list[dict]) -> list[tuple[str, list[str]]]:
    fields: list[tuple[str, list[str]]] = []
    for key in ("category", "kind", "question_type"):
        values = _field_values(rows, key)
        if len(values) >= 2:
            fields.append((key, values))
            break
    for key in ("benchmark", "source", "dataset", "mode"):
        values = _field_values(rows, key)
        if len(values) >= 2 and all(key != field[0] for field in fields):
            fields.append((key, values))
            break
    return fields


def _display_keys(rows: list[dict]) -> list[str]:
    all_keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                all_keys.append(key)
    keys = [key for key in PREFERRED_RESULT_KEYS if key in seen]
    for key in all_keys:
        if key in keys or key in HEAVY_RESULT_KEYS:
            continue
        keys.append(key)
        if len(keys) >= 12:
            break
    return keys[:12]


def _result_cell(value: Any, key: str) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "✅" if value else "❌"
    if isinstance(value, (dict, list)):
        return short_text(json.dumps(value, ensure_ascii=False), 120)
    if isinstance(value, float):
        return _display_value(value, key)
    if isinstance(value, str):
        return short_text(value, 120)
    return str(value)


def _render_results(rows: list[dict], path_str: str) -> None:
    total = len(rows)
    status_key = _find_status_key(rows)
    fields = _pick_filter_fields(rows)
    selections: dict[str, list[str]] = {}
    status_value = "全部"

    if status_key or fields:
        columns = st.columns(1 + len(fields))
        offset = 0
        if status_key:
            status_value = columns[0].radio(
                "结果",
                ["全部", "✅ 通过", "❌ 失败"],
                horizontal=True,
                key=f"history-status-{_digest(path_str)}",
            )
            offset = 1
        for index, (key, values) in enumerate(fields, start=offset):
            selections[key] = columns[index].multiselect(
                FIELD_LABELS.get(key, key),
                values,
                key=f"history-field-{_digest(path_str)}-{key}",
                help="不选表示全部",
            )

    filtered: list[dict] = []
    for row in rows:
        if status_key and status_value != "全部":
            value = row.get(status_key)
            if not isinstance(value, bool):
                continue
            if status_value == "✅ 通过" and not value:
                continue
            if status_value == "❌ 失败" and value:
                continue
        skip = False
        for key, selected in selections.items():
            if selected and str(row.get(key)) not in selected:
                skip = True
                break
        if not skip:
            filtered.append(row)

    suffix = f"；仅展示前 {MAX_ROWS} 条" if len(filtered) > MAX_ROWS else ""
    st.caption(f"筛选后 {len(filtered)} / {total} 条{suffix}")
    if not filtered:
        st.info("没有符合筛选条件的记录。")
        return

    keys = _display_keys(rows)
    display_rows = [
        {key: _result_cell(row.get(key), key) for key in keys}
        for row in filtered[:MAX_ROWS]
    ]
    st.dataframe(display_rows, use_container_width=True, hide_index=True)


@st.cache_data(show_spinner=False)
def _read_bytes_cached(path_str: str, mtime: float) -> bytes:
    return Path(path_str).read_bytes()


def _render_download(path: Path, size: int, mtime: float, label: str, mime: str) -> None:
    if size > MAX_DOWNLOAD_BYTES:
        st.caption(
            f"文件较大（{_format_size(size)}），超过页面内下载上限 "
            f"{_format_size(MAX_DOWNLOAD_BYTES)}；请直接从磁盘打开。"
        )
        return
    try:
        data = _read_bytes_cached(str(path), mtime)
    except (OSError, UnicodeError) as exc:  # noqa: BLE001
        st.warning(f"下载文件读取失败：{type(exc).__name__}: {exc}")
        return
    st.download_button(
        label,
        data=data,
        file_name=path.name,
        mime=mime,
        key=f"history-download-{_digest(str(path))}",
    )


def _render_raw_json(data: Any, size: int) -> None:
    with st.expander("查看原始 JSON", expanded=False):
        if size > MAX_RAW_JSON_BYTES:
            st.caption(
                f"文件较大（{_format_size(size)}），已省略内嵌 JSON；"
                "可使用下方下载按钮或直接从磁盘打开。"
            )
        else:
            st.json(data)


def _render_json_file(row: dict) -> None:
    path: Path = row["path"]
    size: int = row["size"]
    mtime: float = row["mtime"]

    if size > MAX_JSON_PARSE_BYTES:
        summary, error = _summary_prefix_cached(str(path), mtime)
        if error:
            st.warning(f"summary 读取失败：{error}")
        if isinstance(summary, dict):
            _render_summary(summary)
        elif summary is not None:
            st.json(summary)
        else:
            st.info("文件较大，未能读取 summary。")
        st.warning(
            f"文件大小 {_format_size(size)}，超过页面解析上限 "
            f"{_format_size(MAX_JSON_PARSE_BYTES)}；已只加载 summary，"
            "未加载 results 和完整 JSON。"
        )
        with st.expander("查看原始 JSON", expanded=False):
            st.caption(
                f"文件较大（{_format_size(size)}），已省略内嵌 JSON；"
                "请直接从磁盘打开原始文件。"
            )
        _render_download(path, size, mtime, "下载 JSON", "application/json")
        return

    data, error = load_json(path)
    if error:
        st.error(f"读取 JSON 失败：{error}")
        _render_download(path, size, mtime, "下载 JSON", "application/json")
        return
    if data is None:
        st.info("文件不存在或为空。")
        return

    if isinstance(data, dict):
        summary = data.get("summary")
        if isinstance(summary, dict) and summary:
            st.markdown("**Summary**")
            _render_summary(summary)
        elif summary is not None:
            st.markdown("**Summary**")
            st.json(summary)
        else:
            st.caption(f"未发现 summary 字段。顶层：{_top_level_hint(data)}")
    else:
        st.caption("该 JSON 不是对象，按顶层列表展示逐条结果。")

    results_name, results = _extract_results(data)
    if results:
        st.markdown(f"**逐条结果**（`{results_name}`）")
        _render_results(results, str(path))
    elif results_name:
        st.caption(f"`{results_name}` 为空。")
    else:
        st.caption("未发现 results 列表。")

    _render_raw_json(data, size)
    _render_download(path, size, mtime, "下载 JSON", "application/json")


def _render_markdown_file(row: dict) -> None:
    path: Path = row["path"]
    text, error = load_text(path)
    if error:
        st.error(f"读取 Markdown 失败：{error}")
        return
    if text is None:
        st.info("文件不存在。")
        return
    if not text.strip():
        st.info("Markdown 文件为空。")
        return
    st.markdown(text)
    _render_download(path, row["size"], row["mtime"], "下载 Markdown", "text/markdown")


def _render_trace_file(row: dict) -> None:
    path: Path = row["path"]
    rows, error, skipped = load_jsonl(path)
    if error:
        st.error(f"读取 trace 失败：{error}")
        return
    if rows is None:
        st.info("trace 文件不存在。")
        return
    if not rows:
        st.info("trace 文件为空。")
        return

    trace_ids = sorted(
        {
            str(row.get("trace_id"))
            for row in rows
            if isinstance(row, dict) and row.get("trace_id")
        }
    )
    caption = f"共 {len(rows)} 条事件 · {len(trace_ids)} 个 trace_id"
    if skipped:
        caption += f" · 跳过 {skipped} 个坏行"
    st.caption(caption)
    if not trace_ids:
        st.info("事件中没有 trace_id，无法选择执行轨迹。")
        return

    key = f"history-trace-{_digest(str(path))}"
    if st.session_state.get(key) not in trace_ids:
        st.session_state.pop(key, None)
    selected = st.selectbox("trace_id", trace_ids, key=key)
    events = [row for row in rows if str(row.get("trace_id")) == selected]
    timeline = _timeline_rows(events)
    if not timeline:
        st.caption("该 trace 中没有模型 / 工具 / 运行结束事件。")
        return

    model_calls = sum(1 for event in events if event.get("event") == "model_end")
    tool_calls = sum(1 for event in events if event.get("event") == "tool_end")
    st.caption(f"`{selected}` ｜ 模型 {model_calls} 次 · 工具 {tool_calls} 次")
    st.dataframe(
        timeline,
        use_container_width=True,
        hide_index=True,
        height=min(320, max(120, 38 + 32 * len(timeline))),
    )


def _render_selected(row: dict) -> None:
    path: Path = row["path"]
    stamp = file_mtime(path)
    if stamp is None:
        st.info(f"文件不存在或已移走：`{row.get('relpath') or path}`。")
        return
    try:
        size = path.stat().st_size
    except OSError:
        size = int(row.get("size") or 0)

    suffix = path.suffix.lower()
    if suffix == ".md":
        _render_markdown_file({**row, "size": size, "mtime": stamp})
    elif suffix == ".jsonl":
        _render_trace_file({**row, "size": size, "mtime": stamp})
    elif suffix == ".json":
        _render_json_file({**row, "size": size, "mtime": stamp})
    else:
        st.info(f"暂不支持预览该文件类型：`{path.suffix or '无扩展名'}`。")


def render_history() -> None:
    st.caption(
        "只读取 outputs 下已有评测记录，不重新运行评测，也不会触发模型调用；"
        "文件按 path + mtime 缓存，超大 JSON 仅加载 summary。"
    )
    files = _discover_files()
    if not files:
        st.info(
            "未找到评测记录。生成报告后可回到此页刷新；"
            "支持 outputs/agent、rag、public、bfcl、tau2、demo 与 traces。"
        )
        return

    present_labels = [
        TYPE_LABELS[kind]
        for kind in TYPE_ORDER
        if any(row["kind"] == kind for row in files)
    ]
    col_type, col_search = st.columns([1, 2.2])
    selected_type = col_type.selectbox(
        "类型",
        ["全部"] + present_labels,
        key="history-type",
    )
    query = col_search.text_input(
        "搜索文件",
        placeholder="输入文件名或路径片段",
        key="history-search",
    ).strip().casefold()

    filtered: list[dict] = []
    for row in files:
        if selected_type != "全部" and row["type_label"] != selected_type:
            continue
        if query and query not in row["relpath"].casefold() and query not in row["name"].casefold():
            continue
        filtered.append(row)

    st.caption(f"共 {len(filtered)} / {len(files)} 个文件；按更新时间倒序。")
    if not filtered:
        st.info("没有匹配的文件。")
        return

    table_rows = []
    for row in filtered[:MAX_ROWS]:
        summary, _error = _summary_meta(row["path_str"], row["mtime"], row["size"])
        table_rows.append({
            "类型": row["type_label"],
            "文件": row["relpath"],
            "更新时间": format_mtime(row["mtime"]),
            "大小": _format_size(row["size"]),
            "摘要": summary,
        })
    if len(filtered) > MAX_ROWS:
        st.caption(f"仅展示前 {MAX_ROWS} 个文件。")
    st.dataframe(table_rows, use_container_width=True, hide_index=True)

    by_option = {
        f"{row['type_label']} · {row['relpath']}": row
        for row in filtered
    }
    options = list(by_option)
    if st.session_state.get("history-file") not in options:
        st.session_state.pop("history-file", None)
    selected_option = st.selectbox("选择文件", options, key="history-file")
    row = by_option[selected_option]
    stamp = file_mtime(row["path"]) or row["mtime"]
    try:
        size = row["path"].stat().st_size
    except OSError:
        size = row["size"]

    st.divider()
    st.subheader(f"{row['type_label']} · {row['name']}")
    st.caption(
        f"`{row['relpath']}` ｜ 更新于 {format_mtime(stamp)} ｜ {_format_size(size)}"
    )
    _render_selected(row)
