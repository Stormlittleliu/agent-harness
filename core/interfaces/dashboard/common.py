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

ROOT = Path(__file__).resolve().parents[3]
MAX_ROWS = 200
NOT_AVAILABLE = "—"
AGENT_OUT = ROOT / "outputs" / "agent"
OUTCOME_OUT = ROOT / "outputs" / "outcome"


@st.cache_resource(show_spinner=False)
def load_agent(scenario_name: str):
    """按场景缓存 Agent；切换场景时才重新构建。

    延迟 import，避免纯数据视图（成本、目录、记录）加载 LangChain 与工具链。
    """
    from core.agent.framework import FrameworkAgent
    from core.scenarios.registry import get_scenario

    return FrameworkAgent(get_scenario(scenario_name))


@st.cache_data(show_spinner=False)
def _load_cases_file(path: str, mtime: float) -> list[dict]:
    _ = mtime
    from core.quality.agent_eval import load_cases

    return load_cases(Path(path))


def load_cases_cached(path: Path | str | None) -> tuple[list[dict] | None, str | None]:
    """按 path + mtime 缓存 cases.jsonl；返回 ``(cases, error)``。"""
    if not path:
        return None, None
    target = Path(path)
    stamp = file_mtime(target)
    if stamp is None:
        return None, None
    try:
        return _load_cases_file(str(target), stamp), None
    except Exception as exc:  # noqa: BLE001 - 页面兜底
        return None, f"{type(exc).__name__}: {exc}"


def _latest_report(
    files: list[Path],
    expected_total: int | None = None,
) -> tuple[dict | None, Path | None]:
    """从一组报告文件里选一份：优先用例数匹配，其次最新 / 最完整。"""
    candidates: list[tuple[int, float, Path, dict]] = []
    for path in files:
        data, _error = load_json(path)
        if not isinstance(data, dict):
            continue
        summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
        total = summary.get("total")
        if total is None:
            results = data.get("results")
            total = len(results) if isinstance(results, list) else 0
        try:
            total = int(total)
        except (TypeError, ValueError):
            total = 0
        candidates.append((total, file_mtime(path) or 0.0, path, data))
    if not candidates:
        return None, None

    if expected_total is not None:
        exact = [item for item in candidates if item[0] == expected_total]
        if exact:
            chosen = max(exact, key=lambda item: item[1])
        else:
            chosen = max(candidates, key=lambda item: (item[0], item[1]))
    else:
        chosen = max(candidates, key=lambda item: item[1])
    return chosen[3], chosen[2]


def latest_agent_report(
    scenario_name: str,
    expected_total: int | None = None,
) -> tuple[dict | None, Path | None]:
    """读取该场景的行为层报告；没有则返回 (None, None)。

    同一场景可能既有全量报告，也有 `--limit 1` 的冒烟报告。传入
    `expected_total` 时优先选用例数完全匹配的报告，避免“最近一次”其实是
    单条 smoke run；没有匹配时退回结果条数最多的报告。
    """
    files = [path for path in AGENT_OUT.glob(f"agent_test_{scenario_name}_*.json") if path.is_file()]
    return _latest_report(files, expected_total)


def latest_outcome_report(
    scenario_name: str,
    expected_total: int | None = None,
) -> tuple[dict | None, Path | None]:
    """读取该场景的 outcome 报告；规则与行为层报告一致。"""
    files = [path for path in OUTCOME_OUT.glob(f"outcome_test_{scenario_name}_*.json") if path.is_file()]
    return _latest_report(files, expected_total)


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
