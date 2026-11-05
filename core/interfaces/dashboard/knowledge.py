# -*- coding: utf-8 -*-
"""知识库分类视图：按 domain / category 看 Chroma 里到底有什么。

只读：不改分块、不触发模型；分类来自入库元数据（core/tools/rag/classification.py）。
"""
from __future__ import annotations

import streamlit as st

from core.interfaces.dashboard.layout import (
    Kpi,
    compact_table,
    empty_state,
    kpi_row,
    section,
)


@st.cache_data(ttl=30, show_spinner=False)
def _summary() -> dict:
    from core.tools.rag.classification import summary

    return summary()


def render_knowledge() -> None:
    with st.spinner("正在读取知识库元数据…"):
        info = _summary()
    if not info.get("chunks"):
        empty_state(
            "知识库还没有分块。",
            "python -m core.tools.rag.vector_store --rebuild",
        )
        return

    section(
        "知识库分类",
        "domain 决定检索过滤；category 用于看资产。分类是入库元数据，不是模型判断。",
    )
    kpi_row(
        [
            Kpi("文档", str(info["documents"])),
            Kpi("分块", str(info["chunks"])),
            Kpi("领域", str(len(info["by_domain"]))),
            Kpi("类别", str(len(info["by_category"]))),
        ]
    )

    section("按领域", "检索时用 domain 过滤，服装问题不会召回机器人文档。")
    compact_table(
        [
            {"领域": domain, "分块": chunks}
            for domain, chunks in info["by_domain"].items()
        ],
        height=150,
        key="knowledge-domain-table",
    )

    section("按类别", "同领域内的细分；后续可按 category 做更窄的检索。")
    compact_table(
        [
            {"类别": category, "分块": chunks}
            for category, chunks in info["by_category"].items()
        ],
        height=180,
        key="knowledge-category-table",
    )

    section("来源明细", "每个源文件的分块数；新增文档后重新入库即可更新。")
    compact_table(
        [
            {
                "领域": row["domain_label"],
                "类别": row["category_label"],
                "源文件": row["source"],
                "分块": row["chunks"],
            }
            for row in info["rows"]
        ],
        height=240,
        key="knowledge-source-table",
        column_order=["领域", "类别", "源文件", "分块"],
    )
