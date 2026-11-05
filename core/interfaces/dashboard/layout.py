# -*- coding: utf-8 -*-
"""Dashboard 统一布局：页面骨架、KPI、主从分栏、受控表格与长文本容器。

目标是把「每个视图自己拼 columns / metric / dataframe」收敛成一套密度一致的
组件，避免有的页面一屏 6 个指标、有的页面全宽表格无限增长。
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
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
KPI_COLUMNS = 5

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
div[data-testid="stButton"] > button {
    border-radius: 8px;
    font-weight: 500;
    min-height: 2.15rem;
    padding: .28rem .7rem;
    font-size: .84rem;
}
.st-key-chat-rail-card [data-testid="stButton"] button {
    justify-content: flex-start;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: .82rem !important;
    min-height: 2rem;
}
</style>
"""


_CSS_EXTRA = """
<style>
:root {
    --ah-bg: #F5F6F8;
    --ah-surface: #FFFFFF;
    --ah-border: #E4E7EC;
    --ah-ink: #101828;
    --ah-muted: #667085;
    --ah-accent: #2F5BD3;
    --ah-accent-soft: #EEF4FF;
    --ah-radius: 14px;
}
.stApp { background: var(--ah-bg); color: var(--ah-ink); }
[data-testid="stAppViewContainer"], [data-testid="stMain"], .main, section.main {
    background: var(--ah-bg) !important;
}
.block-container {
    padding-top: 4.35rem;
    padding-bottom: 3rem;
    max-width: 1440px;
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
}
[data-testid="stVerticalBlock"] { gap: .55rem; }
h1, h2, h3, h4 { letter-spacing: -.012em; }

/* 页面标题：所有产品共用一套节奏，避免每个页面自己拼 H4 + caption */
.ah-page-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 2rem;
    padding: .15rem 0 .9rem;
    margin-bottom: .15rem;
    border-bottom: 1px solid var(--ah-border);
}
.ah-page-head h1 {
    font-size: 1.55rem !important;
    line-height: 1.2 !important;
    margin: .12rem 0 .28rem !important;
    font-weight: 650 !important;
}
.ah-page-head p {
    margin: 0;
    color: var(--ah-muted);
    font-size: .89rem;
    line-height: 1.65;
    max-width: 74ch;
}
.ah-page-meta {
    color: var(--ah-muted);
    font-size: .78rem;
    white-space: nowrap;
    padding-bottom: .12rem;
}
.ah-eyebrow {
    font-size: .66rem;
    letter-spacing: .13em;
    text-transform: uppercase;
    color: var(--ah-accent);
    font-weight: 700;
}
.ah-section {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
    margin: 1.05rem 0 .4rem;
}
.ah-section-title { font-weight: 650; font-size: .94rem; }
.ah-section-caption { color: var(--ah-muted); font-size: .78rem; text-align: right; }

/* 导航条：品牌 / 产品 / 环境，三段对齐；背景压低，不再是一条纯白通栏 */
.st-key-ah-nav {
    background: rgba(255, 255, 255, .92);
    backdrop-filter: saturate(180%) blur(12px);
    border-bottom: 1px solid var(--ah-border);
    box-shadow: 0 1px 0 rgba(16, 24, 40, .02);
    padding: .48rem max(1rem, calc((100vw - 1440px) / 2)) .48rem;
}
.ah-brand { display: flex; align-items: center; gap: .58rem; line-height: 1.05; }
.ah-brand-mark {
    width: 27px; height: 27px; border-radius: 8px;
    display: inline-flex; align-items: center; justify-content: center;
    background: linear-gradient(135deg, #2F5BD3, #5B8DEF);
    color: #fff; font-size: .8rem; font-weight: 750;
    box-shadow: 0 2px 5px rgba(47, 91, 211, .25);
}
.ah-brand b { font-size: .9rem; font-weight: 650; letter-spacing: -.01em; }
.ah-brand small { display: block; color: var(--ah-muted); font-size: .64rem; margin-top: .16rem; letter-spacing: .02em; }
.ah-nav-status { text-align: right; color: var(--ah-muted); font-size: .7rem; letter-spacing: .04em; }
.ah-nav-status span {
    display: inline-flex; align-items: center; gap: .3rem;
    border: 1px solid var(--ah-border); border-radius: 999px;
    padding: .16rem .5rem; background: var(--ah-surface);
}
.ah-nav-status i { width: 6px; height: 6px; border-radius: 50%; background: #12B76A; display: inline-block; }

/* 容器卡片只作用于显式带 key 的卡片，避免给每个 vertical block 都套边框 */
[data-testid="stMetric"] {
    background: var(--ah-surface);
    border: 1px solid var(--ah-border);
    border-radius: 12px;
    padding: .62rem .75rem .56rem;
    min-height: 68px;
}
[data-testid="stMetricLabel"] { color: var(--ah-muted); font-size: .72rem !important; }
[data-testid="stMetricValue"] { font-size: 1.28rem !important; font-weight: 650; letter-spacing: -.02em; }
[data-testid="stDataFrame"] { background: var(--ah-surface); }

/* 场景卡：构建库用，不再是一行一行的 divider */
.ah-scenario-card { min-height: 100%; }
.ah-card-head { display: flex; align-items: flex-start; gap: .55rem; }
.ah-card-icon {
    width: 30px; height: 30px; border-radius: 9px; flex: 0 0 30px;
    display: inline-flex; align-items: center; justify-content: center;
    background: var(--ah-accent-soft); font-size: 1rem;
}
.ah-card-title { font-weight: 650; font-size: .92rem; line-height: 1.35; }
.ah-card-id { color: var(--ah-muted); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .68rem; }
.ah-card-desc { color: var(--ah-muted); font-size: .875rem; line-height: 1.55; min-height: 2.45rem; margin: .45rem 0 .5rem; }
.ah-card-badges { display: flex; flex-wrap: wrap; gap: .28rem; margin-bottom: .55rem; }
.ah-tag {
    border: 1px solid var(--ah-border); border-radius: 999px;
    padding: .08rem .42rem; font-size: .66rem; color: var(--ah-muted);
    background: #FAFBFC; white-space: nowrap;
}
.ah-tag-ok { color: #067647; border-color: #ABEFC6; background: #ECFDF3; }
.ah-tag-draft { color: #B54708; border-color: #FEDF89; background: #FFFAEB; }
.ah-tag-blue { color: var(--ah-accent); border-color: #C7D7FE; background: var(--ah-accent-soft); }
[class*="st-key-build-card-"] [data-testid="stVerticalBlockBorderWrapper"] {
    height: 100%;
    padding: .85rem .9rem .55rem;
    background: var(--ah-surface);
    border: 1px solid var(--ah-border) !important;
    border-radius: var(--ah-radius) !important;
    box-shadow: 0 1px 2px rgba(16, 24, 40, .025);
}
[class*="st-key-build-card-"] [data-testid="stButton"] button {
    justify-content: flex-end;
    border: 0 !important;
    background: transparent !important;
    box-shadow: none !important;
    color: var(--ah-accent) !important;
    font-weight: 550;
    padding: .18rem .2rem;
}
[class*="st-key-build-card-"] [data-testid="stButton"] button:hover {
    background: var(--ah-accent-soft) !important;
}
[class*="st-key-build-back"] button,
[class*="st-key-build-link"] button {
    border: 0 !important;
    background: transparent !important;
    color: var(--ah-muted) !important;
    box-shadow: none !important;
    padding-left: 0 !important;
}
[class*="st-key-build-back"] button:hover,
[class*="st-key-build-link"] button:hover {
    color: var(--ah-accent) !important;
    background: transparent !important;
}
[class*="st-key-build-chat"] button {
    border-radius: 999px !important;
    padding-left: .85rem !important;
    padding-right: .85rem !important;
}
[class*="st-key-editor-workflow-del"] button {
    border: 0 !important;
    background: transparent !important;
    color: #B42318 !important;
    justify-content: flex-start;
    padding-left: 0 !important;
    font-size: .78rem !important;
    min-height: 1.8rem !important;
}
[class*="st-key-chat-new"] button,
[class*="st-key-chat-edit"] button {
    border: 0 !important;
    background: transparent !important;
    box-shadow: none !important;
    color: var(--ah-muted) !important;
}
[class*="st-key-chat-new"] button:hover,
[class*="st-key-chat-edit"] button:hover {
    color: var(--ah-accent) !important;
    background: var(--ah-accent-soft) !important;
}

/* 构建详情 / 质量页上下文条 */
.ah-context {
    display: flex; align-items: center; justify-content: space-between;
    gap: 1rem; padding: .1rem 0 .2rem;
}
.ah-breadcrumb { color: var(--ah-muted); font-size: .72rem; margin-bottom: .2rem; }
.ah-breadcrumb b { color: var(--ah-ink); font-weight: 600; }
.ah-detail-title {
    font-size: 1.5rem !important;
    line-height: 1.2 !important;
    font-weight: 650 !important;
    letter-spacing: -.02em;
    margin: .05rem 0 .22rem !important;
}

/* 对话页：入口栏是一张卡，不再是裸按钮列表；空态有明确起点 */
.st-key-chat-rail-card { padding: .65rem .6rem .55rem; }
.st-key-chat-rail-card [data-testid="stVerticalBlockBorderWrapper"] {
    padding: .55rem .45rem .35rem;
    background: var(--ah-surface);
    border: 1px solid var(--ah-border) !important;
    border-radius: var(--ah-radius) !important;
}
.st-key-chat-welcome [data-testid="stVerticalBlockBorderWrapper"] {
    padding: .65rem .75rem .55rem;
    background: var(--ah-surface);
    border: 1px solid var(--ah-border) !important;
    border-radius: var(--ah-radius) !important;
}
.st-key-chat-rail-card [data-testid="stButton"] button { justify-content: flex-start; }
.st-key-chat-welcome { padding: .85rem 1rem .75rem; }
.st-key-chat-welcome [data-testid="stVerticalBlockBorderWrapper"] { padding: .65rem .75rem .55rem; }
.ah-chat-welcome { padding: 1.4rem 1.5rem 1.2rem; }
.ah-chat-welcome h3 { margin: 0 0 .2rem !important; font-size: 1.05rem !important; }
.ah-chat-welcome p { margin: 0 0 .85rem; color: var(--ah-muted); font-size: .82rem; line-height: 1.6; }
.ah-chat-capabilities { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .55rem; margin-top: .8rem; }
.ah-chat-cap {
    border: 1px solid var(--ah-border); border-radius: 10px;
    padding: .55rem .6rem; background: #FAFBFC;
}
.ah-chat-cap b { display: block; font-size: .76rem; margin-bottom: .12rem; }
.ah-chat-cap span { color: var(--ah-muted); font-size: .7rem; line-height: 1.45; }

/* 质量页控制条：场景选择与两级视图放进同一张卡，避免控件散落 */
.st-key-quality-context { padding: .7rem .8rem .55rem; }
.st-key-quality-context [data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--ah-surface);
    border: 1px solid var(--ah-border) !important;
    border-radius: var(--ah-radius) !important;
    box-shadow: 0 1px 2px rgba(16, 24, 40, .025);
    padding: .7rem .8rem .5rem;
}
.st-key-quality-context [data-testid="stSelectbox"] { margin-bottom: 0; }
.st-key-quality-context [data-testid="stButtonGroup"] { margin: 0; }
.ah-quality-view { color: var(--ah-muted); font-size: .74rem; margin: .3rem 0 .1rem; }

/* 键盘可达：Streamlit 默认 focus 很淡，补一个不依赖颜色的焦点环 */
button:focus-visible, a:focus-visible, [role="button"]:focus-visible, input:focus-visible, textarea:focus-visible {
    outline: 2px solid var(--ah-accent) !important;
    outline-offset: 2px !important;
}

/* 窄屏：把卡片行折成两列/一列，别把 4 张卡硬塞进 1024 */
@media (max-width: 1180px) {
    [data-testid="stHorizontalBlock"]:has([class*="st-key-build-card-"]) {
        display: grid !important;
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        gap: .8rem !important;
    }
    [data-testid="stHorizontalBlock"]:has([class*="st-key-build-card-"]) > div {
        width: auto !important;
        min-width: 0 !important;
        max-width: none !important;
        flex: none !important;
    }
}
@media (max-width: 900px) {
    .block-container { padding-top: 4rem; padding-left: 1rem !important; padding-right: 1rem !important; }
    .ah-page-head { flex-direction: column; align-items: flex-start; gap: .35rem; }
    .ah-page-meta { white-space: normal; }
    [data-testid="stHorizontalBlock"]:has(.st-key-chat-rail-card) {
        flex-direction: column;
    }
    [data-testid="stHorizontalBlock"]:has(.st-key-chat-rail-card) > div {
        width: 100% !important;
        flex: 1 1 100% !important;
    }
    .ah-chat-capabilities { grid-template-columns: 1fr; }
    .st-key-quality-context [data-testid="stHorizontalBlock"] { flex-direction: column; }
}
@media (max-width: 760px) {
    [data-testid="stHorizontalBlock"]:has([class*="st-key-build-card-"]) {
        grid-template-columns: 1fr !important;
    }
}
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: .01ms !important;
        transition-duration: .01ms !important;
        scroll-behavior: auto !important;
    }
}
</style>
"""


@dataclass(frozen=True)
class Kpi:
    label: str
    value: str
    help: str = ""


def inject_css() -> None:
    """在 set_page_config 之后注入一次；只用主题中立颜色。"""
    st.markdown(_CSS + _CSS_EXTRA, unsafe_allow_html=True)


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
    """页面标题 + 一行说明 + 右侧数据时间；统一走一套 HTML 节奏。"""
    description_html = f"<p>{escape(description)}</p>" if description else ""
    meta_html = f'<div class="ah-page-meta">{escape(meta)}</div>' if meta else ""
    st.markdown(
        f'<div class="ah-page-head"><div><h1>{escape(title)}</h1>'
        f"{description_html}</div>{meta_html}</div>",
        unsafe_allow_html=True,
    )


def section(title: str, caption: str | None = None) -> None:
    caption_html = f'<div class="ah-section-caption">{escape(caption)}</div>' if caption else ""
    st.markdown(
        f'<div class="ah-section"><div class="ah-section-title">{escape(title)}</div>'
        f"{caption_html}</div>",
        unsafe_allow_html=True,
    )


def kpi_row(items: Sequence[Kpi], columns: int = KPI_COLUMNS) -> None:
    """最多 `columns` 个指标一行；多出来的另起一行，保持列宽一致。"""
    items = list(items)
    if not items:
        return
    columns = max(1, int(columns))
    for start in range(0, len(items), columns):
        chunk = items[start:start + columns]
        cols = st.columns(len(chunk), gap="small", vertical_alignment="top")
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
