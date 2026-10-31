# -*- coding: utf-8 -*-
"""总览页顶部 KPI：优化循环与 Benchmark 目录的只读摘要。"""
from __future__ import annotations

import streamlit as st

from core.interfaces.dashboard.catalog import catalog_kpis
from core.interfaces.dashboard.optimization import optimization_kpis


def _catalog_text(tasks: int | None, sources: int | None) -> str:
    task_text = f"{tasks:,}" if tasks is not None else "—"
    source_text = f"{sources:,}" if sources is not None else "—"
    return f"{task_text} / {source_text}"


def render_overview_kpis() -> None:
    """一行展示最新完成迭代与目录规模；详细内容仍在各自标签页。"""
    opt = optimization_kpis()
    cat = catalog_kpis()
    cols = st.columns(5)
    cols[0].metric(
        "最新完成迭代",
        opt["label"],
        help="按 iteration 序号取最新一个包含 trials 的结果。",
    )
    cols[1].metric(
        "BFCL pass^k / mean",
        opt["bfcl_text"],
        help="pass^k = 所有 trial 都通过的 case 占比；mean = 单 trial 平均通过率。",
    )
    cols[2].metric(
        "RAG pass^k / mean",
        opt["rag_text"],
        help="pass^k = 所有 trial 都通过的 case 占比；mean = 单 trial 平均通过率。",
    )
    cols[3].metric(
        "最新修复 / 回归",
        opt["fixed_regressed_text"],
        help="来自该 iteration 文件的 compare 字段；A/B 面板会按当前 A/B 重新计算。",
    )
    cols[4].metric(
        "目录任务 / 来源",
        _catalog_text(cat["tasks"], cat["sources"]),
        help="catalog.jsonl 实际读取的任务数 / manifest 或 catalog 中的来源数。",
    )

    notes = []
    if opt["errors"]:
        notes.append(f"{len(opt['errors'])} 个优化文件无法解析")
    if cat["errors"]:
        notes.append("目录文件读取异常")
    if cat["skipped"]:
        notes.append(f"目录跳过 {cat['skipped']} 行坏数据")
    caption = "KPI 只读汇总；详细筛选、A/B 与逐条结果见「优化循环」「Benchmark 目录」标签。"
    if notes:
        caption += " " + "；".join(notes) + "。"
    st.caption(caption)
