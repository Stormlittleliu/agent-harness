# -*- coding: utf-8 -*-
"""场景编辑视图：把 spec 层搬到控制台里（受约束的低代码）。

能做什么：

- 编辑基本信息（描述 / 系统提示词 / 工具白名单 / harness 开关）；
- 增删工作流与节点，节点只能引用已注册的块，参数按块的参数契约渲染表单；
- 编辑边（含 START / END），保存前先编译；
- 保存成新版本 spec、载入历史版本、预览编译结果；
- 单向 eject：把场景永久转成 code-owned（不可逆，需要写原因）。

不能做什么（也是刻意的）：

- 不能在界面里写代码，不能引用工具池之外的工具；
- 不能改中间件实现，只能显式开关策略（关闭必须写理由）；
- 已 eject 的场景只读。
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import streamlit as st

from core.agent.pipeline import available_policies
from core.interfaces.dashboard.layout import (
    compact_table,
    empty_state,
    graph_dot,
    page_header,
    section,
)
from core.scenarios import spec_edit
from core.scenarios.generic import CODE_ROOT, spec_scenario_names, spec_tool_names
from core.scenarios.ownership import OWNER_CODE, eject, status
from core.scenarios.spec import SpecError, SPEC_ROOT, build_workflows
from core.scenarios.spec_nodes import block_desc, block_label, block_params, registered_nodes

NAME_HINT = "只用小写字母、数字和下划线，例如 note_qa"
MODE_CANVAS = "🎨 可视化画布"
MODE_FORM = "📝 表单"


def _status_rows() -> list[dict]:
    """列出所有带 spec 的场景及其归属状态。"""
    rows: list[dict] = []
    if not SPEC_ROOT.is_dir():
        return rows
    for directory in sorted(SPEC_ROOT.iterdir()):
        if not directory.is_dir():
            continue
        info = status(directory.name)
        versions = spec_edit.versions(directory.name)
        active = next((row["版本"] for row in versions if row["当前"]), "—")
        owner = info.get("owner") or "spec（未构建）"
        editable = info.get("owner") != OWNER_CODE and info.get("hash_match") is not False
        next_action = info.get("next_action") if info.get("owner") else "可低代码编辑"
        rows.append({
            "场景": directory.name,
            "归属": owner,
            "可编辑": "是" if editable else "否",
            "版本数": len(versions),
            "当前版本": active,
            "下一步": next_action or "—",
        })
    return rows


def _reset_agent_caches() -> None:
    """保存/eject 之后要让缓存的 Agent 与编译图失效。"""
    try:
        from core.interfaces.dashboard.architecture import _graphs
        from core.interfaces.dashboard.common import load_agent

        load_agent.clear()
        _graphs.clear()
    except Exception:  # noqa: BLE001 - 缓存清了没清都不该挡住保存
        pass


def _bump_generation() -> None:
    """结构变了就换一整套 widget key，避免旧控件的值串到新结构上。"""
    st.session_state["editor-gen"] = int(st.session_state.get("editor-gen", 0)) + 1


def _draft_for(name: str) -> dict:
    """当前正在编辑的草稿；切换场景时重新从磁盘载入。"""
    if st.session_state.get("editor-current") != name or "editor-draft" not in st.session_state:
        st.session_state["editor-draft"] = spec_edit.load_draft(name, tools=spec_tool_names())
        st.session_state["editor-current"] = name
        st.session_state["editor-errors"] = []
        _bump_generation()
    return st.session_state["editor-draft"]


def _rows_of(table) -> list[dict]:
    """data_editor 可能回 DataFrame，也可能回 list[dict]，统一成 list[dict]。"""
    if hasattr(table, "to_dict"):
        return list(table.to_dict("records"))
    return [dict(row) for row in (table or [])]


def _render_basics(draft: dict, prefix: str, tools: list[str]) -> None:
    draft["description"] = st.text_input(
        "场景描述",
        value=str(draft.get("description") or ""),
        key=f"{prefix}-desc",
    )
    draft["system_prompt"] = st.text_area(
        "系统提示词",
        value=str(draft.get("system_prompt") or ""),
        height=110,
        key=f"{prefix}-prompt",
        help="会原样交给 Agent；把「必须引用来源」「不许编造」这类硬约束写进去。",
    )
    selected = st.multiselect(
        "工具白名单",
        tools,
        default=[name for name in (draft.get("tools") or []) if name in tools],
        key=f"{prefix}-tools",
        help="只来自通用工具池（笔记检索 / 读写 / 记忆 / 翻译 / 总结）。需要别的工具请 eject 后写代码。",
    )
    draft["tools"] = selected

    harness = draft.setdefault("harness", {})
    left, right = st.columns(2)
    harness["enable_todo"] = left.checkbox(
        "自动 todo",
        value=bool(harness.get("enable_todo")),
        key=f"{prefix}-todo",
        help="复杂任务自动维护 write_todos。",
    )
    harness["enable_summarization"] = left.checkbox(
        "上下文压缩",
        value=bool(harness.get("enable_summarization", True)),
        key=f"{prefix}-summ",
        help="历史超过阈值先摘要再送模型。",
    )
    harness["tool_call_limit"] = int(left.number_input(
        "工具调用上限",
        min_value=1,
        max_value=50,
        value=max(1, int(harness.get("tool_call_limit") or 8)),
        step=1,
        key=f"{prefix}-limit",
    ))
    budget = int(right.number_input(
        "Token 预算（0 = 不限）",
        min_value=0,
        max_value=200000,
        value=int(harness.get("token_budget") or 0),
        step=1000,
        key=f"{prefix}-budget",
    ))
    harness["token_budget"] = budget or None
    right.caption("工具白名单决定 Agent 能看见哪些工具；节点参数里的 tool 也只能选这里面的。")


def _render_params(fn: str, args: dict, prefix: str, tools: list[str]) -> dict:
    """按块的参数契约渲染表单；返回规范化后的参数。"""
    values = dict(args or {})
    for param in block_params(fn):
        label = f"{param.name}{'（必填）' if param.required else ''}"
        help_text = param.help or ""
        key = f"{prefix}-{param.name}"
        current = values.get(param.name, param.default)
        if param.type == "bool":
            values[param.name] = st.checkbox(label, value=bool(current), help=help_text, key=key)
        elif param.type in {"int", "float"}:
            minimum = param.minimum if param.minimum is not None else 0
            maximum = param.maximum if param.maximum is not None else 100000
            if param.type == "int":
                minimum, maximum = int(minimum), int(maximum)
                default = current if isinstance(current, (int, float)) else minimum
                default = min(max(int(default), minimum), maximum)
                values[param.name] = int(st.number_input(
                    label, min_value=minimum, max_value=maximum, value=default, step=1,
                    help=help_text, key=key,
                ))
            else:
                default = current if isinstance(current, (int, float)) else float(minimum)
                default = min(max(float(default), float(minimum)), float(maximum))
                values[param.name] = float(st.number_input(
                    label, min_value=float(minimum), max_value=float(maximum),
                    value=default, help=help_text, key=key,
                ))
        elif param.type == "enum":
            choices = list(param.choices or ())
            if not choices:
                continue
            index = choices.index(current) if current in choices else 0
            values[param.name] = st.selectbox(
                label, choices, index=index, help=help_text, key=key,
            )
        elif param.type == "tool_list":
            default = [name for name in (current or []) if name in tools]
            values[param.name] = st.multiselect(
                label, tools, default=default, help=help_text, key=key,
            )
        elif param.type == "str_list":
            text = st.text_input(
                label, value=", ".join(current or []), help=help_text, key=key,
            )
            values[param.name] = [part.strip() for part in text.split(",") if part.strip()]
        else:
            text_value = "" if current is None else str(current)
            if param.name in {"prompt", "system_prompt"}:
                values[param.name] = st.text_area(
                    label, value=text_value, height=90, help=help_text, key=key,
                )
            else:
                values[param.name] = st.text_input(
                    label, value=text_value, help=help_text, key=key,
                )
    return spec_edit.normalize_args(fn, values)


def _render_canvas_editor(
    name: str,
    draft: dict,
    workflow: str,
    prefix: str,
    tools: list[str],
) -> None:
    """可视化画布：拓扑与位置在画布上改，身份与参数在下面的面板改。"""
    from core.interfaces.dashboard.canvas import render_canvas

    errors = st.session_state.get("editor-errors") or []
    payload = spec_edit.canvas_payload(
        name,
        workflow,
        draft,
        errors,
        selected=st.session_state.get("editor-selected"),
    )
    result = render_canvas(payload, key=f"{prefix}-canvas-{workflow}")
    if isinstance(result, dict) and result.get("version") != st.session_state.get("editor-canvas-version"):
        st.session_state["editor-canvas-version"] = result.get("version")
        changed = spec_edit.absorb_canvas(name, workflow, draft, result)
        st.session_state["editor-selected"] = result.get("selected")
        if changed:
            # 结构变了，之前那次校验的结论就过期了。
            st.session_state["editor-errors"] = []
        st.rerun()

    header = st.columns([1.6, 1], vertical_alignment="center")
    header[0].caption("拖节点移动 · 从右侧圆点连到下一个节点 · 点连线删除 · 选中后右上角 × 删节点")
    if header[1].button("重新自动排版", key=f"{prefix}-canvas-relayout"):
        spec_edit.clear_layout(name, workflow)
        _bump_generation()
        st.rerun()

    _render_selected_node(draft, workflow, prefix, tools, "画布上点一个节点，这里改它的 id 与参数。")


def _render_selected_node(
    draft: dict,
    workflow: str,
    prefix: str,
    tools: list[str],
    empty_hint: str,
) -> None:
    """选中节点的身份 + 参数面板（画布与表单两种模式共用）。"""
    nodes = draft["workflows"][workflow]["nodes"]
    selected = st.session_state.get("editor-selected")
    node = next((item for item in nodes if str(item.get("id")) == selected), None)
    if node is None:
        st.info(empty_hint)
        return

    fn = str(node.get("fn"))
    options = registered_nodes()
    col_id, col_fn, col_del = st.columns([1.1, 1.5, 0.5], vertical_alignment="bottom")
    new_id = col_id.text_input(
        "节点 id", value=str(node.get("id")), key=f"{prefix}-sel-id"
    ).strip()
    new_fn = col_fn.selectbox(
        "块",
        options,
        index=options.index(fn) if fn in options else 0,
        format_func=lambda option: f"{block_label(option)}（{option}）",
        key=f"{prefix}-sel-fn",
        help=block_desc(fn),
    )
    if col_del.button("删除节点", key=f"{prefix}-sel-del"):
        index = next(
            (position for position, item in enumerate(nodes) if str(item.get("id")) == selected),
            None,
        )
        if index is not None:
            spec_edit.remove_node(draft, workflow, index)
        st.session_state["editor-selected"] = None
        _bump_generation()
        st.rerun()

    if new_fn != fn:
        node["fn"] = new_fn
        node["args"] = spec_edit.block_defaults(new_fn)
        _bump_generation()
        st.rerun()
    if new_id and new_id != node.get("id"):
        try:
            spec_edit.rename_node(draft, workflow, str(node.get("id")), new_id)
        except SpecError as exc:
            st.error("；".join(exc.errors))
        else:
            st.session_state["editor-selected"] = new_id
            _bump_generation()
            st.rerun()

    st.caption(block_desc(fn) or "该块没有说明。")
    node["args"] = _render_params(
        str(node.get("fn")), node.get("args") or {}, f"{prefix}-sel-{node.get('id')}", tools
    )


def _render_nodes(draft: dict, workflow: str, prefix: str, tools: list[str]) -> None:
    workflow_draft = draft["workflows"][workflow]
    nodes = workflow_draft["nodes"]
    for index, node in enumerate(list(nodes)):
        fn = str(node.get("fn") or "llm_answer")
        with st.expander(
            f"{index + 1:02d}. {node.get('id')} · {block_label(fn)}",
            expanded=len(nodes) <= 3,
        ):
            col_id, col_fn, col_del = st.columns([1.1, 1.5, 0.5], vertical_alignment="bottom")
            new_id = col_id.text_input(
                "节点 id", value=str(node.get("id") or ""), key=f"{prefix}-n{index}-id"
            ).strip()
            if new_id and new_id != node.get("id"):
                node["id"] = new_id
            options = registered_nodes()
            current_fn = str(node.get("fn") or options[0])
            new_fn = col_fn.selectbox(
                "块",
                options,
                index=options.index(current_fn) if current_fn in options else 0,
                format_func=lambda name: f"{block_label(name)}（{name}）",
                key=f"{prefix}-n{index}-fn",
                help=block_desc(current_fn),
            )
            if new_fn != current_fn:
                node["fn"] = new_fn
                node["args"] = spec_edit.block_defaults(new_fn)
                _bump_generation()
                st.rerun()
            if col_del.button("删除", key=f"{prefix}-n{index}-del"):
                spec_edit.remove_node(draft, workflow, index)
                _bump_generation()
                st.rerun()
            st.caption(block_desc(fn) or "该块没有说明。")
            node["args"] = _render_params(
                str(node.get("fn") or fn), node.get("args") or {}, f"{prefix}-n{index}-{fn}", tools
            )

    add_col1, add_col2 = st.columns([1.6, 1])
    block_options = registered_nodes()
    chosen = add_col1.selectbox(
        "新增节点使用的块",
        block_options,
        format_func=lambda name: f"{block_label(name)}（{name}）",
        key=f"{prefix}-add-block",
    )
    if add_col2.button("加一个节点", key=f"{prefix}-add-node"):
        spec_edit.add_node(draft, workflow, chosen)
        _bump_generation()
        st.rerun()


def _render_edges(draft: dict, workflow: str, prefix: str) -> None:
    workflow_draft = draft["workflows"][workflow]
    node_ids = [str(node.get("id")) for node in workflow_draft["nodes"]]
    options = ["__start__", *node_ids, "__end__"]
    rows = [{"从": str(edge[0]), "到": str(edge[1])} for edge in workflow_draft["edges"]]
    if not rows:
        st.caption("还没有边；加一条 START 到第一个节点的边，流程才能开始。")
        if st.button("加第一条边", key=f"{prefix}-edge-first"):
            spec_edit.set_edge(draft, workflow, "__start__", node_ids[0] if node_ids else "__end__")
            _bump_generation()
            st.rerun()
        return
    edited = st.data_editor(
        rows,
        num_rows="dynamic",
        use_container_width=True,
        key=f"{prefix}-edges",
        column_config={
            "从": st.column_config.SelectboxColumn("从", options=options, required=True),
            "到": st.column_config.SelectboxColumn("到", options=options, required=True),
        },
    )
    pairs: list[list[str]] = []
    for row in _rows_of(edited):
        source, target = str(row.get("从") or ""), str(row.get("到") or "")
        if source and target:
            pairs.append([source, target])
    workflow_draft["edges"] = pairs


def _render_policies(draft: dict, prefix: str) -> None:
    policies = draft.get("policies")
    if policies is None:
        st.caption(
            "当前用默认策略（权限 / 超时 / 异常 / 重试 / 模型重试…从场景字段推导）。"
            "需要显式开关某条策略时再打开覆盖。"
        )
        if st.button("改成显式覆盖", key=f"{prefix}-policy-on"):
            draft["policies"] = []
            _bump_generation()
            st.rerun()
        return
    rows = [
        {
            "策略": str(policy.get("name") or ""),
            "启用": bool(policy.get("enabled", True)),
            "理由": str(policy.get("reason") or ""),
            "参数(JSON)": json.dumps(policy.get("args") or {}, ensure_ascii=False),
        }
        for policy in policies
    ]
    if not rows:
        st.caption("还没有覆盖项；加一条就会把该策略显式写进 spec。")
        if st.button("加一条策略覆盖", key=f"{prefix}-policy-add"):
            draft["policies"] = [
                {"name": "permission", "enabled": True, "args": {}, "reason": None}
            ]
            _bump_generation()
            st.rerun()
        return
    edited = st.data_editor(
        rows,
        num_rows="dynamic",
        use_container_width=True,
        key=f"{prefix}-policies",
        column_config={
            "策略": st.column_config.SelectboxColumn(
                "策略", options=available_policies(), required=True,
            ),
            "启用": st.column_config.CheckboxColumn("启用"),
            "理由": st.column_config.TextColumn("理由", help="关闭一条守卫时必须写理由"),
            "参数(JSON)": st.column_config.TextColumn("参数(JSON)", width="medium"),
        },
    )
    parsed: list[dict] = []
    bad_rows: list[int] = []
    for index, row in enumerate(_rows_of(edited)):
        name = str(row.get("策略") or "")
        if not name:
            continue
        raw_args = str(row.get("参数(JSON)") or "{}")
        try:
            args = json.loads(raw_args) if raw_args.strip() else {}
        except json.JSONDecodeError:
            bad_rows.append(index + 1)
            args = {}
        parsed.append({
            "name": name,
            "enabled": bool(row.get("启用")),
            "args": args if isinstance(args, dict) else {},
            "reason": str(row.get("理由") or "") or None,
        })
    if bad_rows:
        st.warning(f"第 {'、'.join(map(str, bad_rows))} 行的参数不是合法 JSON，已按空参数处理。")
    draft["policies"] = parsed


def _compile_preview(draft: dict) -> tuple[dict, list[str]]:
    """用草稿编译一遍图；返回 ``(graphs, errors)``。"""
    try:
        spec = spec_edit.spec_from_draft(draft)
    except SpecError as exc:
        return {}, exc.errors
    stub = SimpleNamespace(
        tools=[SimpleNamespace(name=name) for name in (draft.get("tools") or [])]
    )
    try:
        return build_workflows(spec, stub), []
    except SpecError as exc:
        return {}, exc.errors


def _render_preview(draft: dict, errors: list[str]) -> None:
    section("预览", "保存前先编译：编译不过就看不到图，也不会写盘。")
    if errors:
        for error in errors:
            st.error(error)
        return
    graphs, compile_errors = _compile_preview(draft)
    if compile_errors:
        for error in compile_errors:
            st.error(error)
        return
    if not graphs:
        st.caption("还没有工作流。")
        return
    for name, compiled in graphs.items():
        st.markdown(f"**{name}**")
        with st.container(border=True):
            st.graphviz_chart(graph_dot(compiled.get_graph()), use_container_width=True)


def _render_readonly(name: str, draft: dict) -> None:
    info = status(name)
    if info.get("owner") == OWNER_CODE:
        st.warning(
            f"{name} 已转为 code-owned（{info.get('ejected_at') or '未知时间'}）："
            "spec 不再参与构建，编辑已关闭。改它要动 `core/scenarios/"
            f"{name}/` 下的代码。"
        )
    else:
        st.error(
            "代码与 spec 已经分叉：`core/scenarios/"
            f"{name}/` 被改过，构建会直接失败。先运行 `python -m core.scenarios.eject {name}`"
            "把它转成 code-owned，再来这里看历史 spec。"
        )
    st.json(draft, expanded=False)


def render_editor(current: str | None = None) -> None:
    page_header(
        "场景编辑",
        "受约束的低代码：节点只能引用已注册的块，参数按块契约校验，保存即新版本 spec。",
        meta="保存前会编译；校验不过不写盘。",
    )

    rows = _status_rows()
    if rows:
        section("spec 场景", "归属由 `data/specs/<name>/state.json` 决定；eject 是单向门。")
        compact_table(
            rows,
            height=170,
            key="editor-status",
            column_order=["场景", "归属", "可编辑", "版本数", "当前版本", "下一步"],
        )
    else:
        empty_state("还没有任何 spec 场景；先在下面新建一个。")

    left, right = st.columns([1.2, 1], vertical_alignment="bottom")
    existing = [row["场景"] for row in rows] or spec_scenario_names()
    # 新建场景后要把下拉框切过去；widget 创建后不能直接改它的 state，这里排队到下一次 run。
    pending_select = st.session_state.pop("editor-pending-select", None)
    if pending_select and pending_select in existing:
        st.session_state["editor-scenario"] = pending_select
    # 默认落在"侧边栏当前选中的场景"上：场景库选中谁，这里就编辑谁。
    if "editor-scenario" not in st.session_state and current in existing:
        st.session_state["editor-scenario"] = current
    choice = left.selectbox(
        "编辑场景",
        existing,
        key="editor-scenario",
        help="只列出 data/specs 下已有 spec 的场景。",
    ) if existing else ""
    with right:
        with st.form("editor-create", clear_on_submit=True):
            new_name = st.text_input("新建场景名", placeholder="note_qa", help=NAME_HINT)
            if st.form_submit_button("创建并保存 v1"):
                name = (new_name or "").strip()
                if not name.replace("_", "").isalnum() or name != name.lower():
                    st.error(f"名字不合法：{NAME_HINT}")
                elif name in spec_scenario_names() or (SPEC_ROOT / name).exists():
                    st.error(f"场景已存在：{name}")
                else:
                    # 默认用检索工具：模板里的 retrieve 块会带 query/limit 调它。
                    pool = spec_tool_names()
                    default_tool = "search_notes" if "search_notes" in pool else (pool[0] if pool else None)
                    try:
                        path = spec_edit.save_draft(
                            spec_edit.new_draft(
                                name, tools=[default_tool] if default_tool else []
                            ),
                            tool_names=set(pool),
                        )
                    except SpecError as exc:
                        st.error("；".join(exc.errors))
                    else:
                        st.session_state["editor-notice"] = f"已创建 {name}：{path}"
                        st.session_state["editor-pending-select"] = name
                        st.session_state["editor-current"] = ""  # 下一轮按新场景重新载入
                        _reset_agent_caches()
                        st.rerun()

    notice = st.session_state.pop("editor-notice", None)
    if notice:
        st.success(notice)
    if not choice:
        return

    draft = _draft_for(choice)
    prefix = f"ed-{st.session_state.get('editor-gen', 0)}"
    info = status(choice)
    if info.get("owner") == OWNER_CODE or info.get("hash_match") is False:
        _render_readonly(choice, draft)
        return

    tools = spec_tool_names()
    section("基本信息", "这一层直接决定 Agent 的行为边界。")
    _render_basics(draft, prefix, tools)

    section("工作流", "节点只能引用已注册的块；删节点不会自动重连，悬空边会被校验拦下。")
    workflow_names = list((draft.get("workflows") or {}).keys())
    control_left, control_right = st.columns([1.4, 1], vertical_alignment="bottom")
    workflow = control_left.selectbox(
        "工作流", workflow_names, key=f"{prefix}-workflow"
    ) if workflow_names else ""
    if st.session_state.get("editor-workflow-current") != workflow:
        st.session_state["editor-workflow-current"] = workflow
        st.session_state["editor-selected"] = None
    with control_right:
        with st.form(f"{prefix}-workflow-new", clear_on_submit=True):
            workflow_name = st.text_input("新增工作流名", placeholder="report")
            if st.form_submit_button("新增"):
                try:
                    spec_edit.add_workflow(draft, workflow_name)
                except SpecError as exc:
                    st.error("；".join(exc.errors))
                else:
                    _bump_generation()
                    st.rerun()

    if workflow:
        mode = st.radio(
            "编辑方式",
            [MODE_CANVAS, MODE_FORM],
            horizontal=True,
            key=f"{prefix}-mode",
            help="画布：拖块、连线、移动；表单：逐节点展开，适合同屏改多个参数。",
        )
        if mode == MODE_CANVAS:
            _render_canvas_editor(choice, draft, workflow, prefix, tools)
        else:
            _render_nodes(draft, workflow, prefix, tools)
            st.markdown("**边**（从 → 到；`__start__` / `__end__` 是入口与出口）")
            _render_edges(draft, workflow, prefix)
        if len(workflow_names) > 1:
            if st.button(f"删除工作流 {workflow}", key=f"{prefix}-workflow-del"):
                try:
                    spec_edit.remove_workflow(draft, workflow)
                except SpecError as exc:
                    st.error("；".join(exc.errors))
                else:
                    _bump_generation()
                    st.rerun()

    with st.expander("高级：策略覆盖（中间件）", expanded=False):
        _render_policies(draft, prefix)

    with st.expander("版本与导出", expanded=False):
        version_rows = spec_edit.versions(choice)
        if version_rows:
            compact_table(version_rows, height=150, key=f"{prefix}-versions")
            options = [row["文件"] for row in version_rows]
            picked = st.selectbox("载入哪个版本到编辑器", options, key=f"{prefix}-version-pick")
            if st.button("载入这个版本", key=f"{prefix}-version-load"):
                st.session_state["editor-draft"] = spec_edit.load_version(choice, picked)
                st.session_state["editor-errors"] = []
                _bump_generation()
                st.rerun()
        st.caption(f"spec 目录：`{SPEC_ROOT / choice}`")
        st.download_button(
            "下载当前草稿 JSON",
            data=json.dumps(draft, ensure_ascii=False, indent=2),
            file_name=f"{choice}.json",
            mime="application/json",
            key=f"{prefix}-download",
        )

    errors = st.session_state.get("editor-errors") or []
    _render_preview(draft, errors)

    section("保存", "校验 + 编译都通过才会生成新版本。")
    save_col, check_col, eject_col = st.columns([1, 1, 2], vertical_alignment="bottom")
    if check_col.button("只校验，不保存", key=f"{prefix}-check"):
        st.session_state["editor-errors"] = spec_edit.draft_errors(draft, set(tools))
        st.rerun()
    if save_col.button("保存为新版本", type="primary", key=f"{prefix}-save"):
        try:
            path = spec_edit.save_draft(draft)
        except SpecError as exc:
            st.session_state["editor-errors"] = exc.errors
        else:
            st.session_state["editor-errors"] = []
            st.session_state["editor-notice"] = f"已保存：{path}（新版本已设为 active）"
            _reset_agent_caches()
            _bump_generation()
        st.rerun()

    with eject_col:
        has_code = (CODE_ROOT / choice).is_dir()
        with st.expander("转为代码（eject）", expanded=False):
            st.caption(
                "单向门：spec 失效、构建改用代码、这里变只读。"
                + ("原本就有代码目录。" if has_code else
                   "这个场景还没有代码目录，eject 后需要自己写 `core/scenarios/"
                   f"{choice}/scenario.py`，否则它会从场景列表里消失。")
            )
            reason = st.text_input("原因", key=f"{prefix}-eject-reason")
            confirmed = st.checkbox(
                "我确认放弃这份 spec 的编辑能力", key=f"{prefix}-eject-confirm"
            )
            if st.button(
                "eject",
                key=f"{prefix}-eject",
                disabled=not (reason.strip() and confirmed and has_code),
                help="需要填原因 + 勾确认 + 已存在代码目录",
            ):
                eject(choice, reason=reason.strip())
                _reset_agent_caches()
                st.session_state["editor-notice"] = f"{choice} 已转为 code-owned"
                _bump_generation()
                st.rerun()
