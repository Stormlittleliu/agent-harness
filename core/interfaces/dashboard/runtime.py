# -*- coding: utf-8 -*-
"""运行窗口：任务图 / 任务详情 / 命令日志的 master-detail 布局。"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.interfaces.dashboard.common import short_text
from core.interfaces.dashboard.layout import (
    Kpi,
    compact_table,
    empty_state,
    kpi_row,
    master_detail,
    page_header,
    section,
    text_block,
)
from core.runtime.runner import TaskRunner

STATUS_LABELS = {
    "pending": "待处理",
    "in_progress": "进行中",
    "completed": "已完成",
    "failed": "失败",
}


def _task_rows(store, status: str) -> list[dict]:
    rows = []
    for task in store.list(None if status == "全部" else status):
        rows.append({
            "ID": task.id,
            "任务": short_text(task.subject, 50),
            "状态": STATUS_LABELS.get(task.status, task.status),
            "owner": task.owner or "-",
            "依赖": ", ".join(task.blocked_by) or "-",
            "更新时间": task.updated_at,
        })
    return rows


def _render_task_detail(agent, store, task) -> None:
    with st.container(border=True):
        st.markdown(f"**{task.subject}**")
        st.caption(
            f"`{task.id}` · 状态 `{task.status}` · owner `{task.owner or '-'}` · 更新 {task.updated_at}"
        )
        if task.description:
            st.write(task.description)
        if task.blocked_by:
            st.caption(f"依赖：{', '.join(task.blocked_by)}")
        if task.result:
            section("结果")
            text_block(task.result[:4000], height=200)
        if task.error:
            st.error(task.error)

        if task.status == "pending" and store.deps_done(task):
            if st.button("执行选中任务（调用 Agent）", type="primary", key="runtime-run-task"):
                with st.spinner("任务执行中..."):
                    result = TaskRunner(agent, store).run_task(task.id)
                if result.get("status") == "completed":
                    st.success(f"任务完成：{str(result.get('answer', ''))[:300]}")
                else:
                    st.error(str(result))
                st.rerun()
        elif task.status == "pending":
            st.caption("该任务仍有未完成的依赖，暂时不能执行。")


def render_runtime(agent) -> None:
    runtime = getattr(agent.scenario, "runtime", None)
    store = getattr(runtime, "task_store", None)
    if runtime is None or store is None:
        empty_state("当前场景没有启用任务运行时；切到 `coding_demo` 可以看到任务图与运行窗口。")
        return

    tasks = store.list()
    counts = {status: sum(1 for task in tasks if task.status == status) for status in STATUS_LABELS}
    page_header(
        "运行窗口",
        "左侧选择任务，右侧查看详情并执行 ready 任务；下方是 run_command 日志。",
        meta=f"{len(tasks)} 个任务 · `{Path(runtime.task_store_path).name if getattr(runtime, 'task_store_path', None) else 'SQLite'}`",
    )
    kpi_row(
        [
            Kpi("任务总数", str(len(tasks))),
            Kpi("待处理", str(counts["pending"])),
            Kpi("进行中", str(counts["in_progress"])),
            Kpi("已完成 / 失败", f"{counts['completed']} / {counts['failed']}"),
        ]
    )

    left, right = master_detail(0.58)
    with left:
        section("任务图", "按状态筛选；点击一行查看右侧详情。")
        status = st.radio(
            "状态筛选",
            ["全部", *STATUS_LABELS],
            horizontal=True,
            key="runtime-status-filter",
            format_func=lambda value: "全部" if value == "全部" else STATUS_LABELS.get(value, value),
        )
        rows = _task_rows(store, status)
        selected_indices = compact_table(
            rows,
            height=360,
            key=f"runtime-task-table-{status}",
            selectable=True,
            column_order=["ID", "任务", "状态", "owner", "依赖", "更新时间"],
            empty="当前筛选下没有任务。",
        )
        selected_id = st.session_state.get("runtime-selected-task")
        if selected_indices and 0 <= selected_indices[0] < len(rows):
            selected_id = rows[selected_indices[0]]["ID"]
        valid_ids = {task.id for task in tasks}
        if selected_id not in valid_ids:
            selected_id = tasks[0].id if tasks else None
        st.session_state["runtime-selected-task"] = selected_id

    with right:
        if not selected_id:
            empty_state("当前没有任务。")
        else:
            _render_task_detail(agent, store, store.get(selected_id))

    section("命令日志", "最近一次 run_command 的 stdout / stderr。")
    log_dir = Path(runtime.log_dir) if runtime.log_dir else None
    if not log_dir or not log_dir.exists():
        st.caption("还没有运行日志。")
        return
    logs = sorted(log_dir.glob("run_*.log"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not logs:
        st.caption("还没有 run_command 日志。")
        return
    selected_log = st.selectbox("选择日志", logs, format_func=lambda path: path.name, key="runtime-log-select")
    try:
        lines = selected_log.read_text(encoding="utf-8", errors="replace").splitlines()
        with st.container(height=300):
            st.code("\n".join(lines[-100:]), language="text")
    except OSError as exc:
        st.error(f"读取日志失败：{exc}")
