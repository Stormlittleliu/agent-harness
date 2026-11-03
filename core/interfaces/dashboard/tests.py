# -*- coding: utf-8 -*-
"""测试用例视图：左侧案例列表，右侧判定 / 对象链路 / 原始数据。

关键改进：
- 不再“表格 + 200 个 expander”重复展示；
- 自动加载最近一次行为报告，没跑模型也能看实际工具与 trace；
- 从案例直接看到场景、工具、中间件、评测函数与 trace 的 `module:line`。
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from core.agent.framework import FrameworkAgent
from core.interfaces.dashboard.common import (
    file_mtime,
    format_mtime,
    latest_agent_report,
    load_cases_cached,
    short_text,
)
from core.interfaces.dashboard.layout import (
    Kpi,
    compact_table,
    empty_state,
    filter_bar,
    kpi_row,
    master_detail,
    page_header,
    section,
    source_footer,
    text_block,
)
from core.interfaces.dashboard.objects import (
    build_object_index,
    case_tool_index,
    render_case_object_panel,
)
from core.interfaces.dashboard.traces import render_trace_timeline
from core.quality.agent_eval import evaluate_cases


def _result_map(results: list[dict] | None) -> dict[str, dict]:
    return {
        str(row.get("id")): row
        for row in (results or [])
        if isinstance(row, dict) and row.get("id") is not None
    }


def _merged_rows(cases: list[dict], results: list[dict] | None) -> list[dict]:
    by_id = _result_map(results)
    rows: list[dict] = []
    for case in cases:
        result = by_id.get(str(case.get("id")))
        if result is None:
            rows.append({
                **case,
                "passed": None,
                "coverage": 0.0,
                "matched_points": [],
                "tool_names": [],
                "tool_calls": [],
                "tools_ok": False,
                "refused": False,
                "answer": "（未运行）",
                "judge": None,
                "judge_used": False,
                "trace_id": None,
                "_has_result": False,
            })
        else:
            rows.append({**result, "_has_result": True})
    return rows


def _status_text(row: dict) -> str:
    if not row.get("_has_result"):
        return "—"
    return "✅" if row.get("passed") else "❌"


def _status_label(row: dict) -> str:
    if not row.get("_has_result"):
        return "未运行"
    return "通过" if row.get("passed") else "失败"


def _apply_filters(
    rows: list[dict],
    categories: list[str],
    selected_categories: list[str],
    status: str,
    tool: str,
    query: str,
) -> list[dict]:
    query = query.strip().casefold()
    filtered = []
    for row in rows:
        if selected_categories and row.get("category") not in selected_categories:
            continue
        if status == "通过" and not row.get("passed"):
            continue
        if status == "失败" and (not row.get("_has_result") or row.get("passed")):
            continue
        if status == "未运行" and row.get("_has_result"):
            continue
        names = set(row.get("tool_names") or []) | set(row.get("expected_tools") or [])
        if tool != "全部" and tool not in names:
            continue
        if query:
            haystack = " ".join(str(row.get(key) or "") for key in ("id", "question", "category", "notes"))
            if query not in haystack.casefold():
                continue
        filtered.append(row)
    return filtered


def _render_judgement(row: dict) -> None:
    has_result = bool(row.get("_has_result"))
    coverage = float(row.get("coverage") or 0)
    kpi_row(
        [
            Kpi("关键词覆盖", f"{coverage:.0%}" if has_result else "—"),
            Kpi(
                "判定依据",
                ("LLM judge" if row.get("judge_used") else "关键词") if has_result else "—",
            ),
            Kpi("工具命中", ("是" if row.get("tools_ok") else "否") if has_result else "—"),
            Kpi("拒答", ("是" if row.get("refused") else "否") if has_result else "—"),
        ]
    )
    if not has_result:
        st.caption("该案例尚未运行；以下是用例定义，运行后才会出现覆盖 / 工具 / 拒答判定。")
    expected = row.get("expected_points", []) or []
    matched = row.get("matched_points", []) or []
    missing = [point for point in expected if point not in matched]
    section("要点")
    st.write(f"- 期望：{expected or '—'}")
    st.write(f"- 命中：{matched or '—'}")
    st.write(f"- 缺失：{missing or '—'}")

    section("工具")
    st.write(f"- 期望：{row.get('expected_tools', []) or '—'}")
    st.write(f"- 实际：{row.get('tool_names', []) or '—'}")
    tool_calls = row.get("tool_calls") or []
    if tool_calls:
        compact_table(
            [
                {
                    "工具": call.get("name", ""),
                    "参数": short_text(json.dumps(call.get("args", {}), ensure_ascii=False), 100),
                }
                for call in tool_calls
            ],
            height=200,
            key="tests-tool-call-table",
        )

    section("回答")
    text_block(row.get("answer"), height=220)

    if row.get("judge"):
        with st.expander("LLM judge 明细", expanded=False):
            st.json(row["judge"], expanded=False)


def _render_raw(row: dict) -> None:
    section("原始 case")
    with st.container(height=240):
        st.json(row, expanded=False)
    section("trace")
    render_trace_timeline(row.get("trace_id"))


def _case_table_rows(rows: list[dict]) -> list[dict]:
    table_rows = []
    for row in rows:
        names = row.get("tool_names") or row.get("expected_tools") or []
        table_rows.append({
            "ID": row.get("id"),
            "类别": row.get("category"),
            "问题": short_text(row.get("question"), 42),
            "结果": _status_text(row),
            "工具": ", ".join(names) or "—",
            "覆盖": f"{float(row.get('coverage') or 0):.0%}" if row.get("_has_result") else "—",
        })
    return table_rows


def _render_case_detail(agent: FrameworkAgent, row: dict) -> None:
    st.markdown(f"**{row.get('id')}** · `{row.get('category')}` · {_status_text(row)} {_status_label(row)}")
    st.caption(row.get("question") or "")
    mode = st.radio(
        "详情",
        ["判定", "对象链路", "原始数据"],
        horizontal=True,
        key="tests-detail-mode",
    )
    if mode == "判定":
        _render_judgement(row)
    elif mode == "对象链路":
        render_case_object_panel(agent, row)
    else:
        _render_raw(row)


def _render_object_browse(cases: list[dict], results: list[dict] | None) -> None:
    usage = case_tool_index(cases, results)
    if not usage:
        empty_state("还没有可浏览的工具使用记录。")
        return
    tool = st.selectbox("选择工具", sorted(usage), key="tests-object-tool")
    item = usage[tool]
    total_ids = set(item.get("total") or [])
    rows = []
    for case in cases:
        case_id = str(case.get("id"))
        if case_id not in total_ids:
            continue
        rows.append({
            "ID": case_id,
            "类别": case.get("category"),
            "问题": short_text(case.get("question"), 60),
            "期望使用": "✅" if case_id in set(item.get("expected") or []) else "",
            "实际调用": "✅" if case_id in set(item.get("actual") or []) else "",
            "通过": "✅" if case_id in set(item.get("passed") or []) else "",
        })
    compact_table(rows, height=420, key="tests-object-table")
    matches = len(item.get("actual") or [])
    passed = len(item.get("passed") or [])
    st.caption(f"`{tool}`：实际调用 {matches} 条 · 通过 {passed} 条。")

    case_ids = [row["ID"] for row in rows]
    if case_ids:
        selected_case = st.selectbox("选择案例查看对象链路", case_ids, key="tests-object-case")

        def _open_case(case_id: str) -> None:
            st.session_state["tests-selected-case"] = case_id
            st.session_state["tests-view-mode"] = "按案例"

        st.button(
            "查看该案例的对象链路",
            key="tests-object-open",
            on_click=_open_case,
            args=(selected_case,),
        )


def _render_run_controls(agent: FrameworkAgent, cases: list[dict]) -> None:
    case_ids = [str(case["id"]) for case in cases]
    with st.popover("运行用例", use_container_width=False):
        selected_ids = st.multiselect("选择用例", case_ids, default=case_ids, key="tests-run-ids")
        use_judge = st.checkbox(
            "使用 LLM judge（更慢，会产生额外模型调用）",
            value=False,
            key="tests-use-judge",
        )
        if st.button("运行选中用例", type="primary", key="tests-run"):
            selected = [case for case in cases if str(case["id"]) in set(selected_ids)]
            if not selected:
                st.warning("请至少选择一条用例。")
                return
            progress = st.progress(0.0)
            status = st.empty()

            def on_result(index, total, row):
                progress.progress(index / total)
                status.write(f"[{index}/{total}] {row['id']} {'✅' if row['passed'] else '❌'}")

            try:
                with st.spinner("用例运行中..."):
                    results = evaluate_cases(agent, selected, judge=use_judge, progress=on_result)
            except Exception as exc:  # noqa: BLE001
                st.error(f"用例运行失败：{type(exc).__name__}: {exc}")
                return
            st.session_state["test_results"] = results
            st.session_state["test_judge"] = use_judge
            st.rerun()


def render_tests(agent: FrameworkAgent) -> None:
    scenario = agent.scenario
    cases_path = Path(scenario.cases_path)
    cases, cases_error = load_cases_cached(cases_path)
    if cases_error:
        st.error(f"读取用例失败：{cases_error}")
        return
    if not cases:
        empty_state(f"未找到用例文件 `{cases_path}`。")
        return

    # 从架构页“查看相关用例”跳转过来时，按工具预筛。
    object_focus = st.session_state.pop("_object_focus", None)
    if object_focus:
        st.session_state["tests-view-mode"] = "按案例"
    session_results = st.session_state.get("test_results")
    report, report_path = latest_agent_report(scenario.name, expected_total=len(cases))
    results = session_results if session_results is not None else (report or {}).get("results")
    rows = _merged_rows(cases, results)

    if session_results is not None:
        label = "本次运行结果"
    elif report_path is not None:
        label = f"报告 · {format_mtime(file_mtime(report_path))}"
    else:
        label = "尚未运行：仅显示用例定义"

    page_header(
        "测试用例",
        "左侧选中一条案例，右侧查看判定、对象链路（场景 → 工具 → 中间件 → 评测 → trace）与原始数据。",
        meta=label,
    )
    if report_path is not None and session_results is None:
        source_footer([(report_path, "行为报告")])
    _render_run_controls(agent, cases)

    view_mode = st.radio(
        "浏览方式",
        ["按案例", "按对象"],
        horizontal=True,
        key="tests-view-mode",
    )
    if view_mode == "按对象":
        _render_object_browse(cases, results)
        return

    categories = sorted({str(row.get("category")) for row in rows if row.get("category")})
    all_tools = sorted({
        str(name)
        for row in rows
        for name in (list(row.get("tool_names") or []) + list(row.get("expected_tools") or []))
        if name
    })
    if object_focus and object_focus in all_tools:
        st.session_state["tests-tool-filter"] = object_focus
        st.caption(f"已按对象筛选：`{object_focus}`")
    col_category, col_status, col_tool, col_query = filter_bar((1.9, 1, 1, 1.4))
    selected_categories = col_category.multiselect(
        "类别", categories, default=categories, key="tests-category-filter"
    )
    status = col_status.selectbox(
        "结果", ["全部", "通过", "失败", "未运行"], key="tests-status-filter"
    )
    tool = col_tool.selectbox("工具", ["全部"] + all_tools, key="tests-tool-filter")
    query = col_query.text_input("搜索", key="tests-search", placeholder="ID / 问题")

    filtered = _apply_filters(rows, categories, selected_categories, status, tool, query)
    ran = [row for row in filtered if row.get("_has_result")]
    passed = [row for row in ran if row.get("passed")]
    tools_ok = [row for row in ran if row.get("tools_ok")]
    kpi_row(
        [
            Kpi("筛选后用例", str(len(filtered))),
            Kpi("已运行", str(len(ran))),
            Kpi("通过", f"{len(passed)}/{len(ran)}"),
            Kpi("工具命中", f"{len(tools_ok)}/{len(ran)}"),
        ]
    )

    if not filtered:
        empty_state("没有符合筛选条件的用例。")
        return

    # 筛选变化时换 table key，避免 dataframe 行选择索引指向旧列表。
    signature = (tuple(selected_categories), status, tool, query, len(filtered))
    if st.session_state.get("tests-filter-signature") != signature:
        st.session_state["tests-filter-signature"] = signature
        st.session_state["tests-table-nonce"] = st.session_state.get("tests-table-nonce", 0) + 1
    table_key = f"tests-case-table-{st.session_state.get('tests-table-nonce', 0)}"

    left, right = master_detail(0.38)
    with left:
        section("案例列表", "点击一行查看右侧详情；默认选中第一条。")
        selected_indices = compact_table(
            _case_table_rows(filtered),
            height=420,
            key=table_key,
            selectable=True,
            column_order=["ID", "类别", "问题", "结果", "工具", "覆盖"],
        )
        selected_id = st.session_state.get("tests-selected-case")
        if selected_indices and 0 <= selected_indices[0] < len(filtered):
            selected_id = filtered[selected_indices[0]].get("id")
        valid_ids = {str(row.get("id")) for row in filtered}
        if str(selected_id) not in valid_ids:
            selected_id = filtered[0].get("id")
        st.session_state["tests-selected-case"] = selected_id
        st.caption(f"当前选中：`{selected_id}`")

    selected = next((row for row in filtered if str(row.get("id")) == str(selected_id)), filtered[0])
    with right:
        _render_case_detail(agent, selected)
