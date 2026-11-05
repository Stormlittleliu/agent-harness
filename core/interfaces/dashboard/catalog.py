# -*- coding: utf-8 -*-
"""Benchmark 目录视图：读取 manifest.json 与 catalog.jsonl。"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import streamlit as st

from core.interfaces.dashboard.common import (
    ROOT,
    load_json,
    load_jsonl,
    rows_to_csv,
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

MANIFEST_PATH = ROOT / "data" / "benchmarks" / "manifest.json"
CATALOG_PATH = ROOT / "data" / "benchmarks" / "catalog.jsonl"
BUILD_CMD = "python -m core.benchmarks.catalog --build --per-source 40 --seed 42"

BUCKET_LABELS = {
    "capability": "能力",
    "adversarial": "对抗",
    "multi_turn": "多轮",
}
RUNNER_LABELS = {
    "external": "官方环境",
    "native": "本项目适配",
    "data_only": "仅数据",
}
ADAPTER_PATHS = {
    "tau2-bench": "core/benchmarks/adapters/tau2.py",
    "bfcl-v4": "core/benchmarks/adapters/bfcl.py",
    "rgb": "core/benchmarks/adapters/rag.py",
    "multihop-rag": "core/benchmarks/adapters/rag.py",
    "cfbench": "core/benchmarks/adapters/cfbench.py",
    "gaia": "core/benchmarks/adapters/gaia.py",
    "humaneval": "core/benchmarks/adapters/humaneval.py",
    "mbpp": "core/benchmarks/adapters/mbpp.py",
    "swe-bench": "core/benchmarks/adapters/swebench.py",
    "webarena": "core/benchmarks/adapters/webarena.py",
    "osworld": "core/benchmarks/adapters/osworld.py",
}


def _runner_text(runners: set[str]) -> str:
    if not runners:
        return "—"
    return " / ".join(RUNNER_LABELS.get(runner, runner) for runner in sorted(runners))


def _catalog_runners(rows: list[dict]) -> dict[str, set[str]]:
    runners: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        source = str(row.get("source") or "—")
        environment = row.get("environment") if isinstance(row.get("environment"), dict) else {}
        runner = environment.get("runner")
        if runner:
            runners[source].add(str(runner))
    return runners


def _source_rows(manifest: dict | None, rows: list[dict]) -> list[dict]:
    runners = _catalog_runners(rows)
    sources = manifest.get("sources") if isinstance(manifest, dict) else None
    if isinstance(sources, list) and sources:
        result = []
        for source in sources:
            if not isinstance(source, dict):
                continue
            name = str(source.get("name") or "—")
            available = source.get("available")
            result.append({
                "来源": name,
                "可用": "✅" if available else ("❌" if available is False else "—"),
                "版本": source.get("version") or "—",
                "原始条数": source.get("loaded", "—"),
                "抽样": source.get("sampled", "—"),
                "许可": source.get("license") or "—",
                "运行方式": _runner_text(runners.get(name, set())),
            })
        return result

    # manifest 缺失时，用 catalog 自身推导来源信息
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("source") or "—")].append(row)
    result = []
    for name in sorted(grouped):
        first = grouped[name][0]
        result.append({
            "来源": name,
            "可用": "—",
            "版本": first.get("source_version") or "—",
            "原始条数": "—",
            "抽样": len(grouped[name]),
            "许可": first.get("license") or "—",
            "运行方式": _runner_text(runners.get(name, set())),
        })
    return result


def _match(value: Any, selected: list[str]) -> bool:
    return not selected or str(value or "") in selected


def catalog_kpis() -> dict:
    """总览页 KPI：目录任务数与来源数的只读摘要。"""
    manifest_raw, manifest_error = load_json(MANIFEST_PATH)
    rows_raw, catalog_error, skipped = load_jsonl(CATALOG_PATH)
    manifest = manifest_raw if isinstance(manifest_raw, dict) else None
    rows = rows_raw if isinstance(rows_raw, list) else []
    source_rows = _source_rows(manifest, rows)
    has_data = manifest is not None or rows_raw is not None
    return {
        "tasks": len(rows) if rows_raw is not None else None,
        "sources": len(source_rows) if has_data else None,
        "errors": [error for error in (manifest_error, catalog_error) if error],
        "skipped": skipped,
    }


def _filtered_rows(
    rows: list[dict],
    query: str,
    selected_sources: list[str],
    selected_categories: list[str],
    selected_buckets: list[str],
    selected_task_types: list[str],
) -> list[dict]:
    filtered = []
    for row in rows:
        if query:
            haystack = " ".join(str(row.get(key) or "") for key in (
                "id", "instruction", "source", "category", "bucket", "task_type"
            ))
            if query not in haystack.casefold():
                continue
        if not _match(row.get("source"), selected_sources):
            continue
        if not _match(row.get("category"), selected_categories):
            continue
        if not _match(row.get("bucket"), selected_buckets):
            continue
        if not _match(row.get("task_type"), selected_task_types):
            continue
        environment = row.get("environment") if isinstance(row.get("environment"), dict) else {}
        runner = environment.get("runner") or "—"
        filtered.append({
            "ID": row.get("id"),
            "来源": row.get("source"),
            "Bucket": row.get("bucket"),
            "类别": row.get("category"),
            "任务类型": row.get("task_type"),
            "评分": row.get("grader"),
            "运行方式": RUNNER_LABELS.get(str(runner), runner),
            "指令": row.get("instruction") or "",
            "适配器": ADAPTER_PATHS.get(str(row.get("source")), "—"),
        })
    return filtered


def _render_task_detail(row: dict, raw: dict) -> None:
    with st.container(border=True):
        st.markdown(f"**{row.get('ID')}** · `{row.get('来源')}`")
        st.caption(
            f"Bucket `{row.get('Bucket')}` · 类别 `{row.get('类别')}` · "
            f"任务类型 `{row.get('任务类型')}` · 评分 `{row.get('评分')}` · "
            f"运行方式 `{row.get('运行方式')}`"
        )
        section("指令")
        text_block(row.get("指令"), height=180)
        environment = raw.get("environment") if isinstance(raw.get("environment"), dict) else {}
        if environment:
            section("执行环境")
            st.json(environment, expanded=False)
        section("对象")
        st.code(str(row.get("适配器") or "—"), language="text")
        st.caption("数据可用 ≠ 环境可用；external / data_only 需要官方环境。")


def render_catalog() -> None:
    manifest_raw, manifest_error = load_json(MANIFEST_PATH)
    rows_raw, catalog_error, skipped = load_jsonl(CATALOG_PATH)
    manifest = manifest_raw if isinstance(manifest_raw, dict) else None
    rows = rows_raw if isinstance(rows_raw, list) else None

    if manifest_error:
        st.error(f"读取 manifest.json 失败：{manifest_error}")
    elif manifest_raw is not None and manifest is None:
        st.warning("manifest.json 不是 JSON 对象，来源表将尝试从 catalog.jsonl 推导。")
    if catalog_error:
        st.error(f"读取 catalog.jsonl 失败：{catalog_error}")
    elif manifest is not None and rows is None:
        st.warning("manifest.json 存在，但 catalog.jsonl 缺失；来源表可用，逐条任务为空。")
    if skipped:
        st.warning(f"catalog.jsonl 中有 {skipped} 行无法解析，已跳过。")

    if manifest is None and rows is None:
        page_header("Benchmark 目录", "公开 benchmark 的统一任务目录。")
        empty_state("未找到 benchmark 目录数据。先生成样例集：", "python -m core.benchmarks.catalog --list\n" + BUILD_CMD)
        return

    rows = rows or []
    raw_by_id = {str(row.get("id")): row for row in rows}
    source_rows = _source_rows(manifest, rows)
    source_count = len(source_rows)
    generated_at = (manifest or {}).get("generated_at") or "—"
    seed = (manifest or {}).get("seed")
    total_recorded = (manifest or {}).get("total")
    page_header(
        "Benchmark 目录",
        "统一任务目录；区分数据可用与执行环境可用。",
        meta=f"{len(rows)} 条 · {source_count} 个来源 · seed={seed if seed is not None else '—'}",
    )
    source_footer([(MANIFEST_PATH, "manifest.json"), (CATALOG_PATH, "catalog.jsonl")])
    if total_recorded is not None:
        st.caption(f"manifest total={total_recorded} · 生成于 {generated_at}")

    bucket_counts = Counter(str(row.get("bucket") or "—") for row in rows)
    per_source = (manifest or {}).get("per_source")
    if per_source is None and source_rows:
        sampled = {
            row.get("抽样")
            for row in source_rows
            if isinstance(row.get("抽样"), int)
        }
        per_source = sampled.pop() if len(sampled) == 1 else None
    kpi_row(
        [
            Kpi("样例任务", f"{len(rows):,}"),
            Kpi("来源", str(source_count)),
            Kpi(
                "能力 / 对抗 / 多轮",
                f"{bucket_counts.get('capability', 0)} / "
                f"{bucket_counts.get('adversarial', 0)} / "
                f"{bucket_counts.get('multi_turn', 0)}",
            ),
            Kpi("每个来源", per_source if per_source is not None else "—"),
        ]
    )
    execution = ((manifest or {}).get("summary") or {}).get("by_runner") or {}
    if execution:
        st.caption(
            "执行方式分布："
            + " · ".join(f"{name} {count}" for name, count in sorted(execution.items()))
            + "（external / native / sandbox_required 不等于本机可跑）"
        )

    if not rows:
        empty_state("catalog.jsonl 为空或缺失；生成样例集：", BUILD_CMD)
        return

    sources = sorted({str(row.get("source") or "") for row in rows if row.get("source")})
    categories = sorted({str(row.get("category") or "") for row in rows if row.get("category")})
    buckets = sorted({str(row.get("bucket") or "") for row in rows if row.get("bucket")})
    task_types = sorted({str(row.get("task_type") or "") for row in rows if row.get("task_type")})

    query = st.text_input(
        "搜索任务",
        placeholder="输入 task ID 或指令片段",
        key="cat-search",
        help="不区分大小写，与筛选条件同时生效。",
    ).strip().casefold()
    col_source, col_category, col_bucket, col_task_type = filter_bar((1.2, 1, 1, 1), gap="small")
    selected_sources = col_source.multiselect("来源", sources, key="cat-sources", placeholder="全部")
    selected_categories = col_category.multiselect("类别", categories, key="cat-categories", placeholder="全部")
    selected_buckets = col_bucket.multiselect(
        "Bucket",
        buckets,
        key="cat-buckets",
        placeholder="全部",
        format_func=lambda value: f"{value}（{BUCKET_LABELS.get(value, value)}）",
    )
    selected_task_types = col_task_type.multiselect(
        "任务类型", task_types, key="cat-task-types", placeholder="全部"
    )

    filtered = _filtered_rows(
        rows, query, selected_sources, selected_categories, selected_buckets, selected_task_types
    )
    st.caption(f"筛选后 {len(filtered)} / {len(rows)} 条")
    st.download_button(
        "下载筛选结果 CSV",
        data=rows_to_csv(filtered),
        file_name="benchmark_catalog_filtered.csv",
        mime="text/csv",
        key="download-catalog-csv",
        help="包含全部筛选结果与完整指令，不受表格展示上限影响。",
    )
    if not filtered:
        empty_state("没有符合筛选条件的任务。")
        return

    left, right = master_detail(0.65)
    with left:
        section("样例任务", "点击一行查看完整指令与执行环境。")
        display_rows = [
            {**row, "指令": short_text(row.get("指令"), 80)}
            for row in filtered
        ]
        signature = (
            query,
            tuple(selected_sources),
            tuple(selected_categories),
            tuple(selected_buckets),
            tuple(selected_task_types),
            len(filtered),
        )
        if st.session_state.get("catalog-filter-signature") != signature:
            st.session_state["catalog-filter-signature"] = signature
            st.session_state["catalog-table-nonce"] = (
                st.session_state.get("catalog-table-nonce", 0) + 1
            )
        table_key = f"catalog-task-table-{st.session_state.get('catalog-table-nonce', 0)}"
        selected_indices = compact_table(
            display_rows,
            height=420,
            key=table_key,
            selectable=True,
            column_order=["ID", "来源", "类别", "指令"],
            column_config={
                "ID": st.column_config.TextColumn(width="medium"),
                "来源": st.column_config.TextColumn(width="small"),
                "类别": st.column_config.TextColumn(width="medium"),
                "指令": st.column_config.TextColumn(width="large"),
            },
        )
        selected_id = st.session_state.get("catalog-selected-task")
        if selected_indices and 0 <= selected_indices[0] < len(filtered):
            selected_id = filtered[selected_indices[0]]["ID"]
        valid_ids = {str(row.get("ID")) for row in filtered}
        if str(selected_id) not in valid_ids:
            selected_id = filtered[0].get("ID")
        st.session_state["catalog-selected-task"] = selected_id

    with right:
        row = next((item for item in filtered if str(item.get("ID")) == str(selected_id)), filtered[0])
        _render_task_detail(row, raw_by_id.get(str(row.get("ID")), {}))

    with st.expander("来源、许可与执行方式", expanded=False):
        compact_table(
            source_rows,
            height=280,
            key="catalog-source-table",
            column_order=["来源", "可用", "版本", "原始条数", "抽样", "许可", "运行方式"],
        )
