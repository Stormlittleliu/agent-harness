# -*- coding: utf-8 -*-
"""总览工作台：KPI、视图入口、最近报告与能力矩阵。

总览不加载 Agent；进入架构 / 任务 / 用例 / 运行窗口时才初始化模型与工具。
"""
from __future__ import annotations

import streamlit as st

from core.interfaces.dashboard.catalog import catalog_kpis
from core.interfaces.dashboard.common import (
    ROOT,
    latest_agent_report,
    load_cases_cached,
    short_text,
)
from core.interfaces.dashboard.layout import (
    Kpi,
    compact_table,
    empty_state,
    kpi_row,
    navigate,
    page_header,
    section,
    source_footer,
)
from core.interfaces.dashboard.optimization import optimization_kpis

_VIEW_HINTS = {
    "architecture": "场景、工具、中间件顺序、工作流与对象源码",
    "task": "输入任务，查看回答、工具调用、trace 与 HITL",
    "tests": "案例列表 + 判定 / 对象链路 / 原始数据",
    "runtime": "任务图、任务详情与命令日志",
    "evaluation": "场景报告 + 成本/时延 + 公开基准 + 评测记录",
    "benchmarks": "BFCL / RGB / MultiHop / τ² 的已有报告",
    "optimization": "5 轮优化走势、A/B 与失败归因",
    "catalog": "8 个来源、320 条统一样例与执行方式",
    "cost": "成功率、p50/p95、token 与估算成本",
    "history": "浏览 outputs/ 下的报告、Markdown 与 trace",
}

_CAPABILITIES = [
    {"能力": "Tool Calling", "状态": "✅ 已验证", "证据": "8 场景 / 40+ 工具 + 参数校验 + 错误回注 + 重试"},
    {"能力": "Planning / 路由", "状态": "✅ 已验证", "证据": "确定性 policy；12 条路由 12/12，1 条 abstain 后模型兜底"},
    {"能力": "Outcome 评测", "状态": "✅ 已验证", "证据": "12 条文件 / SQLite / 任务图 / 路由 trace 断言"},
    {"能力": "RAG", "状态": "✅ 已验证", "证据": "BGE + Chroma + 向量/BM25 混合检索"},
    {"能力": "权限 / HITL", "状态": "✅ 已验证", "证据": "allow/deny + reset_device 审批"},
    {"能力": "上下文 / 预算", "状态": "✅ 已验证", "证据": "压缩 + 工具调用上限 + token 预算"},
    {"能力": "可观测性", "状态": "✅ 已验证", "证据": "trace + 成本/时延报告"},
    {"能力": "结构化输出", "状态": "✅ 已验证", "证据": "Pydantic ReportSchema 5/5"},
    {"能力": "任务图 / Subagent", "状态": "🟡 部分", "证据": "机制可用；自然任务 0/10，policy eligible 3/10 → 3/3"},
    {"能力": "MCP", "状态": "🟡 部分", "证据": "stdio Memory + Fetch；无 HTTP/SSE/auth"},
    {"能力": "多 Agent", "状态": "🟡 部分", "证据": "research 只读 fan-out；无 handoff / 治理"},
    {"能力": "多模态", "状态": "— 缺口", "证据": "无语音 / 图像 / OCR / 端侧"},
]


def _catalog_text(tasks: int | None, sources: int | None) -> str:
    task_text = f"{tasks:,}" if tasks is not None else "—"
    source_text = f"{sources:,}" if sources is not None else "—"
    return f"{task_text} / {source_text}"


def render_overview_kpis() -> None:
    """4 个只读 KPI；详细筛选见「优化循环」「Benchmark 目录」。"""
    opt = optimization_kpis()
    cat = catalog_kpis()
    kpi_row(
        [
            Kpi("最新完成迭代", opt["label"], "按 iteration 序号取最新一个包含 trials 的结果。"),
            Kpi("BFCL pass^k / mean", opt["bfcl_text"], "pass^k = 所有 trial 都通过的 case 占比。"),
            Kpi("RAG pass^k / mean", opt["rag_text"], "pass^k = 所有 trial 都通过的 case 占比。"),
            Kpi("目录任务 / 来源", _catalog_text(cat["tasks"], cat["sources"]), "catalog.jsonl 任务数 / 来源数。"),
        ]
    )
    notes = []
    if opt["errors"]:
        notes.append(f"{len(opt['errors'])} 个优化文件无法解析")
    if cat["errors"]:
        notes.append("目录文件读取异常")
    if cat["skipped"]:
        notes.append(f"目录跳过 {cat['skipped']} 行坏数据")
    caption = f"最新修复 / 回归：{opt['fixed_regressed_text']}。KPI 只读汇总，不触发模型调用。"
    if notes:
        caption += " " + "；".join(notes) + "。"
    st.caption(caption)


def _render_launcher(views: list[str], labels: dict[str, str]) -> None:
    section("快速入口", "只渲染点击后的视图；总览不会一次性初始化所有页面。")
    cols = st.columns(4, gap="small")
    for index, view in enumerate(views):
        with cols[index % 4]:
            # 固定卡片高度，避免不同长度的说明把“打开”按钮挤到不同位置。
            with st.container(border=True, height=170):
                st.markdown(f"**{labels.get(view, view)}**")
                st.caption(_VIEW_HINTS.get(view, "打开视图"))
                st.button(
                    "打开",
                    key=f"overview-launch-{view}",
                    on_click=navigate,
                    args=(view,),
                    use_container_width=True,
                )


def _render_latest_report(scenario_name: str) -> None:
    section("行为报告", "来自 outputs/agent；优先选用例数匹配的完整报告，不调用模型。")
    cases_path = ROOT / "core" / "scenarios" / scenario_name / "cases.jsonl"
    cases, _cases_error = load_cases_cached(cases_path)
    report, path = latest_agent_report(
        scenario_name,
        expected_total=len(cases) if cases else None,
    )
    if report is None or path is None:
        empty_state(
            "该场景还没有行为报告。运行一次后即可在这里查看逐条结果与对象链路。",
            f"python -m core.quality.runner agent --scenario {scenario_name}",
        )
        return

    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    kpi_row(
        [
            Kpi("用例", str(summary.get("total", "—"))),
            Kpi("pass^k", f"{summary.get('passed', 0)}/{summary.get('total', 0)}"),
            Kpi("trials / mean", f"{summary.get('trials', 1)} / {float(summary.get('mean_pass_rate', 0)):.2f}"),
            Kpi("工具命中", f"{summary.get('tool_cases_ok', 0)}/{summary.get('total', 0)}"),
        ]
    )
    source_footer([(path, "行为报告")])
    st.button(
        "查看完整用例与对象链路",
        key="overview-open-tests",
        on_click=navigate,
        args=("tests",),
    )

    results = [row for row in (report.get("results") or []) if isinstance(row, dict)]
    failed = [row for row in results if not row.get("passed")]
    if failed:
        st.markdown("**失败案例**")
        compact_table(
            [
                {
                    "ID": row.get("id"),
                    "类别": row.get("category"),
                    "问题": short_text(row.get("question"), 60),
                    "覆盖": f"{float(row.get('coverage') or 0):.0%}",
                    "工具": ", ".join(row.get("tool_names") or []) or "—",
                }
                for row in failed
            ],
            height=220,
            key="overview-failed-table",
        )
    else:
        st.caption("最近一次报告没有失败案例。")


def render_overview(scenario_name: str, views: list[str], labels: dict[str, str]) -> None:
    page_header(
        "工作台",
        "从任一视图开始；总览只读 KPI、最近报告与能力矩阵，不加载 Agent。",
        meta="视图只读已有文件，运行任务 / 用例才会调用模型。",
    )
    render_overview_kpis()
    _render_launcher(views, labels)
    _render_latest_report(scenario_name)

    section("能力矩阵", "✅ 已验证 · 🟡 机制可用但行为未稳定 · — 明确缺口")
    compact_table(
        _CAPABILITIES,
        height=300,
        key="overview-capability-table",
        column_order=["能力", "状态", "证据"],
    )
