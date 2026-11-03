# -*- coding: utf-8 -*-
"""评测视图：把场景报告、成本/时延、公开基准和评测记录合到一个入口。

测评都绑定具体场景：行为/outcome 报告按当前场景过滤；成本/时延也按
trace 里的 scenario 过滤。公开基准是全局/模型级证据，单独放在一个 tab。
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.interfaces.dashboard.benchmarks import render_benchmarks
from core.interfaces.dashboard.common import (
    file_mtime,
    latest_agent_report,
    latest_outcome_report,
    load_cases_cached,
    load_json,
)
from core.interfaces.dashboard.cost import render_cost
from core.interfaces.dashboard.history import render_history
from core.interfaces.dashboard.layout import (
    Kpi,
    compact_table,
    empty_state,
    kpi_row,
    page_header,
    section,
    source_footer,
)
from core.quality.outcome_eval import load_outcome_cases
from core.quality.paths import OUTPUTS_DIR
from core.scenarios.registry import get_scenario

MODES = ["场景评测", "成本 / 时延", "公开基准", "评测记录"]


def _latest_json(pattern: str) -> tuple[dict | None, Path | None]:
    files = sorted(
        (path for path in OUTPUTS_DIR.glob(pattern) if path.is_file()),
        key=lambda path: file_mtime(path) or 0.0,
        reverse=True,
    )
    for path in files:
        data, _error = load_json(path)
        if isinstance(data, dict):
            return data, path
    return None, None


def _render_behavior_report(scenario_name: str, report: dict | None, path: Path | None) -> None:
    section("行为评测", "完整 Agent 跑 cases；pass^k = 所有 trial 都通过。")
    if report is None:
        empty_state(
            "当前场景还没有行为报告。",
            f"python -m core.quality.runner agent --scenario {scenario_name} --trials 3",
        )
        return
    summary = report.get("summary") or {}
    kpi_row(
        [
            Kpi("用例", str(summary.get("total", 0))),
            Kpi("pass^k", f"{summary.get('passed', 0)}/{summary.get('total', 0)}"),
            Kpi("trials", str(summary.get("trials", 1))),
            Kpi("mean", f"{float(summary.get('mean_pass_rate', 0)):.2f}"),
            Kpi("工具命中", f"{summary.get('tool_cases_ok', 0)}/{summary.get('total', 0)}"),
        ]
    )
    source_footer([(path, "行为报告")] if path else [])
    failed = [row for row in (report.get("results") or []) if isinstance(row, dict) and not row.get("passed")]
    if failed:
        compact_table(
            [
                {
                    "ID": row.get("id"),
                    "类别": row.get("category"),
                    "问题": str(row.get("question", ""))[:60],
                    "覆盖": f"{float(row.get('coverage') or 0):.0%}",
                    "工具": ", ".join(row.get("tool_names") or []) or "—",
                    "pass^k": "✅" if row.get("passed") else "❌",
                }
                for row in failed
            ],
            height=220,
            key=f"evaluation-behavior-failed-{scenario_name}",
        )


def _render_outcome_report(scenario_name: str, report: dict | None, path: Path | None) -> None:
    section("Outcome 评测", "不看回答文本，检查文件 / SQLite / 任务图 / 路由 trace。")
    if report is None:
        empty_state(
            "当前场景还没有 outcome 报告。",
            f"python -m core.quality.runner outcome --scenario {scenario_name} --trials 3",
        )
        return
    summary = report.get("summary") or {}
    kpi_row(
        [
            Kpi("用例", str(summary.get("total", 0))),
            Kpi("pass^k", f"{summary.get('passed', 0)}/{summary.get('total', 0)}"),
            Kpi("trials", str(summary.get("trials", 1))),
            Kpi("mean", f"{float(summary.get('mean_pass_rate', 0)):.2f}"),
            Kpi("断言", f"{summary.get('checks_ok', 0)}/{summary.get('checks_total', 0)}"),
        ]
    )
    source_footer([(path, "Outcome 报告")] if path else [])
    failed = [row for row in (report.get("results") or []) if isinstance(row, dict) and not row.get("passed")]
    if failed:
        rows = []
        for row in failed:
            checks = row.get("checks") or []
            reason = "；".join(
                str(check.get("reason", "")) for check in checks if not check.get("ok")
            )
            rows.append({
                "ID": row.get("id"),
                "pass^k": "❌",
                "mean": f"{float(row.get('pass_rate') or 0):.2f}",
                "失败 check": reason[:120],
            })
        compact_table(rows, height=220, key=f"evaluation-outcome-failed-{scenario_name}")


def _render_router_experiment() -> None:
    data, path = _latest_json("experiments/planner_eval_*.json")
    if data is None:
        return
    summaries = data.get("summaries") or {}
    section("相关实验：Planning Policy A/B", "12 条路由；baseline = 模型自主，policy = 确定性注入。")
    rows = []
    for name in ("baseline", "policy"):
        item = summaries.get(name) or {}
        rows.append({
            "变体": name,
            "准确率": f"{float(item.get('accuracy', 0)):.1%}",
            "正确": f"{item.get('correct', 0)}/{item.get('total', 0)}",
            "abstain": f"{float(item.get('abstain_rate', 0)):.0%}",
            "平均模型调用": f"{float(item.get('avg_model_calls', 0)):.2f}",
        })
    compact_table(rows, height=150, key="evaluation-planner-table")
    source_footer([(path, "Planner A/B")] if path else [])


def _render_trigger_experiment() -> None:
    data, path = _latest_json("experiments/trigger_rate_*.json")
    if data is None:
        return
    summaries = data.get("summaries") or {}
    section("相关实验：Subagent 触发率", "10 条 coding 任务；natural/routed 是 prompt，policy 是确定性委派。")
    rows = []
    for name in ("natural", "routed", "policy"):
        item = summaries.get(name) or {}
        rows.append({
            "变体": name,
            "subagent": f"{item.get('subagent_runs', 0)}/{item.get('total', 0)}",
            "任务工具": f"{item.get('task_runs', 0)}/{item.get('total', 0)}",
            "eligible": f"{item.get('eligible_triggered', 0)}/{item.get('eligible_runs', 0)}",
        })
    compact_table(rows, height=170, key="evaluation-trigger-table")
    source_footer([(path, "触发率")] if path else [])


def _render_scenario_eval(scenario_name: str) -> None:
    scenario = get_scenario(scenario_name)
    cases, _cases_error = load_cases_cached(scenario.cases_path)
    behavior, behavior_path = latest_agent_report(
        scenario_name,
        expected_total=len(cases) if cases else None,
    )
    outcome_cases = []
    if scenario.cases_path:
        outcome_path = Path(scenario.cases_path).with_name("outcome_cases.jsonl")
        if outcome_path.exists():
            outcome_cases = load_outcome_cases(outcome_path)
    outcome, outcome_path = latest_outcome_report(
        scenario_name,
        expected_total=len(outcome_cases) if outcome_cases else None,
    )

    _render_behavior_report(scenario_name, behavior, behavior_path)
    _render_outcome_report(scenario_name, outcome, outcome_path)
    if scenario_name == "router":
        _render_router_experiment()
    elif scenario_name == "coding_demo":
        _render_trigger_experiment()


def render_evaluation(scenario_name: str) -> None:
    page_header(
        "评测",
        f"当前场景：{scenario_name}；场景报告、成本/时延、公开基准和评测记录合在一个入口。",
        meta="数据视图只读已有报告，不触发模型调用。",
    )
    mode = st.radio("评测视图", MODES, horizontal=True, key="evaluation-mode")
    if mode == "场景评测":
        _render_scenario_eval(scenario_name)
    elif mode == "成本 / 时延":
        render_cost(embedded=True, scenario_name=scenario_name)
    elif mode == "公开基准":
        render_benchmarks(embedded=True)
    else:
        render_history(embedded=True, scenario_name=scenario_name)
