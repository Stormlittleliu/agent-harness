# -*- coding: utf-8 -*-
"""公开基准视图：BFCL、RGB / MultiHop、τ²-bench 的已有报告。

每个 benchmark 一个模式，避免三段纵向堆叠；表格固定高度，Tau2 明细
改为选择式右侧详情，不再渲染 200 个 expander。
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from core.interfaces.dashboard.common import ROOT, load_json, to_float
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

BFCL_RESULTS = ROOT / "outputs" / "bfcl" / "eval_bfcl.json"
PUBLIC_RESULTS = ROOT / "outputs" / "public" / "eval_public_results.json"
TAU2_RESULTS = ROOT / "outputs" / "tau2" / "results.json"


def _read_report(path: Path, name: str) -> dict | None:
    data, error = load_json(path)
    if error:
        st.error(f"读取 {name} 失败：{error}")
        return None
    if data is None:
        return None
    if not isinstance(data, dict):
        st.error(f"{name} 格式异常：期望 JSON 对象。")
        return None
    return data


def _join_list(value, limit: int = 50) -> str:
    if isinstance(value, list):
        text = ", ".join(str(item) for item in value)
    else:
        text = str(value or "")
    return text[:limit] or "-"


def _bfcl_passed(row: dict) -> bool:
    if row.get("kind") == "irrelevance":
        return not (row.get("actual") or [])
    return bool(row.get("name_ok") and row.get("args_ok") and row.get("exact"))


def _adapter_note(path: str) -> None:
    st.caption(f"适配器：`{path}` · 只读已有报告，不重跑。")


def _render_bfcl() -> None:
    data = _read_report(BFCL_RESULTS, "BFCL 结果")
    if data is None:
        empty_state(
            "未找到 BFCL 报告。",
            "python -m core.quality.runner bfcl --simple 100 --irrelevance 100",
        )
        return

    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    section("BFCL v4 抽样", "函数选择 / 参数 exact / 无关请求不调用；简化评分，不是官方 AST 分数。")
    kpi_row(
        [
            Kpi("函数选择", f"{summary.get('simple_name_ok', 0)}/{summary.get('simple_total', 0)}"),
            Kpi("参数 exact", f"{summary.get('simple_exact', 0)}/{summary.get('simple_total', 0)}"),
            Kpi("无关不调用", f"{summary.get('irrelevance_no_call', 0)}/{summary.get('irrelevance_total', 0)}"),
            Kpi("错误", str(summary.get("errors", 0))),
        ]
    )
    _adapter_note("core/benchmarks/adapters/bfcl.py")

    results = [row for row in (data.get("results") or []) if isinstance(row, dict)]
    if not results:
        empty_state("报告里没有逐条结果。")
        return
    kinds = sorted({str(row.get("kind", "")) for row in results})
    col_kind, col_status = st.columns(2, gap="small")
    kind = col_kind.radio("类型", ["全部"] + kinds, horizontal=True, key="bfcl-kind")
    status = col_status.radio("结果", ["全部", "✅ 通过", "❌ 失败"], horizontal=True, key="bfcl-status")

    rows = []
    for row in results:
        if kind != "全部" and str(row.get("kind", "")) != kind:
            continue
        passed = _bfcl_passed(row)
        if status == "✅ 通过" and not passed:
            continue
        if status == "❌ 失败" and passed:
            continue
        calls = row.get("actual") or []
        is_irrelevance = row.get("kind") == "irrelevance"
        rows.append({
            "ID": row.get("id"),
            "类型": row.get("kind"),
            "问题": (row.get("question") or "")[:70],
            "期望函数": row.get("expected_name") or "-",
            "实际调用": ", ".join(str(call.get("name", "")) for call in calls if isinstance(call, dict))
            or "（未调用）",
            "函数名": "—" if is_irrelevance else ("是" if row.get("name_ok") else "否"),
            "参数": "—" if is_irrelevance else ("是" if row.get("args_ok") else "否"),
            "结果": "通过" if passed else "失败",
            "错误": row.get("error") or "",
        })
    section("逐条结果", f"筛选后 {len(rows)} / {len(results)} 条")
    compact_table(
        rows,
        height=340,
        key="benchmarks-bfcl-table",
        column_order=["ID", "类型", "问题", "期望函数", "实际调用", "函数名", "参数", "结果", "错误"],
    )


def _render_public() -> None:
    data = _read_report(PUBLIC_RESULTS, "公开 RAG 结果")
    if data is None:
        empty_state(
            "未找到 RGB / MultiHop 报告。",
            "python -m core.quality.runner public --rgb-limit 20 --multihop-limit 0",
        )
        return

    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    section("RGB / MultiHop-RAG", "只评检索召回；拒答类不计入检索分。")
    if summary:
        items = []
        for name, item in summary.items():
            if not isinstance(item, dict):
                continue
            items.append(
                Kpi(
                    str(name),
                    f"Hit@4 {to_float(item.get('hit_at_4')):.0%} · MRR {to_float(item.get('mrr')):.3f}",
                    help=f"{item.get('scored', 0)} 条参与评分。",
                )
            )
        kpi_row(items, columns=2)
    else:
        st.caption("报告里没有汇总指标。")
    _adapter_note("core/benchmarks/adapters/rag.py · core/quality/public_sample.py")

    results = [row for row in (data.get("results") or []) if isinstance(row, dict)]
    if not results:
        empty_state("报告里没有逐条结果。")
        return
    benchmarks = sorted({str(row.get("benchmark", "")) for row in results})
    benchmark = st.radio("Benchmark", ["全部"] + benchmarks, horizontal=True, key="public-bench")

    rows = []
    for row in results:
        if benchmark != "全部" and str(row.get("benchmark", "")) != benchmark:
            continue
        hit = row.get("hit")
        mrr = row.get("mrr")
        rows.append({
            "ID": row.get("id"),
            "Benchmark": row.get("benchmark"),
            "类别": row.get("category"),
            "问题": (row.get("question") or "")[:70],
            "Hit@4": "—" if hit is None else ("✅" if hit else "❌"),
            "MRR": "—" if mrr is None else f"{to_float(mrr):.3f}",
            "期望来源": _join_list(row.get("expected_sources")),
            "召回来源": _join_list(row.get("retrieved_sources")),
        })
    section("逐条结果", f"筛选后 {len(rows)} / {len(results)} 条")
    compact_table(
        rows,
        height=340,
        key="benchmarks-public-table",
        column_order=["ID", "Benchmark", "类别", "问题", "Hit@4", "MRR", "期望来源", "召回来源"],
    )


def _tau2_counts(actions: list[dict], tool_type: str) -> tuple[int, int]:
    items = [action for action in actions if action.get("tool_type") == tool_type]
    return sum(1 for item in items if item.get("action_match")), len(items)


def _tau2_stats(sim: dict) -> dict:
    reward_info = sim.get("reward_info") if isinstance(sim.get("reward_info"), dict) else {}
    db_check = reward_info.get("db_check") if isinstance(reward_info.get("db_check"), dict) else {}
    actions = [item for item in (reward_info.get("action_checks") or []) if isinstance(item, dict)]
    nl = [item for item in (reward_info.get("nl_assertions") or []) if isinstance(item, dict)]
    return {
        "reward": reward_info.get("reward"),
        "db_match": db_check.get("db_match"),
        "read": _tau2_counts(actions, "read"),
        "write": _tau2_counts(actions, "write"),
        "generic": _tau2_counts(actions, "generic"),
        "nl": (sum(1 for item in nl if item.get("met")), len(nl)),
    }


def _render_tau2_detail(sim: dict, item: dict) -> None:
    st.markdown(f"**task `{sim.get('task_id')}`** · reward {item['reward']}")
    st.caption(f"终止：{sim.get('termination_reason') or '—'} · 耗时 {to_float(sim.get('duration')):.1f}s")
    reward_info = sim.get("reward_info") if isinstance(sim.get("reward_info"), dict) else {}
    nl = [entry for entry in (reward_info.get("nl_assertions") or []) if isinstance(entry, dict)]
    if nl:
        section("NL 断言")
        for assertion in nl:
            mark = "✅" if assertion.get("met") else "❌"
            st.markdown(f"- {mark} {assertion.get('nl_assertion', '')}")
            if assertion.get("justification"):
                st.caption(assertion["justification"])
    failed_actions = [
        action for action in (reward_info.get("action_checks") or [])
        if isinstance(action, dict) and not action.get("action_match")
    ]
    if failed_actions:
        section("未匹配动作")
        compact_table(
            [
                {
                    "工具": (action.get("action") or {}).get("name"),
                    "类型": action.get("tool_type"),
                    "参数": json.dumps((action.get("action") or {}).get("arguments", {}), ensure_ascii=False),
                }
                for action in failed_actions
            ],
            height=220,
            key="benchmarks-tau2-actions",
        )


def _render_tau2() -> None:
    data = _read_report(TAU2_RESULTS, "τ² 结果")
    if data is None:
        empty_state(
            "未找到 τ² 报告；把 τ² 的 results.json 复制到 outputs/tau2/results.json。",
        )
        return

    sims = [sim for sim in (data.get("simulations") or []) if isinstance(sim, dict)]
    if not sims:
        empty_state("结果文件里没有 simulations。")
        return
    stats = [(sim, _tau2_stats(sim)) for sim in sims]
    passed = sum(1 for _, item in stats if to_float(item["reward"]) == 1.0)
    db_ok = sum(1 for _, item in stats if item["db_match"])
    read_ok = sum(item["read"][0] for _, item in stats)
    read_total = sum(item["read"][1] for _, item in stats)
    write_ok = sum(item["write"][0] for _, item in stats)
    write_total = sum(item["write"][1] for _, item in stats)
    generic_ok = sum(item["generic"][0] for _, item in stats)
    generic_total = sum(item["generic"][1] for _, item in stats)
    nl_ok = sum(item["nl"][0] for _, item in stats)
    nl_total = sum(item["nl"][1] for _, item in stats)

    section("τ²-bench retail", "官方 harness；NL judge 使用 DeepSeek 替代，非官方评分。")
    kpi_row(
        [
            Kpi("Pass^1", f"{passed}/{len(sims)}"),
            Kpi("DB", f"{db_ok}/{len(sims)}"),
            Kpi("Read", f"{read_ok}/{read_total}"),
            Kpi("Write", f"{write_ok}/{write_total}"),
            Kpi("Generic", f"{generic_ok}/{generic_total}"),
            Kpi("NL", f"{nl_ok}/{nl_total}"),
        ]
    )
    _adapter_note("core/benchmarks/adapters/tau2.py")

    rows = [
        {
            "Task": sim.get("task_id"),
            "Reward": item["reward"],
            "DB": "✅" if item["db_match"] else "❌",
            "Read": f"{item['read'][0]}/{item['read'][1]}",
            "Write": f"{item['write'][0]}/{item['write'][1]}",
            "Generic": f"{item['generic'][0]}/{item['generic'][1]}",
            "NL": f"{item['nl'][0]}/{item['nl'][1]}",
            "终止": sim.get("termination_reason"),
            "耗时": f"{to_float(sim.get('duration')):.1f}s",
            "成本": f"${to_float(sim.get('agent_cost')):.4f}",
        }
        for sim, item in stats
    ]
    left, right = master_detail(0.62)
    with left:
        section("逐条任务", "点击一行查看右侧断言与未匹配动作。")
        selected_indices = compact_table(
            rows,
            height=340,
            key="benchmarks-tau2-table",
            selectable=True,
            column_order=["Task", "Reward", "DB", "Read", "Write", "Generic", "NL", "终止", "耗时", "成本"],
        )
        selected_id = st.session_state.get("benchmarks-tau2-selected")
        if selected_indices and 0 <= selected_indices[0] < len(stats):
            selected_id = stats[selected_indices[0]][0].get("task_id")
        valid_ids = {str(sim.get("task_id")) for sim, _ in stats}
        if str(selected_id) not in valid_ids:
            selected_id = stats[0][0].get("task_id")
        st.session_state["benchmarks-tau2-selected"] = selected_id
    with right:
        sim, item = next(
            ((sim, item) for sim, item in stats if str(sim.get("task_id")) == str(selected_id)),
            stats[0],
        )
        _render_tau2_detail(sim, item)


def render_benchmarks(embedded: bool = False) -> None:
    if not embedded:
        page_header(
            "公开基准",
            "只读取已有报告，不在界面里重跑；数字来自各自最近一次运行。",
            meta="BFCL · RGB/MultiHop · τ²",
        )
    else:
        st.caption("公开基准是全局/模型级证据，不按场景拆分；数字来自各自最近一次运行。")
    source_footer([
        (BFCL_RESULTS, "BFCL"),
        (PUBLIC_RESULTS, "RGB / MultiHop"),
        (TAU2_RESULTS, "τ²"),
    ])
    st.caption(
        "执行层：BFCL 200 = 模型层（`bind_tools`）；BFCL 60 = Harness 层（`FrameworkAgent`）；"
        "RGB / MultiHop = 能力/检索层；τ² = 外部官方 harness；320 catalog = 数据目录。"
    )
    mode = st.radio(
        "Benchmark",
        ["BFCL", "RGB / MultiHop", "τ²"],
        horizontal=True,
        key="benchmarks-mode",
    )
    if mode == "BFCL":
        _render_bfcl()
    elif mode == "RGB / MultiHop":
        _render_public()
    else:
        _render_tau2()
