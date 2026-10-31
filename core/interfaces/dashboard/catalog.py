# -*- coding: utf-8 -*-
"""Benchmark 目录视图：读取 manifest.json 与 catalog.jsonl。"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import streamlit as st

from core.interfaces.dashboard.common import (
    MAX_ROWS,
    ROOT,
    freshness_caption,
    load_json,
    load_jsonl,
    rows_to_csv,
    short_text,
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


def render_catalog() -> None:
    manifest_raw, manifest_error = load_json(MANIFEST_PATH)
    rows_raw, catalog_error, skipped = load_jsonl(CATALOG_PATH)
    manifest = manifest_raw if isinstance(manifest_raw, dict) else None
    rows = rows_raw if isinstance(rows_raw, list) else None

    freshness_caption([
        (MANIFEST_PATH, "manifest.json"),
        (CATALOG_PATH, "catalog.jsonl"),
    ])

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
        st.info("未找到 benchmark 目录数据。先生成样例集：")
        st.code(
            "python -m core.benchmarks.catalog --list\n" + BUILD_CMD,
            language="bash",
        )
        return

    rows = rows or []
    source_rows = _source_rows(manifest, rows)
    source_count = len(source_rows)

    generated_at = (manifest or {}).get("generated_at") or "—"
    seed = (manifest or {}).get("seed")
    total_recorded = (manifest or {}).get("total")
    st.caption(
        f"目录生成时间：{generated_at}"
        + (f" · seed={seed}" if seed is not None else "")
        + (f" · manifest total={total_recorded}" if total_recorded is not None else "")
        + f" · 实际读取 {len(rows)} 条"
    )

    bucket_counts = Counter(str(row.get("bucket") or "—") for row in rows)
    per_source = (manifest or {}).get("per_source")
    if per_source is None and source_rows:
        sampled = {
            row.get("抽样")
            for row in source_rows
            if isinstance(row.get("抽样"), int)
        }
        per_source = sampled.pop() if len(sampled) == 1 else None
    cols = st.columns(4)
    cols[0].metric("样例任务", len(rows))
    cols[1].metric("来源", source_count)
    cols[2].metric(
        "能力 / 对抗 / 多轮",
        f"{bucket_counts.get('capability', 0)} / "
        f"{bucket_counts.get('adversarial', 0)} / "
        f"{bucket_counts.get('multi_turn', 0)}",
    )
    cols[3].metric("每个来源", per_source if per_source is not None else "—")

    st.subheader("来源")
    st.dataframe(source_rows, use_container_width=True, hide_index=True)

    runner_counts = Counter(
        runner for runners in _catalog_runners(rows).values() for runner in runners
    )
    runner_note = " · ".join(
        f"{RUNNER_LABELS.get(name, name)} {count} 个来源"
        for name, count in sorted(runner_counts.items())
    )
    st.info(
        "数据可用 ≠ 环境可用：`available`（可用）只表示本地数据已加载；"
        "`external` 需要官方 harness，`native` 使用本项目适配器，"
        "`data_only` 只有任务元数据、没有可执行环境。"
        + (f" 当前目录：{runner_note}。" if runner_note else "")
    )

    st.subheader("样例任务")
    if not rows:
        st.info("catalog.jsonl 为空或缺失；生成样例集：")
        st.code(BUILD_CMD, language="bash")
        return

    sources = sorted({str(row.get("source") or "") for row in rows if row.get("source")})
    categories = sorted({str(row.get("category") or "") for row in rows if row.get("category")})
    buckets = sorted({str(row.get("bucket") or "") for row in rows if row.get("bucket")})
    task_types = sorted({str(row.get("task_type") or "") for row in rows if row.get("task_type")})

    query = st.text_input(
        "搜索任务",
        placeholder="输入 task ID 或指令片段",
        key="cat-search",
        help="不区分大小写，与下方筛选条件同时生效。",
    ).strip().casefold()

    col_source, col_category, col_bucket, col_task_type = st.columns(4)
    selected_sources = col_source.multiselect("来源", sources, key="cat-sources")
    selected_categories = col_category.multiselect("类别", categories, key="cat-categories")
    selected_buckets = col_bucket.multiselect(
        "Bucket",
        buckets,
        key="cat-buckets",
        format_func=lambda value: f"{value}（{BUCKET_LABELS.get(value, value)}）",
    )
    selected_task_types = col_task_type.multiselect(
        "任务类型", task_types, key="cat-task-types"
    )
    st.caption("搜索与筛选可叠加，筛选留空表示全部；表格最多展示前 200 条。")

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
        })

    total = len(filtered)
    suffix = f"；仅展示前 {MAX_ROWS} 条" if total > MAX_ROWS else ""
    st.caption(f"筛选后 {total} / {len(rows)} 条{suffix}")
    if not filtered:
        st.info("没有符合筛选条件的任务。")
        return
    st.download_button(
        "下载筛选结果 CSV",
        data=rows_to_csv(filtered),
        file_name="benchmark_catalog_filtered.csv",
        mime="text/csv",
        key="download-catalog-csv",
        help="包含全部筛选结果与完整指令，不受表格 200 行展示上限影响。",
    )
    display_rows = [
        {**row, "指令": short_text(row["指令"], 90)}
        for row in filtered[:MAX_ROWS]
    ]
    st.dataframe(display_rows, use_container_width=True, hide_index=True)
