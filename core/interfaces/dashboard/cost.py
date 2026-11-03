# -*- coding: utf-8 -*-
"""成本 / 时延视图：聚合本地 trace，展示成功率、p50/p95、token 与估算成本。"""
from __future__ import annotations

import streamlit as st

from core.interfaces.dashboard.common import ROOT, display_path
from core.interfaces.dashboard.layout import (
    Kpi,
    compact_table,
    empty_state,
    kpi_row,
    master_detail,
    page_header,
    section,
    source_footer,
)
from core.observability.cost_report import build_report, summarize

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


def _duration(value) -> str:
    """累计时延用分钟/小时，避免 10362.56s 这种读数。"""
    if value is None:
        return "—"
    number = float(value)
    if number >= 3_600_000:
        return f"{number / 3_600_000:.2f}h"
    if number >= 60_000:
        return f"{number / 60_000:.1f}min"
    return _ms(number)


def _cost(value) -> str:
    return f"¥{float(value or 0):.4f}"


def _pct(value) -> str:
    return f"{float(value or 0):.1%}"


def render_cost(embedded: bool = False, scenario_name: str | None = None) -> None:
    """成本 / 时延；embedded=True 时嵌入评测页，scenario_name 过滤到单个场景。"""
    title = "成本 / 时延"
    description = "聚合 `outputs/traces/trace_*.jsonl`；只读已有 trace，不触发模型调用。"
    signature = _signature()
    if not signature:
        if not embedded:
            page_header(title, description)
        empty_state("未找到 trace 文件；先运行一次 Agent 或评测。")
        return

    report = _load_report(signature)
    runs = report.get("runs") or []
    if scenario_name:
        runs = [run for run in runs if run.get("scenario") == scenario_name]
    summary = summarize(runs) if scenario_name else (report.get("summary") or {})
    if not summary.get("runs"):
        if not embedded:
            page_header(title, description)
        empty_state(f"场景 `{scenario_name}` 还没有可聚合的 trace。")
        return

    generated = str(summary.get("generated_at") or "—").replace("T", " ")[:16]
    meta = f"{summary.get('runs', 0):,} 条 run · 生成于 {generated}"
    if scenario_name:
        meta += f" · 场景 {scenario_name}"
    if not embedded:
        page_header(title, description, meta=meta)
    else:
        st.caption(meta)
    toolbar = st.columns([6, 1], gap="small")
    if toolbar[1].button(
        "重新读取 trace",
        key=f"cost-refresh-{scenario_name or 'all'}",
        use_container_width=True,
    ):
        _load_report.clear()
        st.rerun()
    source_footer([(TRACE_DIR, "trace 目录")])

    kpi_row(
        [
            Kpi("Run", f"{summary.get('runs', 0):,}"),
            Kpi("成功率", f"{float(summary.get('success_rate', 0)):.1%}"),
            Kpi("p50", _ms(summary.get("duration_p50_ms"))),
            Kpi("p95", _ms(summary.get("duration_p95_ms"))),
            Kpi("平均 Token", f"{float(summary.get('avg_tokens', 0)):,.0f}"),
            Kpi("估算成本", _cost(summary.get("cost_est"))),
        ]
    )

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
    st.caption(f"数据目录：`{display_path(TRACE_DIR)}`")

    if summary.get("error_runs"):
        st.caption(
            f"含错误 run：{summary['error_runs']}（其中模型错误 {summary.get('model_error_runs', 0)}）。"
            "这些 run 的模型调用可能失败，但仍可能被 run_end 标记为 completed。"
        )
    if (summary.get("by_model") or {}).get("unknown"):
        st.caption(
            "`unknown` 表示该 run 既没有成功的 model_end，也没有可用的 model_start 模型名；"
            "通常是极旧 trace 或空 run。"
        )

    breakdown = summary.get("latency_breakdown") or {}
    if breakdown:
        section("时延拆解", "按 trace 事件区间合并；其他 = 总时延 - 模型/工具 active 时间。")
        kpi_row(
            [
                Kpi(
                    "模型调用",
                    f"{_duration(breakdown.get('model_ms'))} · {_pct(breakdown.get('model_pct'))}",
                    help=f"p50 {_ms(breakdown.get('model_p50_ms'))} / p95 {_ms(breakdown.get('model_p95_ms'))}",
                ),
                Kpi(
                    "工具调用",
                    f"{_duration(breakdown.get('tool_ms'))} · {_pct(breakdown.get('tool_pct'))}",
                    help=f"p50 {_ms(breakdown.get('tool_p50_ms'))} / p95 {_ms(breakdown.get('tool_p95_ms'))}",
                ),
                Kpi(
                    "工具内模型 / 重叠",
                    f"{_duration(breakdown.get('overlap_ms'))} · {_pct(breakdown.get('overlap_pct'))}",
                    help="工具执行期间发生的模型调用；已从模型/工具单列中扣除，避免重复计时。",
                ),
                Kpi(
                    "其他 / 编排",
                    f"{_duration(breakdown.get('other_ms'))} · {_pct(breakdown.get('other_pct'))}",
                    help="中间件、checkpoint、排队、未埋点等 wall-clock 余量。",
                ),
            ]
        )
        compact_table(
            [
                {
                    "部分": "模型调用",
                    "累计": _duration(breakdown.get("model_ms")),
                    "占比": _pct(breakdown.get("model_pct")),
                    "p50": _ms(breakdown.get("model_p50_ms")),
                    "p95": _ms(breakdown.get("model_p95_ms")),
                },
                {
                    "部分": "工具调用",
                    "累计": _duration(breakdown.get("tool_ms")),
                    "占比": _pct(breakdown.get("tool_pct")),
                    "p50": _ms(breakdown.get("tool_p50_ms")),
                    "p95": _ms(breakdown.get("tool_p95_ms")),
                },
                {
                    "部分": "工具内模型 / 重叠",
                    "累计": _duration(breakdown.get("overlap_ms")),
                    "占比": _pct(breakdown.get("overlap_pct")),
                    "p50": "—",
                    "p95": "—",
                },
                {
                    "部分": "其他 / 编排",
                    "累计": _duration(breakdown.get("other_ms")),
                    "占比": _pct(breakdown.get("other_pct")),
                    "p50": _ms(breakdown.get("other_p50_ms")),
                    "p95": _ms(breakdown.get("other_p95_ms")),
                },
            ],
            height=220,
            key="cost-breakdown-table",
        )

        tool_latency_rows = [
            {"工具": name, "累计时延": _duration(item.get("ms")), "调用次数": item.get("calls", 0)}
            for name, item in (summary.get("by_tool_latency") or {}).items()
        ]
        model_latency_rows = [
            {"模型": name, "累计时延": _duration(item.get("ms")), "调用次数": item.get("calls", 0)}
            for name, item in (summary.get("by_model_latency") or {}).items()
        ]
        col_tool, col_model = st.columns(2, gap="medium")
        with col_tool:
            section("按工具时延", "累计调用时延；并发/嵌套时可能大于 wall-clock，占比看上方拆解表。")
            compact_table(tool_latency_rows, height=260, key="cost-tool-latency-table")
        with col_model:
            section("按模型时延", "累计调用时延；模型错误也会计入。")
            compact_table(model_latency_rows, height=260, key="cost-model-latency-table")

    left, right = master_detail(0.48)
    with left:
        section("按模型")
        model_rows = [
            {
                "模型": model,
                "Run / 成功 / 错误": f"{item.get('runs', 0)} / {item.get('completed', 0)} / {item.get('errors', 0)}",
                "Token": f"{int(item.get('tokens', 0)):,}",
                "估算成本": _cost(item.get("cost_est")),
            }
            for model, item in (summary.get("by_model") or {}).items()
        ]
        compact_table(
            model_rows,
            height=240,
            key="cost-model-table",
            column_order=["模型", "Run / 成功 / 错误", "Token", "估算成本"],
        )

        section("工具调用分布")
        tool_rows = [
            {"工具": tool, "调用次数": count}
            for tool, count in (summary.get("by_tool") or {}).items()
        ]
        compact_table(tool_rows, height=220, key="cost-tool-table")

    with right:
        section("最近 Run", "按 trace_id 查看场景、状态、模型/工具调用与成本。")
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
                "错误": len(run.get("errors") or []),
            }
            for run in (report.get("runs") or [])
        ]
        compact_table(
            run_rows,
            height=360,
            key="cost-run-table",
            column_order=["Trace", "场景", "状态", "成本", "延迟", "错误"],
            column_config={
                "Trace": st.column_config.TextColumn(width="medium"),
                "场景": st.column_config.TextColumn(width="small"),
                "状态": st.column_config.TextColumn(width="small"),
                "成本": st.column_config.TextColumn(width="small"),
                "延迟": st.column_config.TextColumn(width="small"),
                "错误": st.column_config.NumberColumn(width="small"),
            },
        )

        with st.expander("单条 Run 时延拆解", expanded=False):
            runs = (report.get("runs") or [])[:200]
            run_options = {
                f"{run.get('trace_id')} · {run.get('scenario') or '—'} · {_ms(run.get('duration_ms'))}": run
                for run in runs
            }
            if not run_options:
                st.caption("没有可选择的 run。")
            else:
                label = st.selectbox("选择 Run", list(run_options), key="cost-run-breakdown")
                run = run_options[label]
                item = run.get("latency_breakdown")
                if not item:
                    st.caption("该 run 缺少可重建的 start/end 时间区间。")
                else:
                    total = float(item.get("total_ms") or 0)
                    def _share(value) -> str:
                        return f"{float(value or 0) / total:.1%}" if total else "—"
                    st.caption(
                        f"总 {_ms(total)} ｜ "
                        f"模型 {_ms(item.get('model_ms'))} ({_share(item.get('model_ms'))}) ｜ "
                        f"工具 {_ms(item.get('tool_ms'))} ({_share(item.get('tool_ms'))}) ｜ "
                        f"重叠 {_ms(item.get('overlap_ms'))} ({_share(item.get('overlap_ms'))}) ｜ "
                        f"其他 {_ms(item.get('other_ms'))} ({_share(item.get('other_ms'))})"
                    )
                    compact_table(
                        [
                            {"部分": "模型调用", "时延": _ms(item.get("model_ms")), "占比": _share(item.get("model_ms"))},
                            {"部分": "工具调用", "时延": _ms(item.get("tool_ms")), "占比": _share(item.get("tool_ms"))},
                            {"部分": "重叠", "时延": _ms(item.get("overlap_ms")), "占比": _share(item.get("overlap_ms"))},
                            {"部分": "其他 / 编排", "时延": _ms(item.get("other_ms")), "占比": _share(item.get("other_ms"))},
                        ],
                        height=180,
                        key="cost-run-breakdown-table",
                    )
                    col_model, col_tool = st.columns(2, gap="small")
                    with col_model:
                        compact_table(
                            [
                                {"模型": name, "时延": _ms(value)}
                                for name, value in (run.get("model_latency") or {}).items()
                            ],
                            height=160,
                            key="cost-run-model-latency",
                            empty="没有模型区间。",
                        )
                    with col_tool:
                        compact_table(
                            [
                                {"工具": name, "时延": _ms(value)}
                                for name, value in (run.get("tool_latency") or {}).items()
                            ],
                            height=160,
                            key="cost-run-tool-latency",
                            empty="没有工具区间。",
                        )
