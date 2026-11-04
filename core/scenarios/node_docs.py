# -*- coding: utf-8 -*-
"""节点说明：让调用链说清"这一步是哪个节点、为什么存在"。

两个来源：

- **代码场景**：各场景在 ``graph.py`` 里声明 ``NODE_DOCS``，import 时注册进来；
- **spec 场景**：从 active spec 的节点 + 块文档现场推导，所以界面上新建的场景
  也有中文说明，不需要额外写代码。

找不到时返回 ``None``，调用方显示原始节点名。宁可少解释，也不要编。
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Iterable

# 场景名 -> 声明 NODE_DOCS 的模块；只在第一次问到时 import，避免拖慢启动。
# spec 场景（flow_demo 及界面新建的）不在这里：它们的说明由 active spec 现场推导。
_BUILTIN_MODULES: dict[str, str] = {
    "research_assistant": "core.scenarios.research_assistant.graph",
    "robot_vacuum": "core.scenarios.robot_vacuum.graph",
    "workspace_assistant": "core.scenarios.workspace_assistant.graph",
}

REGISTRY: dict[str, dict[str, "NodeDoc"]] = {}
_LOADED: set[str] = set()
_SPEC_CACHE: dict[str, tuple[float | None, dict[str, "NodeDoc"]]] = {}


@dataclass(frozen=True)
class NodeDoc:
    """一个工作流节点的中文说明。"""

    node: str
    label: str
    desc: str
    workflow: str = ""

    @property
    def title(self) -> str:
        """``复核 · verify`` 这种"中文名 + 节点 id"的展示名。"""
        return f"{self.label} · {self.node}" if self.label and self.label != self.node else self.node


def register_node_docs(
    scenario: str,
    docs: Iterable[NodeDoc] | dict[str, "NodeDoc | tuple[str, str]"],
) -> None:
    """登记一个场景的节点说明；``workflow:node`` 优先，裸 node 兜底。"""
    table = REGISTRY.setdefault(scenario, {})
    items: list[NodeDoc] = []
    if isinstance(docs, dict):
        for node, value in docs.items():
            if isinstance(value, NodeDoc):
                items.append(value)
            else:
                label, desc = value
                items.append(NodeDoc(str(node), str(label), str(desc)))
    else:
        items.extend(docs)
    for doc in items:
        table[doc.node] = doc
        if doc.workflow:
            table[f"{doc.workflow}:{doc.node}"] = doc
    _LOADED.add(scenario)


def _load(scenario: str) -> None:
    if scenario in _LOADED:
        return
    _LOADED.add(scenario)  # 先标记，避免 import 失败时反复重试/递归
    module_path = _BUILTIN_MODULES.get(scenario)
    if not module_path:
        return
    try:
        importlib.import_module(module_path)
    except Exception:  # noqa: BLE001 - 说明缺失不该影响执行
        return


def _spec_docs(scenario: str) -> dict[str, NodeDoc]:
    """spec 场景：节点 id -> 块的中文说明（现场推导，改完 spec 立刻生效）。

    按 ``active.json`` 的 mtime 缓存：轨迹页会按事件反复查节点，不能每次都读盘。
    """
    try:
        from core.scenarios.spec import active_spec_path, load_active_spec
        from core.scenarios.spec_nodes import block_desc, block_label
    except Exception:  # noqa: BLE001
        return {}
    try:
        path = active_spec_path(scenario)
        stamp = path.stat().st_mtime if path is not None else None
    except OSError:
        stamp = None
    cached = _SPEC_CACHE.get(scenario)
    if cached is not None and cached[0] == stamp and stamp is not None:
        return dict(cached[1])
    try:
        spec = load_active_spec(scenario)
    except Exception:  # noqa: BLE001
        return {}
    if spec is None:
        return {}
    docs: dict[str, NodeDoc] = {}
    for workflow, workflow_spec in spec.workflows.items():
        for node in workflow_spec.nodes:
            label = block_label(node.fn) or node.fn
            desc = block_desc(node.fn)
            if node.args:
                args_text = "，".join(f"{key}={value}" for key, value in node.args.items())
                desc = f"{desc}（参数：{args_text}）" if desc else f"参数：{args_text}"
            doc = NodeDoc(node=node.id, label=label, desc=desc, workflow=workflow)
            docs.setdefault(node.id, doc)
            docs[f"{workflow}:{node.id}"] = doc
    if stamp is not None:
        _SPEC_CACHE[scenario] = (stamp, dict(docs))
    return docs


def node_docs(scenario: str | None, workflow: str | None = None) -> dict[str, NodeDoc]:
    """返回该场景的节点说明表；``workflow`` 只用于查找时的优先顺序。"""
    name = str(scenario or "")
    _ = workflow
    if not name:
        return {}
    _load(name)
    table = dict(_spec_docs(name))
    table.update(REGISTRY.get(name, {}))
    return table


def describe_node(
    scenario: str | None,
    node: str | None,
    workflow: str | None = None,
) -> NodeDoc | None:
    """查一个节点的说明；先按 ``workflow:node``，再按裸节点名。"""
    if not node:
        return None
    table = node_docs(scenario, workflow)
    if workflow:
        found = table.get(f"{workflow}:{node}")
        if found is not None:
            return found
    return table.get(str(node))


def node_label(scenario: str | None, node: str | None, workflow: str | None = None) -> str:
    """展示用短名；没有说明时回到原始节点名。"""
    doc = describe_node(scenario, node, workflow)
    if doc is not None:
        return doc.title
    return str(node or "—")
