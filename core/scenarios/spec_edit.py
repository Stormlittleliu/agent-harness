# -*- coding: utf-8 -*-
"""场景编辑器背后的纯逻辑：草稿（dict）↔ ``ScenarioSpec``。

Streamlit 只负责摆控件；所有会改结构、会写盘的判断都在这里，所以可以直接
单测：加节点、改块、换参数、校验、存新版本，都不需要跑界面。

草稿就是 ``spec_to_dict`` 的形状（JSON 可序列化），这样"载入已有 spec"和
"界面新建 spec"共用一套代码，不用担心两套模型对不上。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from langgraph.graph import END, START

from core.scenarios.spec import (
    split_edge,
    SPEC_ROOT,
    ScenarioSpec,
    SpecError,
    load_active_spec,
    load_spec,
    save_spec,
    spec_from_dict,
    spec_to_dict,
    validate_spec,
)
from core.scenarios.spec_nodes import NODE_REGISTRY, block_params, block_label

DEFAULT_WORKFLOW = "qa"
LAYOUT_ROOT = Path("data/runtime/spec_layout")
NODE_W = 156
NODE_H = 58
COL_GAP = 210
ROW_GAP = 96
# 第一个节点往右挪一点，给 START 留出位置（否则 START 会被画到画布外面）。
ORIGIN = (216, 40)


def new_draft(
    name: str,
    tools: list[str] | None = None,
    description: str = "",
) -> dict[str, Any]:
    """新场景模板：检索 → 生成回答 → 引用校验。

    模板只是"能编译通过的最小结构"，不预设业务；用户按需要加/删节点。
    """
    tools = list(tools or [])
    return {
        "schema_version": 1,
        "name": name,
        "description": description or "在控制台里搭出来的场景",
        "tools": tools,
        "system_prompt": "你是严谨的助手。回答必须用 [来源id] 标注引用；资料不足就明确说无法确定。",
        "harness": {
            "enable_todo": False,
            "enable_summarization": True,
            "tool_call_limit": 8,
            "token_budget": 20000,
        },
        "policies": None,
        "workflows": {DEFAULT_WORKFLOW: template_workflow(tools)},
    }


def template_workflow(tools: list[str] | None = None) -> dict[str, Any]:
    """默认三节点流程；有工具就把它填进检索节点。"""
    tools = list(tools or [])
    retrieve_args: dict[str, Any] = {"limit": 5}
    if tools:
        retrieve_args["tool"] = tools[0]
    return {
        "nodes": [
            {"id": "search", "fn": "retrieve", "args": retrieve_args},
            {"id": "answer", "fn": "llm_answer", "args": {}},
            {"id": "verify", "fn": "require_citation", "args": {}},
        ],
        "edges": [
            [START, "search"],
            ["search", "answer"],
            ["answer", "verify"],
            ["verify", END],
        ],
    }


def draft_from_spec(spec: ScenarioSpec) -> dict[str, Any]:
    """把已保存的 spec 转成草稿（深拷贝语义，不改调用方对象）。"""
    return spec_to_dict(spec)


def spec_from_draft(draft: dict[str, Any]) -> ScenarioSpec:
    """草稿 -> ``ScenarioSpec``；结构错误统一抛 ``SpecError``。"""
    try:
        return spec_from_dict(dict(draft))
    except SpecError:
        raise
    except Exception as exc:  # noqa: BLE001 - pydantic 的报错不适合直接上屏
        raise SpecError([f"{type(exc).__name__}: {exc}"]) from exc


def load_draft(
    name: str,
    root: str | None = None,
    tools: list[str] | None = None,
) -> dict[str, Any]:
    """读该场景的 active spec；没有就返回模板草稿。"""
    spec = load_active_spec(name) if root is None else load_active_spec(name, root)
    if spec is None:
        return new_draft(name, tools)
    return draft_from_spec(spec)


def block_defaults(fn: str) -> dict[str, Any]:
    """按块的参数契约生成默认参数；必填项留空，由用户填。"""
    args: dict[str, Any] = {}
    for param in block_params(fn):
        if param.required:
            continue
        if param.default is not None:
            args[param.name] = param.default
    return args


def normalize_args(fn: str, args: dict[str, Any]) -> dict[str, Any]:
    """去掉空值，避免 spec 里出现一堆 ``""`` 和 ``null``。"""
    allowed = {param.name for param in block_params(fn)}
    cleaned: dict[str, Any] = {}
    for key, value in (args or {}).items():
        if allowed and key not in allowed:
            continue
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, tuple)) and not value:
            continue
        cleaned[key] = value
    return cleaned


def next_node_id(nodes: list[dict[str, Any]], base: str = "step") -> str:
    """生成不与现有节点冲突的 id。"""
    existing = {str(node.get("id")) for node in nodes}
    index = 1
    while f"{base}{index}" in existing:
        index += 1
    return f"{base}{index}"


def add_node(
    draft: dict[str, Any],
    workflow: str,
    fn: str = "llm_answer",
    node_id: str | None = None,
) -> str:
    """往工作流里加一个节点，返回节点 id。参数按块契约填默认值。"""
    if fn not in NODE_REGISTRY:
        raise SpecError([f"未注册的块：{fn}"])
    nodes = draft["workflows"][workflow]["nodes"]
    node_id = node_id or next_node_id(nodes, fn.split("_")[0])
    nodes.append({"id": node_id, "fn": fn, "args": block_defaults(fn)})
    return node_id


def remove_node(draft: dict[str, Any], workflow: str, index: int) -> None:
    """删节点并顺手删掉挂在它身上的边（不做自动重连）。"""
    nodes = draft["workflows"][workflow]["nodes"]
    if not 0 <= index < len(nodes):
        return
    removed = str(nodes[index].get("id"))
    nodes.pop(index)
    edges = draft["workflows"][workflow]["edges"]
    draft["workflows"][workflow]["edges"] = [
        edge for edge in edges if removed not in (str(edge[0]), str(edge[1]))
    ]


def rename_node(draft: dict[str, Any], workflow: str, old: str, new: str) -> str:
    """改节点 id，并把引用它的边一起改；返回最终 id。"""
    new = (new or "").strip()
    workflow_draft = draft["workflows"][workflow]
    nodes = workflow_draft["nodes"]
    existing = {str(node.get("id")) for node in nodes}
    if not new or new in {START, END}:
        raise SpecError([f"节点 id 不合法：{new!r}"])
    if new != old and new in existing:
        raise SpecError([f"节点 id 已存在：{new}"])
    for node in nodes:
        if str(node.get("id")) == old:
            node["id"] = new
            break
    workflow_draft["edges"] = [
        [new if str(edge[0]) == old else str(edge[0]), new if str(edge[1]) == old else str(edge[1])]
        for edge in workflow_draft["edges"]
    ]
    return new


def set_edge(draft: dict[str, Any], workflow: str, source: str, target: str) -> None:
    """加一条边；重复的边不重复加。"""
    edges = draft["workflows"][workflow]["edges"]
    pair = [str(source), str(target)]
    if pair not in edges:
        edges.append(pair)


def add_workflow(draft: dict[str, Any], name: str) -> str:
    """新建一个空工作流（带一个 START 边都没有的节点列表，交给用户连）。"""
    name = (name or "").strip()
    if not name:
        raise SpecError(["工作流名不能为空"])
    if name in draft["workflows"]:
        raise SpecError([f"工作流已存在：{name}"])
    draft["workflows"][name] = template_workflow(draft.get("tools") or [])
    return name


def remove_workflow(draft: dict[str, Any], name: str) -> None:
    if len(draft.get("workflows") or {}) <= 1:
        raise SpecError(["至少保留一个工作流"])
    draft["workflows"].pop(name, None)


def draft_errors(draft: dict[str, Any], tool_names: set[str] | None = None) -> list[str]:
    """草稿的全部问题：结构 + 编辑器自己的必填检查。"""
    try:
        spec = spec_from_draft(draft)
    except SpecError as exc:
        return exc.errors
    errors = validate_spec(spec, tool_names=tool_names)
    for workflow_name, workflow in spec.workflows.items():
        for node in workflow.nodes:
            for param in block_params(node.fn):
                if not param.required:
                    continue
                value = node.args.get(param.name)
                if value in (None, "", []):
                    errors.append(
                        f"workflow[{workflow_name}].{node.id}：{node.fn}.{param.name} 是必填参数"
                    )
    return errors


def save_draft(
    draft: dict[str, Any],
    root: str | None = None,
    tool_names: set[str] | None = None,
) -> str:
    """校验并写新版本；校验不过直接抛 ``SpecError``，不落盘。"""
    spec = spec_from_draft(draft)
    errors = draft_errors(draft, tool_names)
    if errors:
        raise SpecError(errors)
    return str(save_spec(spec) if root is None else save_spec(spec, root))


def versions(name: str, root: str | None = None) -> list[dict[str, Any]]:
    """列出该场景的版本文件，标出哪个是 active。"""
    directory = (SPEC_ROOT if root is None else Path(root)) / name
    if not directory.is_dir():
        return []
    active = None
    pointer = directory / "active.json"
    if pointer.is_file():
        try:
            active = json.loads(pointer.read_text(encoding="utf-8")).get("file")
        except (OSError, ValueError):
            active = None
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("v*.json")):
        rows.append({
            "版本": path.stem,
            "当前": path.name == active,
            "文件": path.name,
        })
    return rows


def load_version(name: str, filename: str, root: str | None = None) -> dict[str, Any]:
    """读某个历史版本成草稿，用于"载入旧版本"。"""
    directory = (SPEC_ROOT if root is None else Path(root)) / name
    spec = load_spec(directory / filename)
    return draft_from_spec(spec)


# ---------------------------------------------------------------- 画布：布局与合并
#
# 画布只负责"拓扑 + 位置"，节点身份与参数仍在草稿里：
# - 位置不进 spec（会被 schema 拒绝），放 data/runtime/spec_layout/<name>.json；
# - 画布回传的状态先过 merge_canvas 才落进草稿，非法节点 / 悬空边直接丢掉。


def _levels(nodes: list[dict], edges: list[list[str]]) -> dict[str, int]:
    """按"从 START 出发的最长路径"给节点分层；有环也能收敛（重复访问返回 0）。"""
    ids = [str(node.get("id")) for node in nodes]
    parents: dict[str, list[str]] = {node_id: [] for node_id in ids}
    for edge in edges:
        if len(edge) != 2:
            continue
        source, target = str(edge[0]), str(edge[1])
        if source in parents and target in parents:
            parents[target].append(source)
    levels: dict[str, int] = {}

    def depth(node: str, seen: set[str]) -> int:
        if node in levels:
            return levels[node]
        if node in seen:
            return 0
        seen.add(node)
        found = [depth(parent, seen) + 1 for parent in parents.get(node, [])]
        levels[node] = max(found) if found else 0
        return levels[node]

    for node_id in ids:
        depth(node_id, set())
    return levels


def auto_layout(nodes: list[dict], edges: list[list[str]]) -> dict[str, list[int]]:
    """没有历史位置时用的自动布局：按层从左到右，同层从上到下。"""
    levels = _levels(nodes, edges)
    rows: dict[int, int] = {}
    positions: dict[str, list[int]] = {}
    for node in nodes:
        node_id = str(node.get("id"))
        level = levels.get(node_id, 0)
        row = rows.get(level, 0)
        rows[level] = row + 1
        positions[node_id] = [
            ORIGIN[0] + level * COL_GAP,
            ORIGIN[1] + row * ROW_GAP,
        ]
    return positions


def layout_path(name: str, root: str | Path | None = None) -> Path:
    base = LAYOUT_ROOT if root is None else Path(root)
    return base / f"{name}.json"


def load_layout(name: str, root: str | Path | None = None) -> dict[str, dict[str, list[int]]]:
    """读回上次拖动的位置；文件缺失或坏了都返回空。"""
    path = layout_path(name, root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    cleaned: dict[str, dict[str, list[int]]] = {}
    for workflow, positions in data.items():
        if not isinstance(positions, dict):
            continue
        cleaned[str(workflow)] = {
            str(node_id): [int(value[0]), int(value[1])]
            for node_id, value in positions.items()
            if isinstance(value, (list, tuple)) and len(value) == 2
        }
    return cleaned


def save_layout(
    name: str,
    workflow: str,
    positions: dict[str, list[int]],
    root: str | Path | None = None,
) -> Path:
    """把某个工作流的节点位置写盘（其余工作流保留）。"""
    path = layout_path(name, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_layout(name, root)
    data[workflow] = {
        str(node_id): [int(value[0]), int(value[1])]
        for node_id, value in positions.items()
    }
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    return path


def node_positions(
    name: str,
    workflow: str,
    nodes: list[dict],
    edges: list[list[str]],
    root: str | Path | None = None,
) -> dict[str, list[int]]:
    """历史位置优先，缺的节点用自动布局补。"""
    saved = load_layout(name, root).get(workflow, {})
    auto = auto_layout(nodes, edges)
    return {
        str(node.get("id")): list(saved.get(str(node.get("id"))) or auto.get(str(node.get("id")), list(ORIGIN)))
        for node in nodes
    }


def merge_canvas(draft: dict[str, Any], workflow: str, payload: Any) -> bool:
    """把画布回传的状态并进草稿；返回是否真的改了结构。

    画布是"不可信输入"：未知块、重复 id、悬空边、空节点列表全部丢掉，
    只接受 ``{nodes: [{id, fn, x, y}], edges: [[from, to]]}``。
    """
    if not isinstance(payload, dict):
        return False
    raw_nodes = payload.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        return False
    current = {
        str(node.get("id")): node
        for node in draft["workflows"][workflow]["nodes"]
    }
    merged: list[dict[str, Any]] = []
    used: set[str] = set()
    for item in raw_nodes:
        if not isinstance(item, dict):
            continue
        node_id = str(item.get("id") or "").strip()
        fn = str(item.get("fn") or "")
        if not node_id or node_id in used or fn not in NODE_REGISTRY:
            continue
        previous = current.get(node_id)
        if previous is not None and str(previous.get("fn")) == fn:
            args = dict(previous.get("args") or {})
        else:
            args = block_defaults(fn)
        merged.append({"id": node_id, "fn": fn, "args": args})
        used.add(node_id)
    if not merged:
        return False

    known = used | {START, END}
    # 画布只画 from→to，不表达条件；条件边原样保留（按 from/to 配对找回 when）。
    conditions: dict[tuple[str, str], str | None] = {}
    for edge in draft["workflows"][workflow]["edges"]:
        source, target, when = split_edge(edge)
        conditions[(source, target)] = when
    raw_edges = payload.get("edges")
    edges: list[list[str]] = []
    for edge in raw_edges if isinstance(raw_edges, list) else []:
        if not isinstance(edge, (list, tuple)) or len(edge) < 2:
            continue
        source, target = str(edge[0]), str(edge[1])
        if source not in known or target not in known:
            continue
        when = edge[2] if len(edge) >= 3 else conditions.get((source, target))
        item = [source, target] if when in (None, "") else [source, target, str(when)]
        if item not in edges:
            edges.append(item)

    changed = (
        merged != draft["workflows"][workflow]["nodes"]
        or edges != draft["workflows"][workflow]["edges"]
    )
    if changed:
        draft["workflows"][workflow]["nodes"] = merged
        draft["workflows"][workflow]["edges"] = edges
    return changed


def bad_node_ids(errors: list[str], nodes: list[dict]) -> list[str]:
    """从校验错误里挑出"这条错属于哪个节点"，给画布标红用。"""
    ids = [str(node.get("id")) for node in nodes if str(node.get("id") or "").strip()]
    bad: list[str] = []
    for error in errors or ():
        text = str(error)
        for node_id in ids:
            if node_id in bad:
                continue
            pattern = rf"(?:\.|：){re.escape(node_id)}(?![0-9A-Za-z_])"
            if re.search(pattern, text):
                bad.append(node_id)
    return bad


def canvas_payload(
    name: str,
    workflow: str,
    draft: dict[str, Any],
    errors: list[str] | None = None,
    root: str | Path | None = None,
    selected: str | None = None,
) -> dict[str, Any]:
    """给前端画布的完整输入：节点（含中文名与坐标）、边、块库、标红节点。"""
    workflow_draft = draft["workflows"][workflow]
    nodes = list(workflow_draft["nodes"])
    edges = [list(edge) for edge in workflow_draft["edges"]]
    positions = node_positions(name, workflow, nodes, edges, root)

    canvas_nodes = [
        {
            "id": str(node.get("id")),
            "fn": str(node.get("fn")),
            "label": block_label(str(node.get("fn"))),
            "x": positions[str(node.get("id"))][0],
            "y": positions[str(node.get("id"))][1],
        }
        for node in nodes
    ]
    xs = [item["x"] for item in canvas_nodes] or [0]
    ys = [item["y"] for item in canvas_nodes] or [0]
    saved = load_layout(name, root).get(workflow, {})
    start_pos = saved.get(START) or [min(xs) - NODE_W - 40, int(sum(ys) / len(ys))]
    end_pos = saved.get(END) or [max(xs) + NODE_W + 40, int(sum(ys) / len(ys))]
    canvas_nodes.insert(0, {
        "id": START, "fn": "", "label": "START",
        "x": max(4, int(start_pos[0])), "y": max(4, int(start_pos[1])), "kind": "start",
    })
    canvas_nodes.append({
        "id": END, "fn": "", "label": "END",
        "x": min(1000, max(4, int(end_pos[0]))), "y": max(4, int(end_pos[1])), "kind": "end",
    })

    return {
        "nodes": canvas_nodes,
        "edges": edges,
        "blocks": [
            {"fn": fn, "label": block_label(fn)}
            for fn in NODE_REGISTRY
        ],
        "errors": bad_node_ids(list(errors or []), nodes),
        "selected": selected if selected and selected not in {START, END} else None,
        "workflow": workflow,
    }


def absorb_canvas(
    name: str,
    workflow: str,
    draft: dict[str, Any],
    payload: Any,
    root: str | Path | None = None,
) -> bool:
    """吸收一次画布回传：合并结构 + 记住位置；返回结构是否变化。"""
    changed = merge_canvas(draft, workflow, payload)
    if not isinstance(payload, dict):
        return changed
    positions: dict[str, list[int]] = {}
    for item in payload.get("nodes") or []:
        if not isinstance(item, dict):
            continue
        node_id = str(item.get("id") or "")
        if not node_id:
            continue
        try:
            positions[node_id] = [int(item.get("x")), int(item.get("y"))]
        except (TypeError, ValueError):
            continue
    anchors = payload.get("anchors")
    if isinstance(anchors, dict):
        for node_id, value in anchors.items():
            if isinstance(value, (list, tuple)) and len(value) == 2:
                positions[str(node_id)] = [int(value[0]), int(value[1])]
    if positions:
        save_layout(name, workflow, positions, root)
    return changed


def clear_layout(name: str, workflow: str, root: str | Path | None = None) -> None:
    """清掉某工作流的位置缓存，下次渲染回到自动布局。"""
    data = load_layout(name, root)
    if workflow in data:
        data.pop(workflow, None)
        path = layout_path(name, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
        )

