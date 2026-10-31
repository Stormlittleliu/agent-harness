# -*- coding: utf-8 -*-
"""运行窗口：任务图看板 + 命令日志。"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.interfaces.dashboard.common import freshness_caption, short_text
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


def render_runtime(agent) -> None:
    runtime = getattr(agent.scenario, "runtime", None)
    store = getattr(runtime, "task_store", None)
    if runtime is None or store is None:
        st.info("当前场景没有启用任务运行时；切到 `coding_demo` 可以看到任务图与运行窗口。")
        return

    st.subheader("任务图")
    tasks = store.list()
    counts = {status: sum(1 for task in tasks if task.status == status) for status in STATUS_LABELS}
    cols = st.columns(5)
    cols[0].metric("任务总数", len(tasks))
    cols[1].metric("待处理", counts["pending"])
    cols[2].metric("进行中", counts["in_progress"])
    cols[3].metric("已完成", counts["completed"])
    cols[4].metric("失败", counts["failed"])

    status = st.radio("状态筛选", ["全部", *STATUS_LABELS], horizontal=True)
    rows = _task_rows(store, status)
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("没有符合条件的任务。")

    if tasks:
        selected_id = st.selectbox(
            "选择任务查看详情",
            [task.id for task in tasks],
            format_func=lambda task_id: next(
                f"{task.id} · {task.subject}" for task in tasks if task.id == task_id
            ),
        )
        task = store.get(selected_id)
        st.markdown(f"**{task.subject}** · `{task.status}` · owner=`{task.owner or '-'}`")
        if task.description:
            st.write(task.description)
        if task.blocked_by:
            st.caption(f"依赖：{', '.join(task.blocked_by)}")
        if task.result:
            st.markdown("**结果**")
            st.write(task.result[:2000])
        if task.error:
            st.error(task.error)
        if task.status == "pending" and store.deps_done(task):
            if st.button("执行选中任务（调用 Agent）", type="primary"):
                with st.spinner("任务执行中..."):
                    result = TaskRunner(agent, store).run_task(task.id)
                if result.get("status") == "completed":
                    st.success(f"任务完成：{result.get('answer', '')[:300]}")
                else:
                    st.error(str(result))
                st.rerun()
        elif task.status == "pending":
            st.caption("该任务仍有未完成的依赖，暂时不能执行。")

    st.divider()
    st.subheader("运行窗口")
    log_dir = Path(runtime.log_dir) if runtime.log_dir else None
    if not log_dir or not log_dir.exists():
        st.caption("还没有运行日志。")
        return
    freshness_caption([(log_dir, "运行日志目录")], prefix="数据来源")
    logs = sorted(log_dir.glob("run_*.log"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not logs:
        st.caption("还没有 run_command 日志。")
        return
    selected_log = st.selectbox("选择日志", logs, format_func=lambda path: path.name)
    try:
        lines = selected_log.read_text(encoding="utf-8", errors="replace").splitlines()
        st.code("\n".join(lines[-80:]), language="text")
    except OSError as exc:
        st.error(f"读取日志失败：{exc}")
