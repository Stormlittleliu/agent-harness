# -*- coding: utf-8 -*-
"""构建端：场景库 → 场景详情（结构 / 工具与策略 / 发布）。

为什么要分两级：场景是这里的工作对象，页面只是它的一个动作。
旧控制台把"场景"塞进全局侧边栏，再让 8 个平级页面共享它，结果是换场景时
只能靠清空一大堆 key 来防串台。现在场景由路由携带，页面自己不再有全局选择器。

发布是这一层独有的动作：结构改完不点发布，用户端看不到。
"""
from __future__ import annotations

import streamlit as st

from core.interfaces.console import routes
from core.interfaces.dashboard.architecture import render_architecture
from core.interfaces.dashboard.common import load_agent
from core.interfaces.dashboard.editor import render_editor
from core.interfaces.dashboard.layout import compact_table, empty_state, page_header, section
from core.scenarios import entry as entries
from core.scenarios import library, spec_edit

TABS = ("overview", "structure", "tools", "publish")
TAB_LABELS = {
    "overview": "概览",
    "structure": "结构",
    "tools": "工具与策略",
    "publish": "发布",
    "runtime": "运行窗口",
}


def render(route: routes.Route) -> None:
    if not route.scenario:
        _library()
    else:
        _detail(route.scenario, route)


# ---------------------------------------------------------------- 场景库


def _library() -> None:
    items = library.entries()
    published = set(entries.published_names())
    page_header(
        "构建 / 场景库",
        "所有场景都在这里：打开一个就能改结构、看工具与策略、发布成对话入口。",
        meta=f"{len(items)} 个场景 · {len(published)} 个已发布",
    )
    if not items:
        empty_state("场景库是空的。")
        return

    header = st.columns([3.2, 5.8, 1.2], vertical_alignment="bottom")
    header[0].caption("场景")
    header[1].caption("说明 / 状态")
    for info in items:
        item = entries.load_entry(info.name)
        row = st.columns([3.2, 5.8, 1.2], vertical_alignment="center")
        row[0].markdown(f"**{info.icon} {info.label}**  \n`{info.name}`")
        row[1].caption(info.description or "（没有描述）")
        badges = [
            info.badge,
            "已发布" if item.name in published else "未发布",
            f"用例 {info.cases}",
        ]
        row[1].caption(" · ".join(badges))
        if row[2].button("打开", key=f"build-open-{info.name}", use_container_width=True):
            routes.navigate("build", info.name)
        st.divider()

    _create_form()


def _create_form() -> None:
    """新建场景：默认给一个检索工具，保存成 v1 并立刻设为 active。"""
    from core.scenarios.generic import spec_scenario_names, spec_tool_names
    from core.scenarios.spec import SPEC_ROOT, SpecError

    with st.expander("新建场景", expanded=False):
        st.caption("新建后它会立刻出现在场景库里；发布入口仍然要单独点一次。")
        with st.form("build-create", clear_on_submit=True):
            new_name = st.text_input(
                "场景名",
                placeholder="note_qa",
                help="只用小写字母、数字和下划线，例如 note_qa",
            )
            if st.form_submit_button("创建 v1"):
                name = (new_name or "").strip()
                if not name.replace("_", "").isalnum() or name != name.lower():
                    st.error("名字不合法：只用小写字母、数字和下划线")
                elif name in spec_scenario_names() or (SPEC_ROOT / name).exists():
                    st.error(f"场景已存在：{name}")
                else:
                    pool = spec_tool_names()
                    default_tool = "search_notes" if "search_notes" in pool else (pool[0] if pool else None)
                    try:
                        spec_edit.save_draft(
                            spec_edit.new_draft(name, tools=[default_tool] if default_tool else []),
                            tool_names=set(pool),
                        )
                    except SpecError as exc:
                        st.error("；".join(exc.errors))
                    else:
                        load_agent.clear()
                        routes.navigate("build", name)


# ---------------------------------------------------------------- 场景详情


def _detail(name: str, route: routes.Route) -> None:
    info = library.entry(name)
    if info is None:
        st.error(f"场景不存在：`{name}`")
        if st.button("返回场景库"):
            routes.navigate("build")
        return
    item = entries.load_entry(name)
    _detail_header(name, info, item)

    notice = st.session_state.pop(f"build:notice:{name}", None)
    if notice:
        st.success(notice)

    default = route.tab if route.tab in TAB_LABELS else "overview"
    tabs = list(TABS) + (["runtime"] if info.supports_runtime else [])
    if default not in tabs:
        default = "overview"
    tab = st.radio(
        "页签",
        tabs,
        index=tabs.index(default),
        format_func=lambda value: TAB_LABELS[value],
        horizontal=True,
        key=f"build:tab:{name}",
        label_visibility="collapsed",
    )
    if tab == "overview":
        _overview(name, info, item)
    elif tab == "structure":
        section("结构", "画布 / 表单改的是 spec；保存即新版本。")
        render_editor(name, embedded=True)
    elif tab == "tools":
        _tools(name)
    elif tab == "runtime":
        _runtime(name)
    else:
        _publish(name, info, item)


def _detail_header(name: str, info: library.ScenarioEntry, item: entries.ChatEntry) -> None:
    left, right = st.columns([3.4, 2.6], vertical_alignment="center")
    with left:
        st.markdown(f"### {info.icon} {info.label}")
        st.caption(info.description or "（没有描述）")
        badges = [info.badge, "已发布" if item.enabled else "未发布"]
        if item.enabled and entries.drifted(name):
            badges.append("有未发布改动")
        st.caption(f"`{name}` · " + " · ".join(badges) + f" · 用例 {info.cases}")
    with right:
        buttons = st.columns(3)
        if buttons[0].button("返回场景库", key=f"build-back:{name}", use_container_width=True):
            routes.navigate("build")
        if buttons[1].button(
            "对话入口" if item.enabled else "未发布",
            key=f"build-chat:{name}",
            disabled=not item.enabled,
            use_container_width=True,
        ):
            routes.navigate("chat", name)
        if buttons[2].button("复制链接", key=f"build-link:{name}", use_container_width=True):
            st.session_state[f"build:show-link:{name}"] = True
    if st.session_state.get(f"build:show-link:{name}"):
        st.code(routes.link("chat", name), language=None)


def _overview(name: str, info: library.ScenarioEntry, item: entries.ChatEntry) -> None:
    versions = spec_edit.versions(name) if info.from_spec else []
    active = next((row["版本"] for row in versions if row["当前"]), "—")
    section("基本信息")
    st.markdown(
        "\n".join(
            [
                f"- **场景 id**：`{info.name}`",
                f"- **类型**：{'总路由' if info.is_router else '普通 Agent'}",
                f"- **归属**：{'spec（可编辑）' if info.editable else '代码 / 只读'}",
                f"- **当前版本**：{active}（共 {len(versions)} 个版本）",
                f"- **用例**：{info.cases} 条",
                f"- **对话入口**：{'已发布 · ' + routes.link('chat', name) if item.enabled else '未发布'}",
            ]
        )
    )
    if info.examples:
        section("示例任务", "对话页的空状态会拿这些当开场白。")
        for example in info.examples:
            st.code(example, language="text")
    if versions:
        section("版本", "保存结构会生成新版本并设为 active；载入旧版本在「结构」页签里。")
        compact_table(versions, height=170, key=f"build-versions:{name}")
    if info.issue:
        st.error(info.issue)


def _tools(name: str) -> None:
    section("工具与策略", "工具来自工具箱；中间件按 slot 排序，策略只能显式开关。")
    try:
        with st.spinner("正在加载 Agent 与知识库…"):
            agent = load_agent(name)
    except Exception as exc:  # noqa: BLE001 - 页面给出原因，不抛 traceback
        st.error(f"加载失败：{type(exc).__name__}: {exc}")
        return
    render_architecture(agent)


def _runtime(name: str) -> None:
    """coding_demo 的运行窗口：任务图 / 任务详情 / 命令日志。"""
    from core.interfaces.dashboard.runtime import render_runtime

    section("运行窗口", "任务图、命令日志与可执行任务；只读已有文件，点执行才会调模型。")
    try:
        with st.spinner("正在加载 Agent 与知识库…"):
            agent = load_agent(name)
    except Exception as exc:  # noqa: BLE001
        st.error(f"加载失败：{type(exc).__name__}: {exc}")
        return
    render_runtime(agent)


def _publish(name: str, info: library.ScenarioEntry, item: entries.ChatEntry) -> None:
    section(
        "对话入口",
        "发布前会做静态校验（不调用模型）；校验不过不会写盘。",
    )
    if not info.from_spec:
        st.warning("这是代码场景，不能从控制台发布。先让它由 spec 接管。")
        return

    link = routes.link("chat", name)
    if item.enabled:
        st.success(f"已发布：`{link}`")
        if entries.drifted(name):
            st.warning("发布后改过结构：入口现在仍是上次发布的状态，重新发布才会用上新结构。")
    else:
        st.info("未发布：对话端看不到这个场景。")

    if st.button("只校验（不写盘）", key=f"build-validate:{name}"):
        errors = entries.validate(name)
        st.session_state[f"build:errors:{name}"] = errors
    errors = st.session_state.get(f"build:errors:{name}") or []
    if errors:
        st.error("校验没过：")
        for error in errors:
            st.markdown(f"- {error}")
    elif f"build:errors:{name}" in st.session_state:
        st.success("校验通过。")

    with st.form(f"build-publish-form:{name}"):
        title = st.text_input(
            "入口标题",
            value=item.title or info.label,
            help="对话入口卡片上的名字；留空就用场景名。",
        )
        tagline = st.text_input(
            "一句话介绍",
            value=item.tagline or info.description,
            help="告诉用户这个入口能干什么，一句话就够。",
        )
        starters = st.text_area(
            "开场白（一行一条）",
            value="\n".join(item.starters),
            height=90,
            help="会话为空时显示成按钮，点了就直接发出去。",
        )
        order = st.number_input(
            "排序（小的在前）",
            min_value=0,
            max_value=999,
            value=int(item.order),
            step=10,
        )
        submitted = st.form_submit_button("校验并发布", type="primary")
    if submitted:
        rows = [line.strip() for line in starters.splitlines() if line.strip()]
        try:
            entries.publish(name, title=title, tagline=tagline, starters=rows, order=int(order))
        except entries.EntryError as exc:
            st.session_state[f"build:errors:{name}"] = exc.errors
        else:
            st.session_state[f"build:errors:{name}"] = []
            st.session_state[f"build:notice:{name}"] = f"已发布：{name}"
        st.rerun()

    if item.enabled:
        with st.expander("撤回入口", expanded=False):
            st.caption("撤回只关掉入口，spec 和产品信息都保留。")
            if st.button("撤回", key=f"build-unpublish:{name}"):
                entries.unpublish(name)
                st.session_state[f"build:notice:{name}"] = f"已撤回：{name}"
                st.rerun()
