# -*- coding: utf-8 -*-
"""公开基准视图：BFCL、RGB / MultiHop-RAG、τ²-bench 的已有报告。"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from core.interfaces.dashboard.common import (
    MAX_ROWS,
    ROOT,
    freshness_caption,
    load_json,
    source_caption,
    to_float,
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


def _render_bfcl() -> None:
    st.subheader("BFCL v4 抽样")
    data = _read_report(BFCL_RESULTS, "BFCL 结果")
    if data is None:
        st.info("未找到 `outputs/bfcl/eval_bfcl.json`；先运行 `python -m core.quality.runner bfcl ...`。")
        return

    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    cols = st.columns(4)
    cols[0].metric("函数选择", f"{summary.get('simple_name_ok', 0)}/{summary.get('simple_total', 0)}")
    cols[1].metric("参数 exact", f"{summary.get('simple_exact', 0)}/{summary.get('simple_total', 0)}")
    cols[2].metric("无关不调用", f"{summary.get('irrelevance_no_call', 0)}/{summary.get('irrelevance_total', 0)}")
    cols[3].metric("错误", summary.get("errors", 0))
    source_caption(BFCL_RESULTS)

    results = [row for row in (data.get("results") or []) if isinstance(row, dict)]
    if not results:
        st.info("报告里没有逐条结果。")
        return
    kinds = sorted({str(row.get("kind", "")) for row in results})
    col_kind, col_status = st.columns(2)
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
        rows.append({
            "ID": row.get("id"),
            "类型": row.get("kind"),
            "问题": (row.get("question") or "")[:70],
            "期望函数": row.get("expected_name") or "-",
            "实际调用": ", ".join(str(call.get("name", "")) for call in calls if isinstance(call, dict))
            or "（未调用）",
            "函数名": row.get("name_ok"),
            "参数": row.get("args_ok"),
            "结果": "✅" if passed else "❌",
            "错误": row.get("error") or "",
        })
    total = len(rows)
    suffix = f"；仅展示前 {MAX_ROWS} 条" if total > MAX_ROWS else ""
    st.caption(f"筛选后 {total} / {len(results)} 条{suffix}")
    st.dataframe(rows[:MAX_ROWS], use_container_width=True, hide_index=True)


def _render_public() -> None:
    st.subheader("RGB / MultiHop-RAG 抽样")
    data = _read_report(PUBLIC_RESULTS, "公开 RAG 结果")
    if data is None:
        st.info("未找到 `outputs/public/eval_public_results.json`；先运行 `python -m core.quality.runner public ...`。")
        return

    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    if summary:
        cols = st.columns(len(summary))
        for col, (name, item) in zip(cols, summary.items()):
            if not isinstance(item, dict):
                continue
            col.markdown(
                f"**{name}**\n\n"
                f"Hit@4 **{to_float(item.get('hit_at_4')):.0%}** · "
                f"MRR **{to_float(item.get('mrr')):.3f}** · "
                f"{item.get('scored', 0)} 条"
            )
    else:
        st.info("报告里没有汇总指标。")
    source_caption(PUBLIC_RESULTS)

    results = [row for row in (data.get("results") or []) if isinstance(row, dict)]
    if not results:
        st.info("报告里没有逐条结果。")
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
    total = len(rows)
    suffix = f"；仅展示前 {MAX_ROWS} 条" if total > MAX_ROWS else ""
    st.caption(f"筛选后 {total} / {len(results)} 条{suffix}")
    st.dataframe(rows[:MAX_ROWS], use_container_width=True, hide_index=True)


def _tau2_counts(actions: list[dict], tool_type: str) -> tuple[int, int]:
    items = [action for action in actions if action.get("tool_type") == tool_type]
    return sum(1 for action in items if action.get("action_match")), len(items)


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


def _render_tau2() -> None:
    st.subheader("τ²-bench retail")
    data = _read_report(TAU2_RESULTS, "τ² 结果")
    if data is None:
        st.info("未找到 `outputs/tau2/results.json`；把 τ² 的 results.json 复制到该路径。")
        return

    sims = [sim for sim in (data.get("simulations") or []) if isinstance(sim, dict)]
    if not sims:
        st.info("结果文件里没有 simulations。")
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

    cols = st.columns(6)
    cols[0].metric("Pass^1", f"{passed}/{len(sims)}")
    cols[1].metric("DB", f"{db_ok}/{len(sims)}")
    cols[2].metric("Read", f"{read_ok}/{read_total}")
    cols[3].metric("Write", f"{write_ok}/{write_total}")
    cols[4].metric("Generic", f"{generic_ok}/{generic_total}")
    cols[5].metric("NL", f"{nl_ok}/{nl_total}")
    source_caption(TAU2_RESULTS)

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
    suffix = f"；仅展示前 {MAX_ROWS} 条" if len(rows) > MAX_ROWS else ""
    st.caption(f"共 {len(rows)} 条{suffix}")
    st.dataframe(rows[:MAX_ROWS], use_container_width=True, hide_index=True)

    st.markdown("**任务明细**")
    for sim, item in stats[:MAX_ROWS]:
        with st.expander(f"task {sim.get('task_id')} · reward {item['reward']}"):
            reward_info = sim.get("reward_info") if isinstance(sim.get("reward_info"), dict) else {}
            nl = [entry for entry in (reward_info.get("nl_assertions") or []) if isinstance(entry, dict)]
            if nl:
                st.markdown("NL 断言")
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
                st.markdown("未匹配动作")
                st.dataframe(
                    [
                        {
                            "工具": (action.get("action") or {}).get("name"),
                            "类型": action.get("tool_type"),
                            "参数": json.dumps(
                                (action.get("action") or {}).get("arguments", {}),
                                ensure_ascii=False,
                            ),
                        }
                        for action in failed_actions
                    ],
                    use_container_width=True,
                    hide_index=True,
                )


def render_benchmarks() -> None:
    st.caption("只读取已有报告，不在界面里重跑；数字来自各自最近一次运行。")
    freshness_caption([
        (BFCL_RESULTS, "BFCL"),
        (PUBLIC_RESULTS, "RGB / MultiHop"),
        (TAU2_RESULTS, "τ²"),
    ])
    _render_bfcl()
    st.divider()
    _render_public()
    st.divider()
    _render_tau2()
    with st.expander("如何刷新这些结果"):
        st.code(
            "python -m core.quality.runner bfcl ...\n"
            "python -m core.quality.runner public ...\n"
            "# tau2：运行完成后把 results.json 复制到 outputs/tau2/results.json",
            language="bash",
        )
