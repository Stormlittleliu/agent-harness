# -*- coding: utf-8 -*-
"""成本 / 时延视图：聚合本地 trace，展示成功率、p50/p95、token 与估算成本。"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.interfaces.dashboard.common import ROOT, display_path
from core.observability.cost_report import build_report

TRACE_DIR = ROOT / "outputs" / "traces"


def _signature() -> tuple[tuple[str, float, int], ...]:
    items: list[tuple[str, float, int]] = []
    for path in sorted(TRACE_DIR.glob("trace_*.jsonl")):
        try:
            stat = path.stat()
        except OSError:
            continue
        items.append((str(path), stat.st_mtime, stat.st_size))
    return tuple(items)


@st.cache_data(show_spinner=False, max_entries=4)
def _load_report(signature: tuple[tuple[str, float, int], ...]) -> dict:
    # signature 只用于让缓存失效；实际读取仍由 build_report 完成。
    _ = signature
    return build_report(TRACE_DIR)


def _ms(value) -> str:
    if value is None:
        return "—"
    number = float(value)
    return f"{number / 1000:.2f}s" if number >= 1000 else f"{number:.0f}ms"


def _cost(value) -> str:
    return f"¥{float(value or 0):.4f}"


def render_cost() -> None:
    st.subheader("成本 / 时延")
    st.caption(
        "聚合 `outputs/traces/trace_*.jsonl`；只读已有 trace，不触发模型调用。"
    )
    signature = _signature()
    if not signature:
        st.info("未找到 trace 文件；先运行一次 Agent 或评测。")
        return

    report = _load_report(signature)
    summary = report.get("summary") or {}
    if not summary.get("runs"):
        st.info("trace 中没有可聚合的 run。")
        return

    st.caption(
        f"数据目录：`{display_path(TRACE_DIR)}` · "
        f"{summary.get('runs', 0)} 条 run · 生成于 {summary.get('generated_at', '—')}"
    )

    cols = st.columns(6)
    cols[0].metric("Run", f"{summary.get('runs', 0):,}")
    cols[1].metric("成功率", f"{float(summary.get('success_rate', 0)):.1%}")
    cols[2].metric("p50", _ms(summary.get("duration_p50_ms")))
    cols[3].metric("p95", _ms(summary.get("duration_p95_ms")))
    cols[4].metric("平均 Token", f"{float(summary.get('avg_tokens', 0)):,.0f}")
    cols[5].metric("估算成本", _cost(summary.get("cost_est")))

    if not summary.get("pricing_configured"):
        st.warning(
            "`config/observability.yml` 的 `pricing` 未匹配模型，成本为 0；"
            "Token 和时延仍然有效。"
        )
    else:
        st.caption(
            f"平均成本/run：{_cost(summary.get('avg_cost'))} ｜ "
            f"每个成功 run：{_cost(summary.get('cost_per_success'))} ｜ "
            "价格是本地估算，不是账单。"
        )

    st.markdown("**按模型**")
    model_rows = [
        {
            "模型": model,
            "Run": item.get("runs", 0),
            "成功": item.get("completed", 0),
            "Token": f"{int(item.get('tokens', 0)):,}",
            "估算成本": _cost(item.get("cost_est")),
            "p50": _ms(item.get("p50_ms")),
            "p95": _ms(item.get("p95_ms")),
        }
        for model, item in (summary.get("by_model") or {}).items()
    ]
    st.dataframe(model_rows, use_container_width=True, hide_index=True)

    st.markdown("**最近 Run**")
    run_rows = [
        {
            "Trace": run.get("trace_id"),
            "场景": run.get("scenario") or "—",
            "状态": run.get("status"),
            "模型": run.get("model"),
            "模型/工具": f"{run.get('model_calls', 0)}/{run.get('tool_calls', 0)}",
            "Token": f"{int(run.get('total_tokens', 0)):,}",
            "成本": _cost(run.get("cost_est")),
            "延迟": _ms(run.get("duration_ms")),
        }
        for run in (report.get("runs") or [])[:200]
    ]
    st.dataframe(run_rows, use_container_width=True, hide_index=True)

    with st.expander("工具调用分布"):
        tool_rows = [
            {"工具": tool, "调用次数": count}
            for tool, count in (summary.get("by_tool") or {}).items()
        ]
        st.dataframe(tool_rows, use_container_width=True, hide_index=True)

    if st.button("重新读取 trace", key="cost-refresh"):
        _load_report.clear()
        st.rerun()
