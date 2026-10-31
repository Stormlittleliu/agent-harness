# -*- coding: utf-8 -*-
"""Dashboard 公共工具：缓存读取、数据新鲜度、表格上限与少量格式化。"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from core.agent.framework import FrameworkAgent
from core.scenarios.registry import get_scenario

ROOT = Path(__file__).resolve().parents[3]
MAX_ROWS = 200
NOT_AVAILABLE = "—"


@st.cache_resource(show_spinner=False)
def load_agent(scenario_name: str) -> FrameworkAgent:
    """按场景缓存 Agent；切换场景时才重新构建。"""
    return FrameworkAgent(get_scenario(scenario_name))


def display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def file_mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def format_mtime(timestamp: float | None) -> str:
    if timestamp is None:
        return "文件不存在"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def source_caption(path: Path, prefix: str = "数据文件") -> None:
    """在数据区顶部标注来源与 mtime，便于判断结果是否过期。"""
    stamp = file_mtime(path)
    if stamp is None:
        st.caption(f"{prefix}：`{display_path(path)}` · 文件不存在")
    else:
        st.caption(f"{prefix}：`{display_path(path)}` · 更新于 {format_mtime(stamp)}")


def freshness_caption(entries: list[tuple[Path, str]], prefix: str = "数据来源") -> None:
    """一行展示多个数据文件的更新时间。"""
    parts: list[str] = []
    for path, label in entries:
        stamp = file_mtime(path)
        if stamp is None:
            parts.append(f"{label}（缺失）")
        else:
            parts.append(f"{label} · {format_mtime(stamp)}")
    if parts:
        st.caption(f"{prefix}：" + " ｜ ".join(parts))


@st.cache_data(show_spinner=False)
def _read_json(path: str, mtime: float) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_json(path: Path) -> tuple[Any | None, str | None]:
    """按 path + mtime 缓存读取 JSON。

    返回 ``(data, error)``：文件不存在时 ``(None, None)``；
    解析失败时 ``(None, "错误信息")``，调用方自行展示友好提示。
    """
    stamp = file_mtime(path)
    if stamp is None:
        return None, None
    try:
        return _read_json(str(path), stamp), None
    except Exception as exc:  # noqa: BLE001 - 页面需要兜底而不是抛 traceback
        return None, f"{type(exc).__name__}: {exc}"


@st.cache_data(show_spinner=False)
def _read_text(path: str, mtime: float) -> str:
    return Path(path).read_text(encoding="utf-8")


def load_text(path: Path) -> tuple[str | None, str | None]:
    """按 path + mtime 缓存读取文本（用于 report.md）。"""
    stamp = file_mtime(path)
    if stamp is None:
        return None, None
    try:
        return _read_text(str(path), stamp), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


@st.cache_data(show_spinner=False)
def _read_jsonl(path: str, mtime: float) -> tuple[list[dict], int]:
    rows: list[dict] = []
    skipped = 0
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if isinstance(item, dict):
            rows.append(item)
        else:
            skipped += 1
    return rows, skipped


def load_jsonl(path: Path) -> tuple[list[dict] | None, str | None, int]:
    """按 path + mtime 缓存读取 JSONL，跳过坏行。

    返回 ``(rows, error, skipped)``；文件不存在时 rows 为 None。
    """
    stamp = file_mtime(path)
    if stamp is None:
        return None, None, 0
    try:
        rows, skipped = _read_jsonl(str(path), stamp)
        return rows, None, skipped
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}", 0


def parse_ratio(value: Any) -> tuple[int, int, float | None]:
    """解析 ``"3/5"`` 形式的通过率。"""
    text = str(value or "")
    if "/" not in text:
        return 0, 0, None
    left, right = text.rsplit("/", 1)
    try:
        passed, total = int(left), int(right)
    except ValueError:
        return 0, 0, None
    return passed, total, (passed / total if total else None)


def ratio_label(passed: int | None, total: int | None) -> str:
    if not total:
        return NOT_AVAILABLE
    return f"{passed or 0}/{total}"


def pct_label(value: Any, digits: int = 0) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return NOT_AVAILABLE
    return f"{number:.{digits}%}"


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def short_text(value: Any, limit: int = 80) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def rows_to_csv(rows: list[dict]) -> bytes:
    """把展示行转成 Excel 友好的 UTF-8 BOM CSV，包含全部筛选结果。"""
    if not rows:
        return b""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()), extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def show_rows(
    rows: list[dict],
    total: int | None = None,
    *,
    label: str = "条",
    limit: int = MAX_ROWS,
    empty_message: str = "没有符合条件的数据。",
) -> bool:
    """统一渲染受行数上限保护的数据表；返回是否展示成功。"""
    if not rows:
        st.info(empty_message)
        return False
    total = len(rows) if total is None else total
    shown = rows[:limit]
    suffix = f"；仅展示前 {limit} 条" if total > limit else ""
    st.caption(f"共 {total} {label}{suffix}")
    st.dataframe(shown, use_container_width=True, hide_index=True)
    return True
