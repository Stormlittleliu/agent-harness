# -*- coding: utf-8 -*-
"""测试用例视图：运行 cases.jsonl 并查看判定明细。"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from core.agent.framework import FrameworkAgent
from core.interfaces.dashboard.common import MAX_ROWS, file_mtime, source_caption
from core.interfaces.dashboard.task import trace_events
from core.quality.agent_eval import (
    evaluate_cases,
    load_cases,
    summarize_results,
)


@st.cache_data(show_spinner=False)
def _cases_cached(path: str, mtime: float) -> list[dict]:
    return load_cases(Path(path))


def _load_cases(path: Path) -> tuple[list[dict] | None, str | None]:
    stamp = file_mtime(path)
    if stamp is None:
        return None, None
    try:
        return _cases_cached(str(path), stamp), None
    except Exception as exc:  # noqa: BLE001 - 页面兜底
        return None, f"{type(exc).__name__}: {exc}"


def _render_case_detail(row: dict, load_trace: bool = False) -> None:
    """单条用例的完整明细：判定、要点、工具、回答、judge、trace。"""
    cols = st.columns(4)
    cols[0].metric("关键词覆盖", f"{row['coverage']:.0%}")
    cols[1].metric("判定依据", "LLM judge" if row.get("judge_used") else "关键词")
    cols[2].metric("工具命中", "是" if row["tools_ok"] else "否")
    cols[3].metric("拒答", "是" if row["refused"] else "否")

    expected = row.get("expected_points", [])
    matched = row.get("matched_points", [])
    missing = [point for point in expected if point not in matched]
    st.markdown("**要点**")
    st.write(f"- 期望：{expected or '—'}")
    st.write(f"- 命中：{matched or '—'}")
    st.write(f"- 缺失：{missing or '—'}")

    st.markdown("**工具**")
    st.write(f"- 期望：{row.get('expected_tools', []) or '—'}")
    st.write(f"- 实际：{row.get('tool_names', []) or '—'}")
    tool_calls = row.get("tool_calls") or []
    if tool_calls:
        st.dataframe(
            [
                {
                    "工具": call.get("name", ""),
                    "参数": json.dumps(call.get("args", {}), ensure_ascii=False),
                }
                for call in tool_calls
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("**回答**")
    st.markdown(row.get("answer") or "（空）")

    judge = row.get("judge")
    if judge:
        st.markdown("**LLM judge 明细**")
        st.json(judge)

    trace_id = row.get("trace_id")
    if trace_id:
        st.caption(f"trace_id: {trace_id}")
        if load_trace:
            try:
                st.json(trace_events(trace_id))
            except Exception as exc:  # noqa: BLE001
                st.warning(f"trace 读取失败：{type(exc).__name__}: {exc}")


def render_tests(agent: FrameworkAgent) -> None:
    scenario = agent.scenario
    cases_path = Path(scenario.cases_path)
    cases, error = _load_cases(cases_path)
    source_caption(cases_path, prefix="用例文件")
    if error:
        st.error(f"读取用例失败：{error}")
        return
    if cases is None:
        st.info(f"未找到用例文件 `{cases_path}`。")
        return
    if not cases:
        st.info("用例文件为空。")
        return

    st.caption(f"共 {len(cases)} 条行为用例，评分逻辑与 `core.quality.runner agent` 相同。")

    case_ids = [case["id"] for case in cases]
    selected_ids = st.multiselect("选择用例", case_ids, default=case_ids, key="tests-case-ids")
    use_judge = st.checkbox("使用 LLM judge（更慢，会产生额外模型调用）", value=False, key="tests-use-judge")

    with st.expander("查看用例内容", expanded=False):
        case_rows = [
            {
                "ID": case["id"],
                "类别": case["category"],
                "问题": case["question"],
                "期望工具": ", ".join(case.get("expected_tools", [])) or "-",
                "应拒答": "是" if case.get("should_refuse") else "",
                "备注": case.get("notes", ""),
            }
            for case in cases
        ]
        if len(case_rows) > MAX_ROWS:
            st.caption(f"共 {len(case_rows)} 条；仅展示前 {MAX_ROWS} 条。")
            case_rows = case_rows[:MAX_ROWS]
        st.dataframe(case_rows, use_container_width=True, hide_index=True)

    if st.button("运行选中用例", type="primary", key="tests-run"):
        selected = [case for case in cases if case["id"] in set(selected_ids)]
        if not selected:
            st.warning("请至少选择一条用例。")
        else:
            progress = st.progress(0.0)
            status = st.empty()

            def on_result(index, total, row):
                progress.progress(index / total)
                status.write(f"[{index}/{total}] {row['id']} {'✅' if row['passed'] else '❌'}")

            try:
                with st.spinner("用例运行中..."):
                    results = evaluate_cases(agent, selected, judge=use_judge, progress=on_result)
            except Exception as exc:  # noqa: BLE001 - 不展示 traceback
                st.error(f"用例运行失败：{type(exc).__name__}: {exc}")
                return
            st.session_state["test_results"] = results
            st.session_state["test_summary"] = summarize_results(scenario.name, results, judge=use_judge)
            st.session_state["test_judge"] = use_judge

    results = st.session_state.get("test_results")
    if not results:
        return
    summary = st.session_state.get("test_summary")
    if not isinstance(summary, dict):
        st.info("结果汇总缺失，请重新运行用例。")
        return
    judge_used = st.session_state.get("test_judge", False)

    st.caption(
        "本次判定方式：**LLM judge**——通过与否看 judge verdict；"
        "“关键词覆盖”列仍然只表示期望要点的命中率，两者可能不一致。"
        if judge_used else
        "本次判定方式：**确定性规则**——关键词覆盖率 ≥ 50% 且期望工具全部命中；"
        "拒答用例只看是否出现拒答词。"
    )

    cols = st.columns(4)
    cols[0].metric("用例", summary["total"])
    cols[1].metric("通过", f"{summary['passed']}/{summary['total']}")
    cols[2].metric("工具命中", f"{summary['tool_cases_ok']}/{summary['total']}")
    cols[3].metric("拒答", f"{summary['refusal_correct']}/{summary['refusal_count']}")

    st.subheader("筛选")
    col_status, col_judge, col_category = st.columns([1, 1, 1.4])
    status_filter = col_status.radio("结果", ["全部", "✅ 通过", "❌ 失败"], horizontal=True, key="tests-status")
    judge_filter = col_judge.radio("判定依据", ["全部", "关键词", "LLM judge"], horizontal=True, key="tests-judge")
    categories = sorted({row["category"] for row in results})
    selected_categories = col_category.multiselect("类别", categories, default=categories, key="tests-categories")

    filtered = []
    for row in results:
        if status_filter == "✅ 通过" and not row["passed"]:
            continue
        if status_filter == "❌ 失败" and row["passed"]:
            continue
        basis = "LLM judge" if row.get("judge_used") else "关键词"
        if judge_filter != "全部" and basis != judge_filter:
            continue
        if row["category"] not in selected_categories:
            continue
        filtered.append(row)

    total = len(filtered)
    visible = filtered[:MAX_ROWS]
    limit_note = f"；仅展示前 {MAX_ROWS} 条" if total > MAX_ROWS else ""
    st.caption(f"筛选后 {total} / {len(results)} 条{limit_note}")
    load_trace = st.checkbox("明细中加载 trace 事件（较慢）", value=False, key="tests-load-trace")
    if not filtered:
        st.info("没有符合筛选条件的用例。")
        return

    st.dataframe(
        [
            {
                "ID": row["id"],
                "类别": row["category"],
                "问题": row["question"],
                "关键词覆盖": f"{row['coverage']:.0%}",
                "判定依据": "LLM judge" if row.get("judge_used") else "关键词",
                "期望工具": ", ".join(row.get("expected_tools", [])) or "-",
                "实际工具": ", ".join(row.get("tool_names", [])) or "-",
                "通过": "✅" if row["passed"] else "❌",
            }
            for row in visible
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("用例明细")
    st.caption("点击任意一条展开：要点命中、工具调用、完整回答、judge 与 trace。")
    for row in visible:
        icon = "✅" if row["passed"] else "❌"
        label = f"{icon} {row['id']} · {row['category']} · {row['question']}"
        with st.expander(label):
            _render_case_detail(row, load_trace=load_trace)
