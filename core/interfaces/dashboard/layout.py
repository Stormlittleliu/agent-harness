# -*- coding: utf-8 -*-
"""Dashboard 统一布局：页面骨架、KPI、主从分栏、受控表格与长文本容器。

目标是把「每个视图自己拼 columns / metric / dataframe」收敛成一套密度一致的
组件，避免有的页面一屏 6 个指标、有的页面全宽表格无限增长。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import streamlit as st

from core.interfaces.dashboard.common import (
    MAX_ROWS,
    file_mtime,
    format_mtime,
)

TABLE_HEIGHT = 340
COMPACT_TABLE_HEIGHT = 260
LOG_HEIGHT = 420
KPI_COLUMNS = 4

_CSS = """
<style>
.block-container {
    /* 固定导航条盖住 header 顶部；留 5.5rem 给导航条和第一行之间的呼吸 */
    padding-top: 5.5rem;
    padding-bottom: 2rem;
    max-width: 1500px;
    margin: 0 auto;
}
h1 { font-size: 1.5rem !important; }
h2 { font-size: 1.2rem !important; }
h3, h4 { font-size: 1.02rem !important; }
[data-testid="stMetric"] {
    padding: .35rem .55rem;
    border: 1px solid rgba(128,128,128,.18);
    border-radius: 10px;
}
[data-testid="stMetricValue"] { font-size: 1.2rem; }
[data-testid="stMetricLabel"] { font-size: .78rem; }
div[data-testid="stDataFrame"] {
    border: 1px solid rgba(128,128,128,.16);
    border-radius: 10px;
    overflow: hidden;
}
.ah-muted { color: rgba(128,128,128,.95); font-size: .82rem; }
.ah-badge {
    display: inline-block;
    border: 1px solid rgba(128,128,128,.30);
    border-radius: 999px;
    padding: 0 .45rem;
    font-size: .72rem;
    line-height: 1.5;
}
.ah-card-title { font-weight: 600; }
.ah-chain-wrap {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: .18rem .12rem;
    margin: .15rem 0 .1rem;
}
.ah-chain {
    border: 1px solid rgba(128,128,128,.32);
    border-radius: 999px;
    padding: .13rem .5rem;
    font-size: .78rem;
    line-height: 1.5;
    background: rgba(128,128,128,.05);
    cursor: help;
    white-space: nowrap;
}
.ah-chain b { color: #4C7DF0; font-weight: 600; margin-right: .12rem; }
.ah-chain:hover { border-color: #4C7DF0; background: #EEF4FF; }
.ah-arrow { color: rgba(128,128,128,.75); font-size: .72rem; margin: 0 .1rem; }
.stGraphVizChart { min-height: 120px; }
.stGraphVizChart svg { width: 100% !important; height: auto !important; min-height: 120px; }
#MainMenu { visibility: hidden; }
[data-testid="stAppDeployButton"] { display: none; }
[data-testid="stDecoration"] { display: none; }
/* header 是 position:absolute 的 3.75rem 覆盖层：只画成透明不够，它还会吃掉点击。
   把整条 header 的指针事件关掉，只让真正可点的子元素（工具条 / 运行状态 / Deploy）
   恢复 auto——这样既保留运行中的停止按钮，又不会形成"看得见点不动"的死区。 */
header[data-testid="stHeader"] {
    background: transparent;
    pointer-events: none;
}
header[data-testid="stHeader"] [data-testid="stToolbar"],
header[data-testid="stHeader"] [data-testid="stStatusWidget"],
header[data-testid="stHeader"] [data-testid="stAppDeployButton"] {
    pointer-events: auto;
}
/* 顶部导航条：固定在 header 下方。Streamlit 1.40 的 stMain 滚动容器会让
   position:sticky 失效（实测滚动 900px 后导航会消失），所以用 fixed；另加一条
   白色 topfill 盖住 0–3.75rem 的 header 区，避免滚动内容从导航上方透出来。 */
.st-key-ah-nav {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    width: 100vw;
    box-sizing: border-box;
    z-index: 900;
    background: #fff;
    border-bottom: 1px solid rgba(128,128,128,.16);
    padding: .55rem max(1rem, calc((100vw - 1500px) / 2)) .55rem;
    margin: 0;
}
.st-key-ah-nav [data-testid="stButtonGroup"] {
    max-width: 24rem;
    margin: 0;
}
.st-key-ah-nav [data-testid="stButtonGroup"] button,
.st-key-ah-tabs [data-testid="stButtonGroup"] button {
    border: 0 !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 6px 6px 0 0 !important;
    background: transparent !important;
    color: inherit !important;
    box-shadow: none !important;
    padding: .35rem .85rem !important;
    font-weight: 500;
}
.st-key-ah-nav [data-testid="stButtonGroup"] button:hover,
.st-key-ah-tabs [data-testid="stButtonGroup"] button:hover {
    background: rgba(76,125,240,.08) !important;
}
.st-key-ah-nav [data-testid="stButtonGroup"] button[data-testid="stBaseButton-segmented_controlActive"],
.st-key-ah-tabs [data-testid="stButtonGroup"] button[data-testid="stBaseButton-segmented_controlActive"] {
    color: #2F5BD3 !important;
    border-bottom-color: #4C7DF0 !important;
    background: transparent !important;
    font-weight: 600;
}
.st-key-chat-starters [data-testid="stButtonGroup"] button[data-testid="stBaseButton-pillsActive"] {
    color: #2F5BD3 !important;
    border-color: rgba(76,125,240,.45) !important;
    background: #EEF4FF !important;
}
.st-key-ah-tabs {
    margin-bottom: .5rem;
}
/* 对话页入口列表（在内容左列，不再用 sidebar）：整行可点，不要按钮盒子 */
.st-key-chat-rail [data-testid="stButton"] button {
    justify-content: flex-start;
    border: 0 !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: .32rem .55rem;
}
.st-key-chat-rail [data-testid="stButton"] button:hover {
    background: rgba(76,125,240,.08) !important;
}
.st-key-chat-rail [data-testid="stButton"] button[data-testid="stBaseButton-primary"] {
    color: #2F5BD3 !important;
    background: rgba(76,125,240,.14) !important;
    font-weight: 600;
}
/* 构建库的行内「打开」：是一行文字动作，不是 9 个并排的按钮盒子 */
[class*="st-key-build-open-"] [data-testid="stButton"] button {
    justify-content: flex-end;
    border: 0 !important;
    background: transparent !important;
    box-shadow: none !important;
    color: #2F5BD3 !important;
    font-weight: 500;
    padding: .2rem .35rem;
}
[class*="st-key-build-open-"] [data-testid="stButton"] button:hover {
    background: rgba(76,125,240,.08) !important;
}
/* 开场白是小 chip，不是三张通栏大卡 */
.st-key-chat-starters [data-testid="stButtonGroup"] button {
    border-radius: 999px !important;
    font-size: .82rem !important;
    padding: .22rem .7rem !important;
}
[data-testid="stSidebar"] {
    background: #FAFBFC;
    border-right: 1px solid rgba(128,128,128,.12);
}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .35rem; }
[data-testid="stSidebar"] [data-testid="stButton"] button {
    justify-content: flex-start;
    border: 0 !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: .3rem .55rem;
}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover {
    background: rgba(76,125,240,.08) !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button[data-testid="stBaseButton-primary"] {
    color: #2F5BD3 !important;
    background: rgba(76,125,240,.14) !important;
    font-weight: 600;
}
[data-testid="stBaseButton-secondary"] { border-color: rgba(128,128,128,.26); }
div[data-testid="stButton"] > button { border-radius: 8px; font-weight: 500; }
</style>
"""


@dataclass(frozen=True)
class Kpi:
    label: str
    value: str
    help: str = ""


def inject_css() -> None:
    """在 set_page_config 之后注入一次；只用主题中立颜色。"""
    st.markdown(_CSS, unsafe_allow_html=True)


def sync_widget(key: str, value: Any) -> None:
    """让 widget 的值跟随外部真相（如 ``console:route``）。

    必须在**创建该 widget 之前**调用：Streamlit 只允许在实例化前改
    ``st.session_state[key]``。导航 / 页签都用它把 route 当唯一真相，
    这样深链 ``?tab=publish`` 在第二次进入同一场景时也不会被旧 widget 值盖掉。
    """
    if st.session_state.get(key) != value:
        st.session_state[key] = value


def page_header(
    title: str,
    description: str | None = None,
    meta: str | None = None,
) -> None:
    """页面标题 + 一行说明 + 右侧数据时间，替代重复的 title/subheader/caption。"""
    left, right = st.columns([3.4, 1], gap="small", vertical_alignment="top")
    with left:
        st.markdown(f"#### {title}")
        if description:
            st.caption(description)
    with right:
        if meta:
            st.caption(meta)


def section(title: str, caption: str | None = None) -> None:
    st.markdown(f"**{title}**")
    if caption:
        st.caption(caption)


def kpi_row(items: Sequence[Kpi], columns: int = KPI_COLUMNS) -> None:
    """最多 `columns` 个指标一行；多出来的另起一行，保持列宽一致。"""
    items = list(items)
    if not items:
        return
    columns = max(1, int(columns))
    for start in range(0, len(items), columns):
        chunk = items[start:start + columns]
        cols = st.columns(columns, gap="small", vertical_alignment="top")
        for col, item in zip(cols, chunk):
            col.metric(item.label, item.value, help=item.help or None)


def filter_bar(
    weights: tuple[float, ...] = (1.2, 1, 1, 1.4),
    *,
    gap: str = "small",
) -> list:
    """一行筛选控件；调用方按返回的 columns 放控件。"""
    return st.columns(list(weights), gap=gap, vertical_alignment="bottom")


def master_detail(left_ratio: float = 0.62) -> list:
    """左主区 / 右详情区；比例用 `left_ratio` 控制。"""
    left_ratio = min(0.85, max(0.15, float(left_ratio)))
    return st.columns([left_ratio, 1 - left_ratio], gap="medium", vertical_alignment="top")


def compact_table(
    rows: Sequence[dict],
    *,
    height: int = TABLE_HEIGHT,
    key: str | None = None,
    selectable: bool = False,
    column_order: Sequence[str] | None = None,
    column_config: dict | None = None,
    total: int | None = None,
    limit: int = MAX_ROWS,
    empty: str = "没有符合条件的数据。",
) -> list[int]:
    """受控表格：固定高度、行数提示、可选单选；返回选中行索引。"""
    rows = list(rows or [])
    if not rows:
        empty_state(empty)
        return []
    total = len(rows) if total is None else total
    shown = rows[:limit]
    suffix = f"；仅展示前 {limit} 条" if total > limit else ""
    st.caption(f"共 {total} 条{suffix}")
    table_height = min(int(height), max(140, 40 + 34 * len(shown)))
    kwargs: dict[str, Any] = {
        "data": shown,
        "use_container_width": True,
        "hide_index": True,
        "height": table_height,
    }
    if column_order is not None:
        kwargs["column_order"] = list(column_order)
    if column_config is not None:
        kwargs["column_config"] = column_config
    if selectable:
        if not key:
            raise ValueError("selectable table 需要稳定的 key")
        event = st.dataframe(
            **kwargs,
            key=key,
            on_select="rerun",
            selection_mode="single-row",
        )
        try:
            return list(event.selection.rows)
        except Exception:  # noqa: BLE001 - 旧版/测试环境没有 selection
            return []
    st.dataframe(**kwargs)
    return []


def text_block(text: str | None, *, height: int = 260) -> None:
    """长文本放进固定高度容器，避免把整页撑开。"""
    with st.container(height=height):
        st.markdown(str(text).strip() if text and str(text).strip() else "—")


def empty_state(message: str, command: str | None = None) -> None:
    st.info(message)
    if command:
        st.code(command, language="bash")


def graph_dot(graph) -> str:
    """把 LangGraph 的边转成 Graphviz DOT，Streamlit 可直接渲染。"""
    labels = {"__start__": "START", "__end__": "END"}
    lines = [
        "digraph G {",
        "rankdir=LR;",
        'node [shape=box, style="rounded,filled", fillcolor="#EEF4FF", fontsize=11];',
    ]
    nodes: set[str] = set()
    for edge in graph.edges:
        source = labels.get(edge.source, edge.source)
        target = labels.get(edge.target, edge.target)
        nodes.update({source, target})
        style = " [style=dashed]" if getattr(edge, "conditional", False) else ""
        lines.append(f'  "{source}" -> "{target}"{style};')
    for node in nodes:
        if node in {"START", "END"}:
            lines.append(f'  "{node}" [shape=oval, fillcolor="#E8F5E9"];')
    lines.append("}")
    return "\n".join(lines)


def source_footer(entries: Sequence[tuple[Path, str]]) -> None:
    """一行展示多个数据源与 mtime，避免每个区块重复 caption。"""
    parts: list[str] = []
    for path, label in entries:
        stamp = file_mtime(path)
        if stamp is None:
            parts.append(f"{label}（缺失）")
        else:
            parts.append(f"{label} · {format_mtime(stamp)}")
    if parts:
        st.caption("数据来源：" + " ｜ ".join(parts))


def navigate(view: str, focus: str | None = None) -> None:
    """on_click 回调：写非 widget 状态，由 run() 顶部应用到导航 radio。"""
    st.session_state["_pending_nav"] = view
    if focus:
        st.session_state["_object_focus"] = focus
