# -*- coding: utf-8 -*-
"""优化循环视图：读取 outputs/demo 的 iteration_*.json 与 report.md。"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from core.interfaces.dashboard.common import (
    MAX_ROWS,
    ROOT,
    file_mtime,
    format_mtime,
    load_json,
    load_text,
    parse_ratio,
    rows_to_csv,
    short_text,
)
from core.interfaces.dashboard.traces import render_trace_timeline

DEMO_DIR = ROOT / "outputs" / "demo"
REPORT_PATH = DEMO_DIR / "report.md"
GENERATE_CMD = "python -m core.experiments.optimize --iterations 5 --trials 3"

# 统一的克制配色：BFCL 蓝、RAG 橙；同数据集用深浅区分 pass^k / mean。
BFCL_COLORS = ["#3B6EA5", "#9DB7D5"]
RAG_COLORS = ["#C07A32", "#E0B98C"]
FAILURE_COLORS = ["#3B6EA5", "#C07A32"]


def _iteration_paths() -> list[Path]:
    return sorted(DEMO_DIR.glob("iteration_*.json"))


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _pct(value: Any, digits: int = 0) -> str:
    try:
        return f"{float(value):.{digits}%}"
    except (TypeError, ValueError):
        return "—"


def _rate(passed: int, total: int) -> float | None:
    return (passed / total) if total else None


def _chart_pct(value: Any) -> float | None:
    """把 0–1 的比例转成图表用的 0–100，非法值返回 None。"""
    try:
        return float(value) * 100
    except (TypeError, ValueError):
        return None


def _items_of(item: dict, key: str) -> list[dict]:
    value = item.get(key)
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _mean_of(rows: list[dict]) -> float | None:
    """旧版结果没有 mean 时，用每 case 的 pass_rate（或单 trial 结果）近似。"""
    rates: list[float] = []
    for row in rows:
        value = row.get("pass_rate")
        if value is None:
            value = 1.0 if row.get("passed") else 0.0
        try:
            rates.append(float(value))
        except (TypeError, ValueError):
            continue
    return sum(rates) / len(rates) if rates else None


def _trials(item: dict) -> Any:
    if item.get("trials") is not None:
        return item["trials"]
    lengths = {
        len(row.get("trial_passes") or [])
        for row in _items_of(item, "bfcl_results") + _items_of(item, "rag_results")
        if row.get("trial_passes")
    }
    if len(lengths) == 1:
        return lengths.pop()
    return "未记录"


def _failure_counts(item: dict, key: str, rows: list[dict]) -> dict[str, int]:
    summary = item.get("summary") if isinstance(item.get("summary"), dict) else {}
    counts = summary.get(key)
    if isinstance(counts, dict):
        return {str(name): _int(value) for name, value in counts.items()}
    counter = Counter()
    for row in rows:
        if not row.get("passed") and row.get("failure_type"):
            counter[str(row["failure_type"])] += 1
    return dict(counter)


def _same_class(item: dict) -> dict[str, str]:
    value = item.get("same_class")
    if isinstance(value, dict) and value:
        return {str(key): str(ratio) for key, ratio in value.items()}
    groups: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in _items_of(item, "bfcl_results") + _items_of(item, "rag_results"):
        key = row.get("kind") or row.get("question_type")
        if not key:
            continue
        groups[str(key)][1] += 1
        if row.get("passed"):
            groups[str(key)][0] += 1
    return {key: f"{value[0]}/{value[1]}" for key, value in groups.items()}


def _summary(item: dict) -> dict:
    bfcl_rows = _items_of(item, "bfcl_results")
    rag_rows = _items_of(item, "rag_results")
    summary = item.get("summary") if isinstance(item.get("summary"), dict) else {}

    bfcl_pass = _int(summary.get("bfcl_pass"), sum(1 for row in bfcl_rows if row.get("passed")))
    bfcl_total = _int(summary.get("bfcl_total"), len(bfcl_rows))
    rag_pass = _int(summary.get("rag_pass"), sum(1 for row in rag_rows if row.get("passed")))
    rag_total = _int(summary.get("rag_total"), len(rag_rows))

    bfcl_mean = summary.get("bfcl_mean")
    if bfcl_mean is None:
        bfcl_mean = _mean_of(bfcl_rows)
    rag_mean = summary.get("rag_mean")
    if rag_mean is None:
        rag_mean = summary.get("rag_hit4")
    if rag_mean is None:
        rag_mean = _mean_of(rag_rows)

    compare = item.get("compare") if isinstance(item.get("compare"), dict) else {}
    fixed = compare.get("fixed") if isinstance(compare.get("fixed"), list) else []
    regressed = compare.get("regressed") if isinstance(compare.get("regressed"), list) else []
    unchanged = compare.get("unchanged") if isinstance(compare.get("unchanged"), list) else []

    return {
        "bfcl_pass": bfcl_pass,
        "bfcl_total": bfcl_total,
        "bfcl_mean": bfcl_mean,
        "rag_pass": rag_pass,
        "rag_total": rag_total,
        "rag_mean": rag_mean,
        "trials": _trials(item),
        "bfcl_failures": _failure_counts(item, "bfcl_failures", bfcl_rows),
        "rag_failures": _failure_counts(item, "rag_failures", rag_rows),
        "same_class": _same_class(item),
        "fixed": [str(case_id) for case_id in fixed],
        "regressed": [str(case_id) for case_id in regressed],
        "unchanged": [str(case_id) for case_id in unchanged],
    }


def _item_label(item: dict) -> str:
    index = item.get("index")
    prefix = f"#{_int(index):02d}" if index is not None else "#?"
    name = item.get("name") or "未命名"
    direction = item.get("direction") or "—"
    return f"{prefix} · {name} · {direction}"


def _short_item_label(item: dict | None) -> str:
    if item is None:
        return "—"
    return f"#{_int(item.get('index')):02d} · {item.get('name') or '未命名'}"


def _latest_path(paths: list[Path]) -> Path | None:
    if not paths:
        return None
    return max(paths, key=lambda path: file_mtime(path) or 0.0)


def _render_run_status(paths: list[Path], items: list[dict]) -> None:
    """一次页面加载只检查一次：最新写入时间、已完成数量与在跑提示。"""
    completed = [item for item in items if item.get("trials") is not None]
    latest_path = _latest_path(paths)
    latest_stamp = file_mtime(latest_path) if latest_path else None
    latest_completed = max(
        completed, key=lambda item: _int(item.get("index"), -1), default=None
    )
    with st.container(border=True):
        st.markdown("**运行状态**")
        cols = st.columns(3)
        cols[0].metric("最新写入", format_mtime(latest_stamp))
        cols[1].metric("已完成迭代", f"{len(completed)} / {len(paths)}")
        cols[2].metric("最新完成", _short_item_label(latest_completed))
        if latest_path:
            st.caption(
                f"最新文件：`{latest_path.name}` ｜ "
                "页面每次加载只检查一次文件状态，不会自动轮询。"
            )
        if len(completed) < len(paths):
            st.caption(
                "未包含 trials 的文件可能是旧格式，也可能仍在写入；评测可能尚未完成。"
            )
        else:
            st.caption("全部文件均已包含 trials；若后台评测仍在运行，后续仍可能覆盖写入。")


def _raw_cases(item: dict) -> dict[tuple[str, str], dict]:
    result: dict[tuple[str, str], dict] = {}
    for dataset, key in (("BFCL", "bfcl_results"), ("RAG", "rag_results")):
        for row in _items_of(item, key):
            case_id = row.get("id")
            if case_id is not None:
                result[(dataset, str(case_id))] = row
    return result


def _case_display(ref: tuple[str, str]) -> str:
    dataset, case_id = ref
    return f"`{case_id}`（{dataset}）"


def _ref_list(refs: list[tuple[str, str]], limit: int = 100) -> str:
    if not refs:
        return "无"
    text = "、".join(_case_display(ref) for ref in refs[:limit])
    if len(refs) > limit:
        text += f"…（共 {len(refs)} 条）"
    return text


def _pass_text(row: dict) -> str:
    text = "✅ 通过" if row.get("passed") else "❌ 失败"
    if row.get("pass_rate") is not None:
        text += f"（{_pct(row.get('pass_rate'))}）"
    return text


def _call_names(row: dict, limit: int = 5) -> str:
    names = []
    for call in row.get("calls") or []:
        if not isinstance(call, dict):
            continue
        name = call.get("name") or call.get("query")
        if name:
            names.append(short_text(name, 45))
    if not names:
        return ""
    text = "；".join(names[:limit])
    if len(names) > limit:
        text += f"…（共 {len(names)} 次）"
    return text


def _render_case_side(dataset: str, row: dict) -> None:
    st.caption(
        f"{_pass_text(row)} ｜ 失败类型：{row.get('failure_type') or '—'}"
    )
    trial_passes = row.get("trial_passes") or []
    if trial_passes:
        st.caption(
            "trials：" + " ".join("✅" if item else "❌" for item in trial_passes)
        )
    if dataset == "BFCL":
        st.markdown("**期望 vs 实际**")
        st.write(f"- 期望函数：`{row.get('expected_name') or '—'}`")
        st.write(f"- 实际调用：{_call_names(row) or '（未调用）'}")
        st.json(
            {
                "expected_args": row.get("expected_args") or {},
                "calls": row.get("calls") or [],
            },
            expanded=False,
        )
    else:
        mrr = row.get("mrr")
        mrr_text = f"{float(mrr):.3f}" if isinstance(mrr, (int, float)) else "—"
        st.markdown("**问题与检索**")
        st.write(f"- 问题：{short_text(row.get('question'), 200) or '—'}")
        st.write(f"- Hit：{'✅' if row.get('hit') else '❌'} ｜ MRR：{mrr_text}")
        st.json({"calls": row.get("calls") or []}, expanded=False)
    st.markdown("**回答片段**")
    st.write(short_text(row.get("answer"), 500) or "（空）")


def _pass_label(passed: int, total: int) -> str:
    if not total:
        return "—"
    return f"{passed}/{total}（{passed / total:.0%}）"


def _pass_delta(pass_a: int, total_a: int, pass_b: int, total_b: int) -> str:
    if not total_a or not total_b:
        return "—"
    delta_pp = (pass_b / total_b - pass_a / total_a) * 100
    if total_a == total_b:
        return f"{pass_b - pass_a:+d} 条 / {delta_pp:+.1f}pp"
    return f"{delta_pp:+.1f}pp（样本 {total_a}→{total_b}）"


def _mean_delta(mean_a: Any, mean_b: Any) -> str:
    if mean_a is None or mean_b is None:
        return "—"
    try:
        return f"{(float(mean_b) - float(mean_a)) * 100:+.1f}pp"
    except (TypeError, ValueError):
        return "—"


def _ab_delta_rows(a_summary: dict, b_summary: dict) -> list[dict]:
    rows = []
    for label, pass_key, total_key, mean_key in (
        ("BFCL", "bfcl_pass", "bfcl_total", "bfcl_mean"),
        ("RAG", "rag_pass", "rag_total", "rag_mean"),
    ):
        pass_a, total_a, mean_a = (
            a_summary[pass_key],
            a_summary[total_key],
            a_summary[mean_key],
        )
        pass_b, total_b, mean_b = (
            b_summary[pass_key],
            b_summary[total_key],
            b_summary[mean_key],
        )
        rows.append({
            "指标": f"{label} pass^k",
            "A": _pass_label(pass_a, total_a),
            "B": _pass_label(pass_b, total_b),
            "Δ (B-A)": _pass_delta(pass_a, total_a, pass_b, total_b),
        })
        rows.append({
            "指标": f"{label} mean",
            "A": _pct(mean_a, 1),
            "B": _pct(mean_b, 1),
            "Δ (B-A)": _mean_delta(mean_a, mean_b),
        })
    return rows


def _render_ab_compare(items: list[dict]) -> None:
    st.subheader("A/B 对比")
    if len(items) < 2:
        st.info("至少需要两个 iteration 文件才能做 A/B 对比。")
        return

    labels = [_item_label(item) for item in items]
    for key in ("opt-ab-a", "opt-ab-b"):
        if st.session_state.get(key) not in labels:
            st.session_state.pop(key, None)

    baseline = next(
        (item for item in items if str(item.get("name")) == "baseline"), items[0]
    )
    completed = [item for item in items if item.get("trials") is not None]
    default_b = completed[-1] if completed else items[-1]
    if default_b is baseline:
        default_b = next(
            (item for item in reversed(items) if item is not baseline), baseline
        )

    col_a, col_b = st.columns(2)
    a_label = col_a.selectbox(
        "基线 A", labels, index=labels.index(_item_label(baseline)), key="opt-ab-a"
    )
    b_label = col_b.selectbox(
        "对比 B", labels, index=labels.index(_item_label(default_b)), key="opt-ab-b"
    )
    st.caption(
        f"A = {a_label} ｜ B = {b_label} ｜ Δ = B - A；"
        "pass^k 同时给出条数与百分点。"
    )
    if a_label == b_label:
        st.info("A 和 B 是同一个迭代，请选择两个不同的迭代。")
        return

    a = items[labels.index(a_label)]
    b = items[labels.index(b_label)]
    a_summary = _summary(a)
    b_summary = _summary(b)
    st.dataframe(
        _ab_delta_rows(a_summary, b_summary),
        use_container_width=True,
        hide_index=True,
    )
    if a.get("trials") is None or b.get("trials") is None:
        st.caption("A 或 B 缺少 trials 字段，mean 可能来自旧格式近似值；差异仅供参考。")
    elif a.get("trials") != b.get("trials"):
        st.caption(
            f"注意：A/B 的 trials 不同（{a.get('trials')} vs {b.get('trials')}），"
            "请谨慎比较。"
        )

    a_map = _raw_cases(a)
    b_map = _raw_cases(b)
    common = sorted(set(a_map) & set(b_map), key=lambda ref: (ref[0], ref[1]))
    fixed = [
        ref for ref in common
        if not a_map[ref].get("passed") and b_map[ref].get("passed")
    ]
    regressed = [
        ref for ref in common
        if a_map[ref].get("passed") and not b_map[ref].get("passed")
    ]
    changed = [
        ref for ref in common
        if bool(a_map[ref].get("passed")) != bool(b_map[ref].get("passed"))
    ]

    cols = st.columns(3)
    cols[0].metric("共同 case", len(common))
    cols[1].metric("修复 A❌→B✅", len(fixed))
    cols[2].metric("回归 A✅→B❌", len(regressed))
    if not common:
        st.info("A/B 没有可对齐的共同 case（ID 集合不同）。")
        return

    with st.expander("查看修复 / 回归 case ID", expanded=bool(changed)):
        st.markdown(f"**修复**：{_ref_list(fixed)}")
        st.markdown(f"**回归**：{_ref_list(regressed)}")
        st.caption(
            "按 A/B 的逐条结果计算；iteration 文件里的 compare 字段通常对比基线，可能不同。"
        )
    st.caption(
        f"B 文件记录的 compare：修复 {len(b_summary['fixed'])}、"
        f"回归 {len(b_summary['regressed'])}；若与上方 A→B 计数不同，"
        "说明该字段对比的不是当前选择的 A。"
    )

    scopes = ["仅变化 case", "全部共同 case"] if changed else ["全部共同 case"]
    if st.session_state.get("opt-ab-scope") not in scopes:
        st.session_state.pop("opt-ab-scope", None)
    scope = st.radio(
        "逐条明细范围", scopes, horizontal=True, key="opt-ab-scope"
    )
    detail_refs = changed if scope == "仅变化 case" else common
    if not detail_refs:
        st.info("A/B 之间没有变化的 case。")
        return
    total = len(detail_refs)
    suffix = f"；仅展示前 {MAX_ROWS} 条" if total > MAX_ROWS else ""
    st.caption(f"逐条明细共 {total} 条{suffix}")

    for ref in detail_refs[:MAX_ROWS]:
        a_row, b_row = a_map[ref], b_map[ref]
        dataset, case_id = ref
        if ref in fixed:
            status = "修复"
        elif ref in regressed:
            status = "回归"
        else:
            status = "未变化"
        icon = "✅" if b_row.get("passed") else "❌"
        with st.expander(f"{icon} {status} · {dataset} · {case_id}"):
            st.caption(f"A：{_pass_text(a_row)} ｜ B：{_pass_text(b_row)}")
            col_b, col_a = st.columns(2)
            with col_b:
                st.markdown("**B（对比）**")
                _render_case_side(dataset, b_row)
            with col_a:
                st.markdown("**A（基线）**")
                _render_case_side(dataset, a_row)
            st.divider()
            st.markdown("**执行轨迹**")
            if not a_row.get("trace_id") and not b_row.get("trace_id"):
                st.caption("A/B 结果都没有 trace_id（旧版结果或未记录 trace）。")
            else:
                st.markdown("**B（对比）**")
                render_trace_timeline(b_row.get("trace_id"))
                st.markdown("**A（基线）**")
                render_trace_timeline(a_row.get("trace_id"))


def _render_report_download(report_text: str | None) -> None:
    if report_text and report_text.strip():
        st.download_button(
            "下载 report.md",
            data=report_text.encode("utf-8"),
            file_name="report.md",
            mime="text/markdown",
            key="download-report-md",
        )


def _load_iterations() -> tuple[list[dict], list[tuple[str, str]]]:
    items: list[dict] = []
    errors: list[tuple[str, str]] = []
    for path in _iteration_paths():
        data, error = load_json(path)
        if error:
            errors.append((path.name, error))
            continue
        if not isinstance(data, dict):
            errors.append((path.name, "期望 JSON 对象"))
            continue
        item = dict(data)
        item["_path"] = str(path)
        items.append(item)
    items.sort(key=lambda item: (_int(item.get("index"), 10**6), str(item.get("name", ""))))
    return items, errors


def optimization_kpis() -> dict:
    """总览页 KPI：最新已完成 iteration 的只读摘要，不渲染页面。"""
    items, errors = _load_iterations()
    completed = [item for item in items if item.get("trials") is not None]
    if not completed:
        return {
            "label": "暂无数据" if not items else "暂无已完成",
            "bfcl_text": "—",
            "rag_text": "—",
            "fixed_regressed_text": "—",
            "trials": "—",
            "errors": errors,
            "item_count": len(items),
            "completed": 0,
        }

    item = completed[-1]
    summary = _summary(item)

    def _pass_mean(passed: int, total: int, mean: Any) -> str:
        if not total:
            return "—"
        return f"{passed}/{total} · {_pct(mean, 1)}"

    return {
        "label": _short_item_label(item),
        "bfcl_text": _pass_mean(
            summary["bfcl_pass"], summary["bfcl_total"], summary["bfcl_mean"]
        ),
        "rag_text": _pass_mean(
            summary["rag_pass"], summary["rag_total"], summary["rag_mean"]
        ),
        "fixed_regressed_text": f"{len(summary['fixed'])} / {len(summary['regressed'])}",
        "trials": summary["trials"],
        "errors": errors,
        "item_count": len(items),
        "completed": len(completed),
    }


def _status_of(case_id: Any, fixed: set[str], regressed: set[str], unchanged: set[str]) -> str:
    key = str(case_id)
    if key in fixed:
        return "修复"
    if key in regressed:
        return "回归"
    if key in unchanged:
        return "未变化"
    return "—"


def _case_rows(item: dict, summary: dict) -> list[dict]:
    fixed = set(summary["fixed"])
    regressed = set(summary["regressed"])
    unchanged = set(summary["unchanged"])
    rows: list[dict] = []
    for row in _items_of(item, "bfcl_results"):
        calls = row.get("actual") or row.get("calls") or []
        actual = ", ".join(
            str(call.get("name", "")) for call in calls if isinstance(call, dict)
        )
        rows.append({
            "数据集": "BFCL",
            "ID": row.get("id"),
            "类别": row.get("kind") or "—",
            "结果": "✅ 通过" if row.get("passed") else "❌ 失败",
            "单次通过率": "—" if row.get("pass_rate") is None else _pct(row.get("pass_rate")),
            "失败类型": row.get("failure_type") or "",
            "对比": _status_of(row.get("id"), fixed, regressed, unchanged),
            "摘要": short_text(
                row.get("expected_name") or actual or row.get("question"), 70
            ),
            "_search": " ".join(str(part or "") for part in (
                row.get("id"),
                row.get("kind"),
                row.get("expected_name"),
                row.get("question"),
                actual,
                row.get("failure_type"),
            )),
        })
    for row in _items_of(item, "rag_results"):
        sources = row.get("retrieved_sources") or []
        rows.append({
            "数据集": "RAG",
            "ID": row.get("id"),
            "类别": row.get("question_type") or "—",
            "结果": "✅ 通过" if row.get("passed") else "❌ 失败",
            "单次通过率": "—" if row.get("pass_rate") is None else _pct(row.get("pass_rate")),
            "失败类型": row.get("failure_type") or "",
            "对比": _status_of(row.get("id"), fixed, regressed, unchanged),
            "摘要": short_text(row.get("question") or f"召回 {len(sources)} 条", 90),
            "_search": " ".join(str(part or "") for part in (
                row.get("id"),
                row.get("question_type"),
                row.get("question"),
                row.get("failure_type"),
            )),
        })
    return rows


def _overview_rows(items: list[dict]) -> list[dict]:
    rows = []
    for item in items:
        summary = _summary(item)
        rows.append({
            "#": item.get("index"),
            "配置": item.get("name"),
            "方向": item.get("direction"),
            "BFCL pass^k": f"{summary['bfcl_pass']}/{summary['bfcl_total']}",
            "BFCL mean": _pct(summary["bfcl_mean"], 1),
            "RAG pass^k": f"{summary['rag_pass']}/{summary['rag_total']}",
            "RAG mean": _pct(summary["rag_mean"], 1),
            "Trials": str(summary["trials"]),
            "状态": "已完成" if item.get("trials") is not None else "未含 trials",
            "修复": len(summary["fixed"]),
            "回归": len(summary["regressed"]),
            "样本": f"{summary['bfcl_total']}+{summary['rag_total']}",
        })
    return rows


def _render_overview_chart(items: list[dict]) -> None:
    chart_rows = []
    for item in items:
        summary = _summary(item)
        chart_rows.append({
            "迭代": f"#{_int(item.get('index'))}",
            "BFCL pass^k": _chart_pct(
                _rate(summary["bfcl_pass"], summary["bfcl_total"])
            ),
            "BFCL mean": _chart_pct(summary["bfcl_mean"]),
            "RAG pass^k": _chart_pct(
                _rate(summary["rag_pass"], summary["rag_total"])
            ),
            "RAG mean": _chart_pct(summary["rag_mean"]),
        })
    frame = pd.DataFrame(chart_rows).set_index("迭代")
    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    col_bfcl, col_rag = st.columns(2)
    with col_bfcl:
        st.caption("BFCL")
        st.bar_chart(
            frame[["BFCL pass^k", "BFCL mean"]],
            use_container_width=True,
            color=BFCL_COLORS,
            stack=False,
            x_label="迭代",
            y_label="通过率 (%)",
        )
    with col_rag:
        st.caption("RAG")
        st.bar_chart(
            frame[["RAG pass^k", "RAG mean"]],
            use_container_width=True,
            color=RAG_COLORS,
            stack=False,
            x_label="迭代",
            y_label="通过率 (%)",
        )
    st.caption(
        "pass^k = 所有 trial 都通过的 case 占比；mean = 单 trial 平均通过率；纵轴为百分比。"
        "BFCL 用蓝色系、RAG 用橙色系，深色为 pass^k、浅色为 mean。"
    )


def _render_failure_chart(bfcl: dict[str, int], rag: dict[str, int]) -> None:
    if not bfcl and not rag:
        st.success("本轮没有失败案例。")
        return
    failure_types = sorted(
        set(bfcl) | set(rag),
        key=lambda name: (
            -(bfcl.get(name, 0) + rag.get(name, 0)),
            -bfcl.get(name, 0),
            name,
        ),
    )
    rows = [
        {"失败类型": name, "数据集": dataset, "数量": counts.get(name, 0)}
        for name in failure_types
        for dataset, counts in (("BFCL", bfcl), ("RAG", rag))
    ]
    # 用显式 sort 固定“失败数降序”；st.bar_chart 无法直接指定分类排序。
    spec = {
        "mark": {"type": "bar"},
        "encoding": {
            "y": {
                "field": "失败类型",
                "type": "ordinal",
                "sort": {"field": "数量", "op": "sum", "order": "descending"},
                "axis": {"title": None, "labelLimit": 180, "grid": False},
            },
            "x": {
                "field": "数量",
                "type": "quantitative",
                "axis": {"title": "失败数", "tickMinStep": 1, "grid": True},
                "stack": False,
            },
            "yOffset": {"field": "数据集"},
            "color": {
                "field": "数据集",
                "type": "nominal",
                "scale": {"domain": ["BFCL", "RAG"], "range": FAILURE_COLORS},
                "legend": {"title": None, "orient": "bottom"},
            },
            "tooltip": [
                {"field": "失败类型", "type": "ordinal"},
                {"field": "数据集", "type": "nominal"},
                {"field": "数量", "type": "quantitative"},
            ],
        },
    }
    st.vega_lite_chart(pd.DataFrame(rows), spec, use_container_width=True)


def _render_cases(item: dict, summary: dict) -> None:
    rows = _case_rows(item, summary)
    if not rows:
        st.info("该迭代没有逐条 case 结果。")
        return

    query = st.text_input(
        "搜索 case",
        placeholder="输入 case ID、问题或期望函数片段",
        key="opt-case-search",
        help="不区分大小写，与下方筛选条件同时生效。",
    ).strip().casefold()

    families = sorted({row["类别"] for row in rows if row["类别"]})
    failure_types = sorted({row["失败类型"] for row in rows if row["失败类型"]})
    col_dataset, col_family, col_failure, col_passed = st.columns([1, 1.3, 1.3, 1])
    dataset = col_dataset.radio(
        "数据集", ["全部", "BFCL", "RAG"], horizontal=True, key="opt-dataset"
    )
    selected_families = col_family.multiselect("类别 / family", families, key="opt-families")
    selected_failures = col_failure.multiselect("失败类型", failure_types, key="opt-failures")
    passed = col_passed.radio(
        "结果", ["全部", "✅ 通过", "❌ 失败"], horizontal=True, key="opt-passed"
    )

    filtered = []
    for row in rows:
        if query and query not in str(row.get("_search") or "").casefold():
            continue
        if dataset != "全部" and row["数据集"] != dataset:
            continue
        if selected_families and row["类别"] not in selected_families:
            continue
        if selected_failures and row["失败类型"] not in selected_failures:
            continue
        if passed == "✅ 通过" and not row["结果"].startswith("✅"):
            continue
        if passed == "❌ 失败" and not row["结果"].startswith("❌"):
            continue
        filtered.append(row)

    display_rows = [
        {key: value for key, value in row.items() if key != "_search"}
        for row in filtered
    ]
    total = len(display_rows)
    suffix = f"；仅展示前 {MAX_ROWS} 条" if total > MAX_ROWS else ""
    st.caption(f"筛选后 {total} / {len(rows)} 条{suffix}")
    if not display_rows:
        st.info("没有符合筛选条件的 case。")
        return
    st.download_button(
        "下载筛选后 case CSV",
        data=rows_to_csv(display_rows),
        file_name="optimization_cases_filtered.csv",
        mime="text/csv",
        key="download-opt-cases",
        help="包含全部搜索 / 筛选结果，不受表格 200 行展示上限影响。",
    )
    st.dataframe(display_rows[:MAX_ROWS], use_container_width=True, hide_index=True)


def render_optimization() -> None:
    paths = _iteration_paths()
    latest = max((file_mtime(path) for path in paths if file_mtime(path)), default=None)
    report_stamp = file_mtime(REPORT_PATH)
    if paths:
        iteration_text = (
            f"`outputs/demo/iteration_*.json`（{len(paths)} 个，最新 {format_mtime(latest)}）"
        )
    else:
        iteration_text = "`outputs/demo/iteration_*.json`（缺失）"
    st.caption(
        "数据来源："
        + iteration_text
        + f" ｜ `outputs/demo/report.md`（{format_mtime(report_stamp)}）"
    )

    items, errors = _load_iterations()
    for name, error in errors:
        st.warning(f"跳过无法解析的 {name}：{error}")
    if paths:
        _render_run_status(paths, items)
    if not items:
        st.info("未找到优化循环结果。先在项目根目录运行：")
        st.code(GENERATE_CMD, language="bash")
        st.caption("生成后会写入 `outputs/demo/iteration_*.json` 与 `outputs/demo/report.md`。")
        report_text, report_error = load_text(REPORT_PATH)
        if report_error:
            st.warning(f"读取已有 report.md 失败：{report_error}")
        elif report_text is not None:
            _render_report_download(report_text)
            with st.expander("查看已有 report.md", expanded=True):
                st.markdown(report_text)
        return

    labels = [_item_label(item) for item in items]
    completed_items = [item for item in items if item.get("trials") is not None]
    default_item = completed_items[-1] if completed_items else items[-1]
    if st.session_state.get("opt-iteration") not in labels:
        st.session_state.pop("opt-iteration", None)
    selected_label = st.selectbox(
        "迭代 / 配置",
        labels,
        index=labels.index(_item_label(default_item)),
        key="opt-iteration",
        help="默认打开最新完成的迭代；表格保留全部迭代，走势图只展示已完成迭代。",
    )
    item = items[labels.index(selected_label)]
    summary = _summary(item)

    st.markdown(f"#### {_item_label(item)}")
    st.caption(
        f"方向：{item.get('direction') or '—'} ｜ "
        f"改动：{item.get('change') or '—'} ｜ "
        f"公开参考：{item.get('knowledge_ref') or '—'}"
    )

    cols = st.columns(6)
    cols[0].metric("BFCL pass^k", f"{summary['bfcl_pass']}/{summary['bfcl_total']}")
    cols[1].metric("BFCL mean", _pct(summary["bfcl_mean"], 1))
    cols[2].metric("RAG pass^k", f"{summary['rag_pass']}/{summary['rag_total']}")
    cols[3].metric("RAG mean", _pct(summary["rag_mean"], 1))
    cols[4].metric("Trials", str(summary["trials"]))
    cols[5].metric("修复 / 回归", f"{len(summary['fixed'])} / {len(summary['regressed'])}")

    legacy_items = [entry for entry in items if entry.get("trials") is None]
    if item.get("trials") is None:
        st.caption("当前迭代为旧格式（缺少 trials / mean），mean 以单 trial 结果近似。")
    elif legacy_items:
        st.caption(
            f"总览中有 {len(legacy_items)} 个旧格式迭代（缺少 trials / mean），"
            "其 mean 为近似值；走势图仅包含已完成迭代。"
        )

    st.subheader("迭代总览")
    st.dataframe(_overview_rows(items), use_container_width=True, hide_index=True)
    chart_items = completed_items or items
    st.markdown("**迭代走势**")
    if len(chart_items) < len(items):
        st.caption("走势图仅展示已包含 trials 的迭代，避免不同样本量的旧结果混入对比。")
    _render_overview_chart(chart_items)
    _render_ab_compare(items)

    st.subheader("失败归因")
    bfcl_failures = summary["bfcl_failures"]
    rag_failures = summary["rag_failures"]
    failure_rows = [
        {"数据集": "BFCL", "失败类型": name, "数量": count}
        for name, count in sorted(
            bfcl_failures.items(), key=lambda pair: (-pair[1], pair[0])
        )
    ] + [
        {"数据集": "RAG", "失败类型": name, "数量": count}
        for name, count in sorted(
            rag_failures.items(), key=lambda pair: (-pair[1], pair[0])
        )
    ]
    if failure_rows:
        st.dataframe(failure_rows, use_container_width=True, hide_index=True)
    st.caption("失败类型分布（按失败数降序；BFCL 蓝 / RAG 橙）")
    _render_failure_chart(bfcl_failures, rag_failures)

    st.markdown("**同类任务通过率**")
    same_class_rows = []
    for family, ratio in summary["same_class"].items():
        passed_count, total_count, rate = parse_ratio(ratio)
        same_class_rows.append({
            "类别": family,
            "通过 / 总数": ratio if total_count else ratio or "—",
            "通过率": _pct(rate) if rate is not None else "—",
        })
    if same_class_rows:
        st.dataframe(same_class_rows, use_container_width=True, hide_index=True)
    else:
        st.info("该迭代没有同类任务统计。")

    st.subheader("修复与回归")
    col_fixed, col_regressed = st.columns(2)
    with col_fixed:
        st.metric("修复 case", len(summary["fixed"]))
    with col_regressed:
        st.metric("回归 case", len(summary["regressed"]))
    with st.expander(
        "查看 case ID",
        expanded=bool(summary["fixed"] or summary["regressed"]),
    ):
        fixed_text = "、".join(f"`{case_id}`" for case_id in summary["fixed"]) or "无"
        regressed_text = "、".join(f"`{case_id}`" for case_id in summary["regressed"]) or "无"
        st.markdown(f"**修复**：{fixed_text}")
        st.markdown(f"**回归**：{regressed_text}")

    st.subheader("逐条 case")
    _render_cases(item, summary)

    st.subheader("优化报告")
    report_text, report_error = load_text(REPORT_PATH)
    if report_stamp and latest and report_stamp < latest:
        st.caption("注意：`report.md` 早于最新的 iteration 文件，内容可能尚未同步。")
    _render_report_download(report_text)
    with st.expander("查看 report.md", expanded=False):
        if report_error:
            st.error(f"读取 report.md 失败：{report_error}")
        elif report_text is None:
            st.info("未找到 `outputs/demo/report.md`。生成命令：")
            st.code(GENERATE_CMD, language="bash")
        elif not report_text.strip():
            st.info("`outputs/demo/report.md` 为空。")
        else:
            st.markdown(report_text)
