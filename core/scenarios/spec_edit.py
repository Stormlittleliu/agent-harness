# -*- coding: utf-8 -*-
"""场景编辑器背后的纯逻辑：草稿（dict）↔ ``ScenarioSpec``。

Streamlit 只负责摆控件；所有会改结构、会写盘的判断都在这里，所以可以直接
单测：加节点、改块、换参数、校验、存新版本，都不需要跑界面。

草稿就是 ``spec_to_dict`` 的形状（JSON 可序列化），这样"载入已有 spec"和
"界面新建 spec"共用一套代码，不用担心两套模型对不上。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langgraph.graph import END, START

from core.scenarios.spec import (
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
from core.scenarios.spec_nodes import NODE_REGISTRY, block_params

DEFAULT_WORKFLOW = "qa"


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
