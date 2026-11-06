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

import copy
import json
from datetime import datetime
from pathlib import Path
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
from core.scenarios.spec import SpecError, SPEC_ROOT, build_workflows, split_edge
from core.scenarios.spec_nodes import block_desc, block_label, block_params, registered_nodes

NAME_HINT = "只用小写字母、数字和下划线，例如 note_qa"
MODE_CANVAS = "🎨 可视化画布"
MODE_FORM = "📝 表单"
DRAFT_ROOT = Path("data/runtime/spec_drafts")
HISTORY_LIMIT = 50


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


def _draft_path(name: str) -> Path:
    return DRAFT_ROOT / f"{name}.json"


def _drafts() -> dict[str, dict]:
    return st.session_state.setdefault("editor:drafts", {})


def _bases() -> dict[str, dict]:
    return st.session_state.setdefault("editor:bases", {})


def _undo_stacks() -> dict[str, list]:
    return st.session_state.setdefault("editor:undo", {})


def _redo_stacks() -> dict[str, list]:
    return st.session_state.setdefault("editor:redo", {})


def _runtime_draft(name: str) -> dict | None:
    """崩溃恢复用的草稿；文件坏了就当没有，不让它挡住编辑。"""
    path = _draft_path(name)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    draft = payload.get("draft") if isinstance(payload, dict) else payload
    return draft if isinstance(draft, dict) else None


def _draft_for(name: str) -> dict:
    """按场景保存草稿：切走再切回不丢未保存改动。"""
    drafts = _drafts()
    if name not in drafts:
        base = spec_edit.load_draft(name, tools=spec_tool_names())
        draft = copy.deepcopy(base)
        recovered = _runtime_draft(name)
        if recovered is not None and recovered != base:
            draft = recovered
            st.session_state["editor-notice"] = f"已恢复 {name} 的未保存草稿"
        drafts[name] = draft
        _bases()[name] = copy.deepcopy(base)
        _undo_stacks()[name] = []
        _redo_stacks()[name] = []
        st.session_state["editor-errors"] = []
        _bump_generation()
    return drafts[name]


def _draft_base(name: str) -> dict:
    return _bases().get(name) or spec_edit.load_draft(name, tools=spec_tool_names())


def _is_dirty(name: str, draft: dict) -> bool:
    return draft != _draft_base(name)


def _push_undo(name: str, snapshot: dict) -> None:
    undo = _undo_stacks().setdefault(name, [])
    if undo and undo[-1] == snapshot:
        return
    undo.append(copy.deepcopy(snapshot))
    del undo[:-HISTORY_LIMIT]
    _redo_stacks()[name] = []


def _remember(name: str, draft: dict) -> None:
    """改结构/参数前压栈；同一状态不重复压。"""
    _push_undo(name, draft)


def _undo(name: str) -> bool:
    undo = _undo_stacks().setdefault(name, [])
    if not undo:
        return False
    current = copy.deepcopy(_drafts()[name])
    _drafts()[name] = undo.pop()
    _redo_stacks().setdefault(name, []).append(current)
    return True


def _redo(name: str) -> bool:
    redo = _redo_stacks().setdefault(name, [])
    if not redo:
        return False
    current = copy.deepcopy(_drafts()[name])
    _drafts()[name] = redo.pop()
    _undo_stacks().setdefault(name, []).append(current)
    return True


def _autosave(name: str, draft: dict) -> None:
    """未保存草稿写到运行时目录；不进 spec、不进 git，用于崩溃恢复。"""
    if not _is_dirty(name, draft):
        _clear_runtime_draft(name)
        return
    path = _draft_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "draft": draft,
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _clear_runtime_draft(name: str) -> None:
    path = _draft_path(name)
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass


def _rows_of(table) -> list[dict]:
    """data_editor 可能回 DataFrame，也可能回 list[dict]，统一成 list[dict]。"""
    if hasattr(table, "to_dict"):
        return list(table.to_dict("records"))
    return [dict(row) for row in (table or [])]


def _render_basics(name: str, draft: dict, prefix: str, tools: list[str]) -> None:
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
    _render_prompt_blocks(name, draft, prefix)
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


def _render_prompt_blocks(name: str, draft: dict, prefix: str) -> None:
    """提示词分块：列出块、看拼接结果、按场景覆盖某一块。"""
    from core.prompts.assemble import PromptContext, assemble
    from core.prompts.blocks import load_book

    prompt = draft.get("prompt") or {}
    block_ids = [str(item) for item in (prompt.get("blocks") or [])]
    if not block_ids:
        return
    book = load_book(SPEC_ROOT / name / "prompt.yml")
    missing = [block_id for block_id in block_ids if book.get(block_id) is None]
    overrides = dict(prompt.get("overrides") or {})

    context = PromptContext(
        name=name,
        kind=str(draft.get("kind") or "agent"),
        tools=tuple(str(item) for item in (draft.get("tools") or [])),
        workflows=tuple((draft.get("workflows") or {}).keys()),
        has_cases=bool(draft.get("cases_path")),
    )
    assembly = assemble(block_ids, book, context, overrides)

    with st.expander(f"提示词分块（{len(block_ids)} 块 · 拼接后 {len(assembly.text)} 字）", expanded=False):
        rows = []
        for index, block_id in enumerate(block_ids, 1):
            block = book.get(block_id)
            rows.append({
                "#": index,
                "块": block_id,
                "标题": block.title if block else "（缺块）",
                "字数": len((overrides.get(block_id) or (block.body if block else "")) or ""),
                "覆盖": "是" if block_id in overrides else "",
            })
        compact_table(rows, height=170, key=f"{prefix}-prompt-blocks", column_order=["#", "块", "标题", "字数", "覆盖"])
        if missing:
            st.error(f"prompt.yml 里缺少这些块：{'、'.join(missing)}")

        picked = st.selectbox(
            "选中一块", [item for item in block_ids if book.get(item) is not None],
            key=f"{prefix}-prompt-block-pick",
        ) if any(book.get(item) for item in block_ids) else None
        if picked:
            block = book.get(picked)
            current = overrides.get(picked, block.body if block else "")
            text = st.text_area("块内容（保存后写入本场景的 overrides）", value=current, height=160,
                                key=f"{prefix}-prompt-block-body-{picked}")
            col_save, col_reset = st.columns([1, 1])
            if col_save.button("保存覆盖", key=f"{prefix}-prompt-block-save"):
                overrides[picked] = text
                draft.setdefault("prompt", {}).setdefault("blocks", block_ids)
                draft["prompt"]["overrides"] = overrides
                _bump_generation()
                st.rerun()
            if col_reset.button("清除覆盖", key=f"{prefix}-prompt-block-reset", disabled=picked not in overrides):
                overrides.pop(picked, None)
                draft["prompt"]["overrides"] = overrides
                _bump_generation()
                st.rerun()
        st.caption("拼接结果（含条件判断与 {tools} 等插值）：")
        with st.container(height=220):
            st.code(assembly.text or "（空）", language="text")


def _mark_param_change() -> None:
    """参数 widget 的 on_change：只标记，不在这里改草稿。

    不能用"渲染后的值 != 草稿值"来推断用户改过参数：首次挂载时的默认值归一化
    也会不相等，那样会把一次粘贴变成两个撤销步。on_change 只在用户真的动了
    控件时触发，撤销栈才是干净的。
    """
    st.session_state["editor-param-changed"] = True


def _render_params(fn: str, args: dict, prefix: str, tools: list[str]) -> dict:
    """按块的参数契约渲染表单；返回规范化后的参数。"""
    values = dict(args or {})
    for param in block_params(fn):
        label = f"{param.name}{'（必填）' if param.required else ''}"
        help_text = param.help or ""
        key = f"{prefix}-{param.name}"
        current = values.get(param.name, param.default)
        if param.type == "bool":
            values[param.name] = st.checkbox(
                label, value=bool(current), help=help_text, key=key,
                on_change=_mark_param_change,
            )
        elif param.type in {"int", "float"}:
            minimum = param.minimum if param.minimum is not None else 0
            maximum = param.maximum if param.maximum is not None else 100000
            if param.type == "int":
                minimum, maximum = int(minimum), int(maximum)
                default = current if isinstance(current, (int, float)) else minimum
                default = min(max(int(default), minimum), maximum)
                values[param.name] = int(st.number_input(
                    label, min_value=minimum, max_value=maximum, value=default, step=1,
                    help=help_text, key=key, on_change=_mark_param_change,
                ))
            else:
                default = current if isinstance(current, (int, float)) else float(minimum)
                default = min(max(float(default), float(minimum)), float(maximum))
                values[param.name] = float(st.number_input(
                    label, min_value=float(minimum), max_value=float(maximum),
                    value=default, help=help_text, key=key, on_change=_mark_param_change,
                ))
        elif param.type == "enum":
            choices = list(param.choices or ())
            if not choices:
                continue
            index = choices.index(current) if current in choices else 0
            values[param.name] = st.selectbox(
                label, choices, index=index, help=help_text, key=key,
                on_change=_mark_param_change,
            )
        elif param.type == "tool_list":
            default = [name for name in (current or []) if name in tools]
            values[param.name] = st.multiselect(
                label, tools, default=default, help=help_text, key=key,
                on_change=_mark_param_change,
            )
        elif param.type == "str_list":
            text = st.text_input(
                label, value=", ".join(current or []), help=help_text, key=key,
                on_change=_mark_param_change,
            )
            values[param.name] = [part.strip() for part in text.split(",") if part.strip()]
        else:
            text_value = "" if current is None else str(current)
            if param.name in {"prompt", "system_prompt"}:
                values[param.name] = st.text_area(
                    label, value=text_value, height=90, help=help_text, key=key,
                    on_change=_mark_param_change,
                )
            else:
                values[param.name] = st.text_input(
                    label, value=text_value, help=help_text, key=key,
                    on_change=_mark_param_change,
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
    selection_key = f"editor-selection:{name}:{workflow}"
    payload = spec_edit.canvas_payload(
        name,
        workflow,
        draft,
        errors,
        selected=st.session_state.get("editor-selected"),
        include_blocks=False,
        selection=st.session_state.get(selection_key),
    )
    # 画布 key 不跟 generation 走：撤销/保存会换一套表单 widget，但不该重挂画布，
    # 否则 iframe 一重建就把缩放/平移视角拉回默认。
    result = render_canvas(payload, key=f"ed-canvas-{name}-{workflow}")
    command_key = f"editor-canvas-command:{workflow}"
    if (
        isinstance(result, dict)
        and result.get("command") in {"undo", "redo"}
        and result.get("version") != st.session_state.get(command_key)
    ):
        st.session_state[command_key] = result.get("version")
        st.session_state["editor-canvas-version"] = result.get("version")
        changed = _undo(name) if result.get("command") == "undo" else _redo(name)
        if changed:
            _bump_generation()
            st.rerun()
        return
    if isinstance(result, dict) and result.get("version") != st.session_state.get("editor-canvas-version"):
        st.session_state["editor-canvas-version"] = result.get("version")
        before = copy.deepcopy(draft)
        clipboard = st.session_state.get(f"editor:clipboard:{name}") or {}
        if result.get("cut"):
            # Ctrl+X 后源节点已经不在草稿里；先把带参数的快照留在 Python 侧，
            # 粘贴时按 copy_of 恢复参数，而不是让画布传参数。
            clipboard = {
                str(node.get("id")): copy.deepcopy(node)
                for node in draft["workflows"][workflow]["nodes"]
            }
            st.session_state[f"editor:clipboard:{name}"] = clipboard
        changed = spec_edit.absorb_canvas(
            name, workflow, draft, result, clipboard=clipboard
        )
        if changed:
            _remember(name, before)
            # 结构变了，之前那次校验的结论就过期了。
            st.session_state["editor-errors"] = []
        st.session_state["editor-selected"] = result.get("selected")
        saved_selection = result.get("selection")
        if isinstance(saved_selection, list):
            st.session_state[selection_key] = [str(item) for item in saved_selection]
        elif result.get("selected"):
            st.session_state[selection_key] = [str(result.get("selected"))]
        else:
            st.session_state[selection_key] = []
        st.rerun()

    header = st.columns([2.2, 1], vertical_alignment="center")
    header[0].caption(
        "拖节点移动 · Shift/Alt+点或拖空白多选 · Ctrl+C/X/V 复制剪切粘贴 · "
        "Ctrl+Z/Y 撤销重做 · Delete 删除 · 滚轮缩放 / 空白拖动平移"
    )
    if header[1].button("重新自动排版", key=f"{prefix}-canvas-relayout"):
        spec_edit.clear_layout(name, workflow)
        _bump_generation()
        st.rerun()


def _render_selected_node(
    name: str,
    draft: dict,
    workflow: str,
    prefix: str,
    tools: list[str],
    empty_hint: str,
) -> None:
    """右侧检查器：选中节点的身份 + 参数，不再跳到画布下方。"""
    nodes = draft["workflows"][workflow]["nodes"] if workflow else []
    selected = st.session_state.get("editor-selected")
    node = next((item for item in nodes if str(item.get("id")) == selected), None)
    if node is None:
        st.caption(empty_hint)
        return

    if st.session_state.pop("editor-param-changed", False):
        _push_undo(name, draft)

    fn = str(node.get("fn"))
    options = registered_nodes()
    st.caption(f"`{fn}` · {block_desc(fn) or '该块没有说明。'}")

    new_id = st.text_input(
        "节点 id", value=str(node.get("id")), key=f"{prefix}-sel-id"
    ).strip()
    new_fn = st.selectbox(
        "块",
        options,
        index=options.index(fn) if fn in options else 0,
        format_func=lambda option: f"{block_label(option)}（{option}）",
        key=f"{prefix}-sel-fn",
        help=block_desc(fn),
    )

    if new_fn != fn:
        _remember(name, draft)
        node["fn"] = new_fn
        node["args"] = spec_edit.block_defaults(new_fn)
        _bump_generation()
        st.rerun()
    if new_id and new_id != node.get("id"):
        before = copy.deepcopy(draft)
        try:
            spec_edit.rename_node(draft, workflow, str(node.get("id")), new_id)
        except SpecError as exc:
            st.error("；".join(exc.errors))
        else:
            _push_undo(name, before)
            st.session_state["editor-selected"] = new_id
            _bump_generation()
            st.rerun()

    if st.button("删除节点", key=f"{prefix}-sel-del", use_container_width=True):
        _remember(name, draft)
        index = next(
            (position for position, item in enumerate(nodes) if str(item.get("id")) == selected),
            None,
        )
        if index is not None:
            spec_edit.remove_node(draft, workflow, index)
        st.session_state["editor-selected"] = None
        _bump_generation()
        st.rerun()

    old_args = dict(node.get("args") or {})
    node["args"] = _render_params(
        str(node.get("fn")), old_args, f"{prefix}-sel-{node.get('id')}", tools
    )


def _render_nodes(name: str, draft: dict, workflow: str, prefix: str, tools: list[str]) -> None:
    if st.session_state.pop("editor-param-changed", False):
        _push_undo(name, draft)
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
                _remember(name, draft)
                node["id"] = new_id
            options = registered_nodes()
            current_fn = str(node.get("fn") or options[0])
            new_fn = col_fn.selectbox(
                "块",
                options,
                index=options.index(current_fn) if current_fn in options else 0,
                format_func=lambda option: f"{block_label(option)}（{option}）",
                key=f"{prefix}-n{index}-fn",
                help=block_desc(current_fn),
            )
            if new_fn != current_fn:
                _remember(name, draft)
                node["fn"] = new_fn
                node["args"] = spec_edit.block_defaults(new_fn)
                _bump_generation()
                st.rerun()
            if col_del.button("删除", key=f"{prefix}-n{index}-del"):
                _remember(name, draft)
                spec_edit.remove_node(draft, workflow, index)
                _bump_generation()
                st.rerun()
            st.caption(block_desc(fn) or "该块没有说明。")
            node["args"] = _render_params(
                str(node.get("fn") or fn),
                dict(node.get("args") or {}),
                f"{prefix}-n{index}-{fn}",
                tools,
            )

    add_col1, add_col2 = st.columns([1.6, 1])
    block_options = registered_nodes()
    chosen = add_col1.selectbox(
        "新增节点使用的块",
        block_options,
        format_func=lambda option: f"{block_label(option)}（{option}）",
        key=f"{prefix}-add-block",
    )
    if add_col2.button("加一个节点", key=f"{prefix}-add-node"):
        _remember(name, draft)
        spec_edit.add_node(draft, workflow, chosen)
        _bump_generation()
        st.rerun()


def _render_edges(name: str, draft: dict, workflow: str, prefix: str) -> None:
    workflow_draft = draft["workflows"][workflow]
    node_ids = [str(node.get("id")) for node in workflow_draft["nodes"]]
    options = ["__start__", *node_ids, "__end__"]
    rows = []
    for edge in workflow_draft["edges"]:
        source, target, when = split_edge(edge)
        rows.append({"从": source, "到": target, "条件": when or ""})
    if not rows:
        st.caption("还没有边；加一条 START 到第一个节点的边，流程才能开始。")
        if st.button("加第一条边", key=f"{prefix}-edge-first"):
            _remember(name, draft)
            spec_edit.set_edge(draft, workflow, "__start__", node_ids[0] if node_ids else "__end__")
            _bump_generation()
            st.rerun()
        return
    st.caption("条件列填 branch 的 route 值（cases 里写的 route 或 default；旧版是 hit / miss）；留空表示无条件边。也可以在画布上点一条边，在弹层里设置条件。同一个节点要么全有条件，要么全无条件。")
    before = copy.deepcopy(draft)
    edited = st.data_editor(
        rows,
        num_rows="dynamic",
        use_container_width=True,
        key=f"{prefix}-edges",
        column_config={
            "从": st.column_config.SelectboxColumn("从", options=options, required=True),
            "到": st.column_config.SelectboxColumn("到", options=options, required=True),
            "条件": st.column_config.TextColumn(
                "条件",
                help="branch 写入 scratch.route 的值，例如 robot / clothing / other；旧版为 hit / miss",
                width="small",
            ),
        },
    )
    pairs: list[list[str]] = []
    for row in _rows_of(edited):
        source, target = str(row.get("从") or ""), str(row.get("到") or "")
        when = str(row.get("条件") or "").strip()
        if source and target:
            pairs.append([source, target] if not when else [source, target, when])
    old_pairs = []
    for edge in before["workflows"][workflow]["edges"]:
        source, target, when = split_edge(edge)
        old_pairs.append([source, target] if not when else [source, target, when])
    if pairs != old_pairs:
        _push_undo(name, before)
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


def _render_block_library(name: str, draft: dict, workflow: str, prefix: str) -> None:
    st.markdown("**块库**")
    query = st.text_input(
        "搜索块",
        key=f"{prefix}-block-search",
        placeholder="名称 / 说明",
        label_visibility="collapsed",
    ).strip().lower()
    if not workflow:
        st.caption("先选一个工作流。")
        return
    composite = {"react_loop", "fan_out"}
    with st.container(height=300):
        for is_composite, title in ((True, "复合块"), (False, "基础块")):
            matches = [
                fn for fn in registered_nodes()
                if (fn in composite) == is_composite
                and (
                    not query
                    or query in block_label(fn).lower()
                    or query in fn.lower()
                    or query in block_desc(fn).lower()
                )
            ]
            if not matches:
                continue
            st.caption(title)
            for fn in matches:
                if st.button(
                    f"+ {block_label(fn)}",
                    key=f"{prefix}-add-{fn}",
                    help=block_desc(fn),
                    use_container_width=True,
                ):
                    _remember(name, draft)
                    node_id = spec_edit.add_node(draft, workflow, fn)
                    st.session_state["editor-selected"] = node_id
                    _bump_generation()
                    st.rerun()


def _render_error_list(draft: dict, workflow: str, prefix: str) -> None:
    errors = st.session_state.get("editor-errors") or []
    if not errors:
        st.caption("校验通过。")
        return
    nodes = draft["workflows"][workflow]["nodes"] if workflow else []
    st.markdown(f"**{len(errors)} 个问题**")
    for index, error in enumerate(errors[:8]):
        bad = spec_edit.bad_node_ids([error], nodes)
        if bad:
            if st.button(
                f"定位 {bad[0]}",
                key=f"{prefix}-err-loc-{index}",
                use_container_width=True,
            ):
                st.session_state["editor-selected"] = bad[0]
                st.rerun()
        st.caption(error)


def _save_draft(name: str, draft: dict) -> None:
    try:
        path = spec_edit.save_draft(draft)
    except SpecError as exc:
        st.session_state["editor-errors"] = exc.errors
    else:
        _bases()[name] = copy.deepcopy(draft)
        _clear_runtime_draft(name)
        st.session_state["editor-errors"] = []
        st.session_state["editor-notice"] = f"已保存：{path}（新版本已设为 active）"
        _reset_agent_caches()
        _bump_generation()
    st.rerun()


def _render_status(name: str, draft: dict, prefix: str, tools: list[str]) -> None:
    errors = st.session_state.get("editor-errors") or []
    versions = spec_edit.versions(name)
    active = next((row["版本"] for row in versions if row["当前"]), "—")
    undo = _undo_stacks().get(name) or []
    redo = _redo_stacks().get(name) or []
    with st.container(border=True):
        cols = st.columns(
            [1.2, 1.2, 0.95, 0.7, 0.7, 1.25, 1.35, 0.95],
            vertical_alignment="center",
            gap="small",
        )
        cols[0].caption("● 未保存" if _is_dirty(name, draft) else "已保存")
        cols[1].caption(f"{len(errors)} errors" if errors else "校验通过")
        cols[2].caption(f"版本 {active}")
        if cols[3].button("撤销", key=f"{prefix}-undo", disabled=not undo):
            if _undo(name):
                _bump_generation()
                st.rerun()
        if cols[4].button("重做", key=f"{prefix}-redo", disabled=not redo):
            if _redo(name):
                _bump_generation()
                st.rerun()
        if cols[5].button("只校验，不保存", key=f"{prefix}-check"):
            st.session_state["editor-errors"] = spec_edit.draft_errors(draft, set(tools))
            st.rerun()
        if cols[6].button("保存为新版本", type="primary", key=f"{prefix}-save"):
            _save_draft(name, draft)
        wide = bool(st.session_state.get("editor-wide"))
        if cols[7].button(
            "还原宽度" if wide else "宽屏",
            key=f"{prefix}-wide",
            help="把整个构建页放宽到接近视口宽度；画布右下角还可以拖拽调高。",
        ):
            st.session_state["editor-wide"] = not wide
            st.rerun()



def _render_versions(name: str, draft: dict, prefix: str) -> None:
    version_rows = spec_edit.versions(name)
    if version_rows:
        compact_table(version_rows, height=150, key=f"{prefix}-versions")
        options = [row["文件"] for row in version_rows]
        picked = st.selectbox("载入哪个版本到编辑器", options, key=f"{prefix}-version-pick")
        if st.button("载入这个版本", key=f"{prefix}-version-load"):
            _drafts()[name] = spec_edit.load_version(name, picked)
            st.session_state["editor-errors"] = []
            _bump_generation()
            st.rerun()
    st.caption(f"spec 目录：`{SPEC_ROOT / name}`")
    st.download_button(
        "下载当前草稿 JSON",
        data=json.dumps(draft, ensure_ascii=False, indent=2),
        file_name=f"{name}.json",
        mime="application/json",
        key=f"{prefix}-download",
    )


def _render_eject(name: str, prefix: str) -> None:
    has_code = (CODE_ROOT / name).is_dir()
    with st.expander("转为代码（eject）", expanded=False):
        st.caption(
            "单向门：spec 失效、构建改用代码、这里变只读。"
            + ("原本就有代码目录。" if has_code else
               "这个场景还没有代码目录，eject 后需要自己写 `core/scenarios/"
               f"{name}/scenario.py`，否则它会从场景列表里消失。")
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
            eject(name, reason=reason.strip())
            _reset_agent_caches()
            st.session_state["editor-notice"] = f"{name} 已转为 code-owned"
            _bump_generation()
            st.rerun()


def _render_workbench(name: str, draft: dict, prefix: str, tools: list[str]) -> None:
    """三栏工作台：左块库 / 中画布 / 右检查器；状态栏在下方。"""
    workflow_names = list((draft.get("workflows") or {}).keys())
    left, center, right = st.columns([1.35, 4.25, 1.8], gap="small")
    with left:
        workflow = st.selectbox(
            "工作流", workflow_names, key=f"{prefix}-workflow"
        ) if workflow_names else ""
        if st.session_state.get("editor-workflow-current") != workflow:
            st.session_state["editor-workflow-current"] = workflow
            st.session_state["editor-selected"] = None
        with st.expander("新建工作流", expanded=False):
            with st.form(f"{prefix}-workflow-new", clear_on_submit=True):
                workflow_name = st.text_input("新增工作流名", placeholder="report")
                if st.form_submit_button("新增"):
                    _remember(name, draft)
                    try:
                        spec_edit.add_workflow(draft, workflow_name)
                    except SpecError as exc:
                        st.error("；".join(exc.errors))
                    else:
                        _bump_generation()
                        st.rerun()
        mode = st.radio(
            "编辑方式",
            [MODE_CANVAS, MODE_FORM],
            horizontal=True,
            key=f"{prefix}-mode",
            help="画布：拖节点 / 连线 / 缩放；表单：逐节点展开，适合同屏改多个参数。",
        )
        _render_block_library(name, draft, workflow, prefix)
        if workflow and len(workflow_names) > 1:
            if st.button(
                "删除当前工作流",
                key=f"{prefix}-workflow-del",
                help=f"删除 {workflow} 及其边；不会自动重连",
            ):
                _remember(name, draft)
                try:
                    spec_edit.remove_workflow(draft, workflow)
                except SpecError as exc:
                    st.error("；".join(exc.errors))
                else:
                    _bump_generation()
                    st.rerun()

    with center:
        if not workflow:
            empty_state("还没有工作流；先在左侧新建一个。")
        elif mode == MODE_CANVAS:
            _render_canvas_editor(name, draft, workflow, prefix, tools)
        else:
            _render_nodes(name, draft, workflow, prefix, tools)
            st.markdown("**边**（从 → 到；`__start__` / `__end__` 是入口与出口）")
            _render_edges(name, draft, workflow, prefix)

    with right:
        st.markdown("**检查器**")
        if workflow:
            _render_selected_node(
                name,
                draft,
                workflow,
                prefix,
                tools,
                "点画布上的节点，或从左侧块库添加一个。",
            )
            st.divider()
            _render_error_list(draft, workflow, prefix)
        else:
            st.caption("先选工作流。")


def render_editor(current: str | None = None, *, embedded: bool = False) -> None:
    """``embedded=True``：场景由路由固定，只渲染这个场景的结构编辑（构建页用）。

    旧控制台是"场景选择器 + 编辑页"两层都在这一页里；现在场景由路由携带，
    嵌进场景详情后就不该再出现第二个选择器——那正是之前换场景清一堆状态的来源。
    """
    if not embedded:
        page_header(
            "场景编辑",
            "受约束的低代码：节点只能引用已注册的块，参数按块契约校验，保存即新版本 spec。",
            meta="保存前会编译；校验不过不写盘。",
        )

    rows = _status_rows()
    if embedded:
        choice = current or ""
        if not choice or not (SPEC_ROOT / choice).is_dir():
            empty_state("这个场景还没有 spec 目录。")
            return
    else:
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
        # 默认落在"场景库当前选中的场景"上：场景库选中谁，这里就编辑谁。
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

    notice = st.session_state.pop("editor-notice", None)
    if notice:
        st.success(notice)

    from core.scenarios import pools

    tools = pools.tool_names(choice)
    if st.session_state.setdefault("editor-wide", False):
        st.markdown(
            "<style>.block-container{max-width:calc(100vw - 2rem) !important;"
            "padding-left:1rem !important;padding-right:1rem !important;}</style>",
            unsafe_allow_html=True,
        )
    structure_tab, basics_tab, advanced_tab = st.tabs(["画布", "配置", "策略与版本"])
    with structure_tab:
        _render_workbench(choice, draft, prefix, tools)
    with basics_tab:
        section("基本信息", "这一层直接决定 Agent 的行为边界。")
        _render_basics(choice, draft, prefix, tools)
    with advanced_tab:
        with st.expander("高级：策略覆盖（中间件）", expanded=False):
            _render_policies(draft, prefix)
        with st.expander("版本与导出", expanded=True):
            _render_versions(choice, draft, prefix)
        _render_eject(choice, prefix)
        errors = st.session_state.get("editor-errors") or []
        _render_preview(draft, errors)

    _render_status(choice, draft, prefix, tools)
    _autosave(choice, draft)
