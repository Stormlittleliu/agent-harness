# -*- coding: utf-8 -*-
"""四类素材对象的 provider：工具池 / spec 工作流 / 场景库 / 块库。

设计原则：

- **列目录不构建场景**：工具 provider 只 import 工具模块，用"占位依赖"拿到
  工具对象（description / args_schema），不调用 ``pools.toolbox()``；
- **不 import 模型工厂 / 不发网络请求**：RAG 工具、外部 MCP 工具、subagent 的
  schema 写在静态表里；MCP server 只在 spec 里出现工具名时登记为"未解析占位"；
  scenario 直接扫描 spec 目录，不经过会 import generic 的 registry；
- **重资源延迟**：真正执行工具、构建场景、读向量库都不在这里发生；
- 所有结果都是 ``ResourceDescriptor``，由 catalog 统一排序 / 搜索 / 序列化。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from core.paths import PROJECT_ROOT, SPEC_ROOT
from core.resources.contracts import (
    ResourceDescriptor,
    ResourceKind,
    empty_object_schema,
)


# ---------------------------------------------------------------- 通用小工具


def _object(properties: dict[str, Any] | None = None, required: Iterable[str] = ()) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": dict(properties or {}),
        "required": [str(item) for item in required],
    }


def _prop(
    type_name: str,
    *,
    description: str = "",
    default: Any = None,
    enum: Iterable[str] | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
    items: str | None = None,
) -> dict[str, Any]:
    prop: dict[str, Any] = {"type": type_name}
    if description:
        prop["description"] = description
    if default is not None:
        prop["default"] = default
    if enum is not None:
        prop["enum"] = list(enum)
    if minimum is not None:
        prop["minimum"] = minimum
    if maximum is not None:
        prop["maximum"] = maximum
    if items is not None:
        prop["items"] = {"type": items}
    return prop


def _schema_from_tool(tool: Any) -> dict[str, Any]:
    """从 LangChain tool 的 args_schema 取 JSON schema；失败时返回空 object。"""
    schema = getattr(tool, "args_schema", None)
    if schema is None:
        return empty_object_schema()
    try:
        if hasattr(schema, "model_json_schema"):
            raw = schema.model_json_schema()
        elif hasattr(schema, "schema"):
            raw = schema.schema()
        else:
            return empty_object_schema()
    except Exception:  # noqa: BLE001 - 目录优先可用，坏 schema 不该拖垮列表
        return empty_object_schema()
    if not isinstance(raw, dict):
        return empty_object_schema()
    properties = raw.get("properties")
    if not isinstance(properties, dict):
        return empty_object_schema()
    required = raw.get("required") or []
    return _object(
        properties,
        [item for item in required if isinstance(item, str)],
    )


@dataclass(frozen=True)
class _ToolRecord:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=empty_object_schema)
    label: str = ""
    tags: tuple[str, ...] = ()
    pools: tuple[str, ...] = ()
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def _record_from_tool(
    tool: Any,
    *,
    source: str,
    pools: Iterable[str],
    tags: Iterable[str],
    label: str = "",
) -> _ToolRecord:
    name = str(getattr(tool, "name", "") or "").strip()
    return _ToolRecord(
        name=name,
        description=str(getattr(tool, "description", "") or ""),
        input_schema=_schema_from_tool(tool),
        label=label or name,
        tags=tuple(str(item) for item in tags),
        pools=tuple(str(item) for item in pools),
        source=source,
    )


class _Unused:
    """占位依赖：工具闭包会引用它，但目录查询不会调用任何方法。"""


# ---------------------------------------------------------------- 工具：轻量构造


@lru_cache(maxsize=None)
def _workspace_tools() -> tuple:
    from core.scenarios.workspace_assistant.tools import build_workspace_tools

    return tuple(build_workspace_tools(_Unused(), _Unused()))


@lru_cache(maxsize=None)
def _runtime_tools() -> tuple:
    from core.runtime.workspace import build_workspace_tools

    return tuple(build_workspace_tools(_Unused()))


@lru_cache(maxsize=None)
def _task_tools() -> tuple:
    from core.runtime.task_tools import build_task_tools

    return tuple(build_task_tools(_Unused()))


@lru_cache(maxsize=None)
def _research_tools() -> tuple:
    from core.scenarios.research_assistant.tools import build_research_tools

    return tuple(build_research_tools(_Unused()))


_OFFICE_TAGS = {
    "list_notes": ("笔记", "列表", "notes"),
    "read_note": ("笔记", "读取", "notes"),
    "search_notes": ("笔记", "检索", "搜索", "notes"),
    "write_note": ("笔记", "写入", "notes"),
    "remember": ("记忆", "偏好", "记住", "memory"),
    "recall": ("记忆", "偏好", "读取", "memory"),
    "list_memory": ("记忆", "列表", "memory"),
    "translate": ("翻译", "跨语言", "translate"),
    "summarize": ("总结", "摘要", "summarize"),
}

_CODING_TAGS = {
    "read_file": ("文件", "读取", "file"),
    "write_file": ("文件", "写入", "file"),
    "edit_file": ("文件", "编辑", "file"),
    "glob": ("文件", "查找", "glob"),
    "grep": ("文件", "搜索", "正则", "grep"),
    "run_command": ("命令", "执行", "shell"),
    "create_task": ("任务", "创建", "task"),
    "list_tasks": ("任务", "列表", "task"),
    "get_task": ("任务", "详情", "task"),
    "claim_task": ("任务", "认领", "task"),
    "complete_task": ("任务", "完成", "task"),
    "fail_task": ("任务", "失败", "task"),
}

_RESEARCH_TAGS = {
    "list_sources": ("资料", "列表", "research"),
    "read_source": ("资料", "读取", "research"),
    "search_sources": ("资料", "检索", "research"),
    "write_report": ("报告", "写入", "research"),
}

_BUSINESS_TAGS = {
    "reset_device": ("设备", "重置", "高风险", "device"),
    "get_weather": ("天气", "城市", "weather"),
    "get_user_location": ("位置", "城市", "location"),
    "get_user_id": ("用户", "ID", "user"),
    "get_current_month": ("月份", "日期", "month"),
    "fetch_external_data": ("使用记录", "报告", "外部数据", "record"),
}


def _workspace_records() -> list[_ToolRecord]:
    return [
        _record_from_tool(
            tool,
            source="core.scenarios.workspace_assistant.tools",
            pools=("office", "workspace_assistant"),
            tags=("办公", "笔记") + _OFFICE_TAGS.get(tool.name, ()),
        )
        for tool in _workspace_tools()
    ]


def _runtime_records() -> list[_ToolRecord]:
    return [
        _record_from_tool(
            tool,
            source="core.runtime.workspace",
            pools=("coding_demo",),
            tags=("编码", "文件") + _CODING_TAGS.get(tool.name, ()),
        )
        for tool in _runtime_tools()
    ]


def _task_records() -> list[_ToolRecord]:
    return [
        _record_from_tool(
            tool,
            source="core.runtime.task_tools",
            pools=("coding_demo",),
            tags=("编码", "任务") + _CODING_TAGS.get(tool.name, ()),
        )
        for tool in _task_tools()
    ]


def _research_records() -> list[_ToolRecord]:
    return [
        _record_from_tool(
            tool,
            source="core.scenarios.research_assistant.tools",
            pools=("research_assistant",),
            tags=("研究",) + _RESEARCH_TAGS.get(tool.name, ()),
        )
        for tool in _research_tools()
    ]


def _business_records() -> list[_ToolRecord]:
    from core.tools.business import tools as business_tools

    records = []
    for name in (
        "reset_device",
        "get_weather",
        "get_user_location",
        "get_user_id",
        "get_current_month",
        "fetch_external_data",
    ):
        tool = getattr(business_tools, name, None)
        if tool is None:
            continue
        records.append(
            _record_from_tool(
                tool,
                source="core.tools.business.tools",
                pools=("robot_vacuum",),
                tags=("机器人", "客服") + _BUSINESS_TAGS.get(name, ()),
            )
        )
    return records


def _static_tool_records() -> list[_ToolRecord]:
    """无法轻量构造的工具：只写元数据，绝不 import RAG/subagent 运行时。

    - RAG 工具的真实构造函数会初始化 embedding / 向量库；
    - subagent 会 import FrameworkAgent；
    - route_to_* 会 import 目标场景注册表。

    目录要的是 name/description/schema，这三样都是稳定契约，直接登记即可。
    """
    records: list[_ToolRecord] = []

    def rag(name: str, description: str, schema: dict[str, Any], tags: Iterable[str]) -> None:
        records.append(
            _ToolRecord(
                name=name,
                description=description,
                input_schema=schema,
                label=name,
                tags=tuple(str(item) for item in tags),
                pools=("retail_expert",),
                source="core.tools.rag.tools",
                metadata={"static_schema": True},
            )
        )

    summarize_schema = _object(
        {"query": _prop("string", description="检索词（用户问题或关键词）")},
        ["query"],
    )
    retrieve_schema = _object(
        {
            "query": _prop("string", description="检索词（用户问题或关键词）"),
            "k": _prop("integer", description="返回条数", default=4),
        },
        ["query"],
    )
    rag(
        "rag_summarize",
        "从向量存储中检索参考资料并总结回答",
        summarize_schema,
        ("检索", "知识库", "RAG", "总结"),
    )
    rag(
        "rag_retrieve",
        "检索知识库并返回原始资料片段（评测用）",
        retrieve_schema,
        ("检索", "知识库", "RAG", "评测"),
    )
    rag(
        "robot_rag",
        "从向量存储中检索参考资料并总结回答",
        summarize_schema,
        ("检索", "知识库", "RAG", "扫地机器人"),
    )
    rag(
        "robot_retrieve",
        "检索知识库并返回原始资料片段（评测用）",
        retrieve_schema,
        ("检索", "知识库", "RAG", "扫地机器人", "robot"),
    )
    rag(
        "clothing_rag",
        "从向量存储中检索参考资料并总结回答",
        summarize_schema,
        ("检索", "知识库", "RAG", "服装"),
    )
    rag(
        "clothing_retrieve",
        "检索知识库并返回原始资料片段（评测用）",
        retrieve_schema,
        ("检索", "知识库", "RAG", "服装", "clothing", "尺码"),
    )

    from core.runtime.config import SubagentConfig

    config = SubagentConfig()
    records.append(
        _ToolRecord(
            name=config.name,
            description=config.description,
            input_schema=_object(
                {"description": _prop("string", description="子 Agent 要完成的自包含子任务")},
                ["description"],
            ),
            label=config.name,
            tags=("子代理", "并发", "fan-out", "subagent"),
            pools=("coding_demo", "research_assistant"),
            source="core.agent.subagent",
        )
    )

    from core.scenarios.router.routes import load_routes

    for route in load_routes("router"):
        target = str(route.get("target") or "").strip()
        tool_name = str(route.get("tool") or "").strip()
        if not target or not tool_name:
            continue
        label = str(route.get("label") or target)
        description = str(route.get("description") or "").strip()
        records.append(
            _ToolRecord(
                name=tool_name,
                description=f"把{label}相关任务交给 {target} 场景。{description}".strip(),
                input_schema=_object(
                    {"query": _prop("string", description="要转交给目标场景的请求")},
                    ["query"],
                ),
                label=label,
                tags=("路由", "分流", "router", label),
                pools=("router",),
                source="core.scenarios.router.routes",
                metadata={"target": target},
            )
        )
    return records


# ---------------------------------------------------------------- spec 扫描


def _iter_active_specs():
    """只读扫描 ``data/specs/*/active.json`` 指向的 JSON，不 import spec 编译器。"""
    root = Path(SPEC_ROOT)
    if not root.is_dir():
        return
    for directory in sorted(root.iterdir(), key=lambda item: item.name):
        if not directory.is_dir():
            continue
        pointer_path = directory / "active.json"
        if not pointer_path.is_file():
            continue
        try:
            pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(pointer, dict):
            continue
        file_name = str(pointer.get("file") or "").strip()
        if not file_name:
            continue
        target = directory / file_name
        try:
            if target.resolve().parent != directory.resolve():
                continue
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        yield directory.name, payload, _spec_version(pointer, target), target


def _spec_version(pointer: dict[str, Any], path: Path) -> Any:
    version = pointer.get("version")
    if isinstance(version, int):
        return version
    if path.stem.startswith("v") and path.stem[1:].isdigit():
        return int(path.stem[1:])
    return None


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def _collect_tool_records() -> tuple[_ToolRecord, ...]:
    records: dict[str, _ToolRecord] = {}
    builders = (
        _workspace_records,
        _runtime_records,
        _task_records,
        _research_records,
        _business_records,
        _static_tool_records,
    )
    for builder in builders:
        try:
            items = builder()
        except Exception:  # noqa: BLE001 - 单个工具族坏了，目录仍要可用
            continue
        for record in items:
            if record.name:
                records.setdefault(record.name, record)

    # spec 里引用了但本地目录没有的工具（主要是外部 MCP）：登记占位，不连 server。
    referenced: dict[str, list[str]] = {}
    for scenario, payload, _version, _path in _iter_active_specs():
        for name in payload.get("tools") or []:
            text = str(name or "").strip()
            if text:
                referenced.setdefault(text, []).append(scenario)
    for name, scenarios in referenced.items():
        if name in records:
            continue
        external = name.startswith("memory_") or name.startswith("fetch_")
        records[name] = _ToolRecord(
            name=name,
            description=(
                "外部 MCP 工具（未连接 server；描述与参数 schema 以运行时为准）"
                if external
                else "工具目录未登记的工具（来自 spec 引用；schema 为空）"
            ),
            input_schema=empty_object_schema(),
            label=name,
            tags=("MCP", "外部", "外部工具") if external else ("未登记",),
            pools=(),
            source="mcp:external" if external else "spec:unresolved",
            metadata={
                "external": external,
                "resolved": False,
                "referenced_by": sorted(set(scenarios)),
            },
        )
    return tuple(records[key] for key in sorted(records))


# ---------------------------------------------------------------- providers


class ToolProvider:
    kind = ResourceKind.TOOL

    def __init__(self) -> None:
        self._cache: tuple[_ToolRecord, ...] | None = None

    def _records(self) -> tuple[_ToolRecord, ...]:
        if self._cache is None:
            self._cache = _collect_tool_records()
        return self._cache

    def refresh(self) -> None:
        self._cache = None

    def _descriptor(self, record: _ToolRecord) -> ResourceDescriptor:
        metadata = {
            "pools": list(record.pools),
            "schema_available": bool(record.input_schema.get("properties")),
        }
        metadata.update(record.metadata)
        return ResourceDescriptor(
            kind=ResourceKind.TOOL,
            id=record.name,
            name=record.name,
            label=record.label or record.name,
            description=record.description,
            tags=record.tags,
            source=record.source,
            version=None,
            metadata=metadata,
            input_schema=record.input_schema,
        )

    def items(self) -> list[ResourceDescriptor]:
        return [self._descriptor(record) for record in self._records()]

    def get(self, resource_id: str) -> ResourceDescriptor | None:
        for record in self._records():
            if record.name == resource_id:
                return self._descriptor(record)
        return None


def _split_edge(edge: Any) -> tuple[str, str, str | None]:
    if isinstance(edge, dict):
        when = edge.get("when")
        return (
            str(edge.get("from") or ""),
            str(edge.get("to") or ""),
            None if when in (None, "") else str(when),
        )
    if isinstance(edge, (list, tuple)) and len(edge) >= 2:
        when = edge[2] if len(edge) >= 3 else None
        return str(edge[0]), str(edge[1]), None if when in (None, "") else str(when)
    return "", "", None


def _workflow_descriptor(
    scenario: str,
    name: str,
    workflow: dict[str, Any],
    version: Any,
    path: Path,
) -> ResourceDescriptor:
    from core.scenarios.spec_nodes import block_desc, block_label

    raw_nodes = workflow.get("nodes") if isinstance(workflow.get("nodes"), list) else []
    raw_edges = workflow.get("edges") if isinstance(workflow.get("edges"), list) else []
    nodes: list[dict[str, Any]] = []
    tools: set[str] = set()
    for node in raw_nodes:
        if not isinstance(node, dict):
            continue
        fn = str(node.get("fn") or "")
        args = node.get("args") if isinstance(node.get("args"), dict) else {}
        nodes.append(
            {
                "id": str(node.get("id") or ""),
                "fn": fn,
                "label": block_label(fn),
                "desc": block_desc(fn),
                "args": dict(args),
            }
        )
        if isinstance(args.get("tool"), str) and args["tool"].strip():
            tools.add(args["tool"].strip())
        for item in args.get("tools") or []:
            if str(item or "").strip():
                tools.add(str(item).strip())
    edges = []
    for edge in raw_edges:
        source, target, when = _split_edge(edge)
        if source and target:
            edges.append({"from": source, "to": target, "when": when})
    chain = " → ".join(node["label"] or node["fn"] for node in nodes) or "（空）"
    tags = ["工作流", "workflow", scenario]
    tags.extend(node["label"] for node in nodes if node["label"])
    metadata = {
        "scenario": scenario,
        "workflow": name,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "tools": sorted(tools),
        "source_file": _display_path(path),
    }
    return ResourceDescriptor(
        kind=ResourceKind.WORKFLOW,
        id=f"{scenario}/{name}",
        name=name,
        label=f"{scenario} / {name}",
        description=f"场景 {scenario} 的工作流 {name}：{len(nodes)} 个节点（{chain}）",
        tags=tuple(dict.fromkeys(tags)),
        source=_display_path(path),
        version=version,
        metadata=metadata,
        input_schema=_object(
            {"input": _prop("string", description="用户输入（SpecState.input）")},
            ["input"],
        ),
    )


class WorkflowProvider:
    kind = ResourceKind.WORKFLOW

    def items(self) -> list[ResourceDescriptor]:
        result: list[ResourceDescriptor] = []
        for scenario, payload, version, path in _iter_active_specs():
            workflows = payload.get("workflows")
            if not isinstance(workflows, dict):
                continue
            for name in sorted(workflows):
                workflow = workflows[name]
                if isinstance(workflow, dict):
                    result.append(_workflow_descriptor(scenario, name, workflow, version, path))
        return result

    def get(self, resource_id: str) -> ResourceDescriptor | None:
        scenario, _, name = str(resource_id).partition("/")
        if not scenario or not name:
            return None
        for current, payload, version, path in _iter_active_specs():
            if current != scenario:
                continue
            workflows = payload.get("workflows")
            if isinstance(workflows, dict) and isinstance(workflows.get(name), dict):
                return _workflow_descriptor(current, name, workflows[name], version, path)
        return None


def _scenario_descriptor(entry: Any, version: Any) -> ResourceDescriptor:
    tags = ["场景", "scenario", entry.kind]
    tags.append("spec" if entry.from_spec else "code")
    tags.append("可编辑" if entry.editable else "只读")
    if entry.has_workflow:
        tags.append("工作流")
    metadata = {
        "icon": entry.icon,
        "kind": entry.kind,
        "title": entry.title,
        "badge": entry.badge,
        "owner": entry.owner,
        "editable": entry.editable,
        "from_spec": entry.from_spec,
        "has_workflow": entry.has_workflow,
        "supports_runtime": entry.supports_runtime,
        "pool": entry.pool,
        "cases": entry.cases,
        "issue": entry.issue,
        "examples": list(entry.examples),
    }
    if entry.extra:
        metadata["extra"] = dict(entry.extra)
    if entry.from_spec:
        source = f"data/specs/{entry.name}/active.json"
    else:
        source = f"core/scenarios/{entry.name}"
    return ResourceDescriptor(
        kind=ResourceKind.SCENARIO,
        id=entry.name,
        name=entry.name,
        label=entry.label,
        description=entry.description,
        tags=tuple(dict.fromkeys(tags)),
        source=source,
        version=version,
        metadata=metadata,
        input_schema=empty_object_schema(),
    )


class ScenarioProvider:
    kind = ResourceKind.SCENARIO

    @staticmethod
    def _versions() -> dict[str, Any]:
        return {
            scenario: version
            for scenario, _payload, version, _path in _iter_active_specs()
        }

    def items(self) -> list[ResourceDescriptor]:
        from core.scenarios import library

        versions = self._versions()
        return [
            _scenario_descriptor(entry, versions.get(entry.name))
            for entry in library.entries()
        ]

    def get(self, resource_id: str) -> ResourceDescriptor | None:
        from core.scenarios import library

        entry = library.entry(resource_id)
        if entry is None:
            return None
        return _scenario_descriptor(entry, self._versions().get(entry.name))


def _param_schema(params: Iterable[Any]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param in params:
        type_name = str(getattr(param, "type", "str"))
        prop: dict[str, Any]
        if type_name == "int":
            prop = _prop(
                "integer",
                description=str(getattr(param, "help", "") or ""),
                default=getattr(param, "default", None),
                minimum=getattr(param, "minimum", None),
                maximum=getattr(param, "maximum", None),
            )
        elif type_name == "float":
            prop = _prop(
                "number",
                description=str(getattr(param, "help", "") or ""),
                default=getattr(param, "default", None),
                minimum=getattr(param, "minimum", None),
                maximum=getattr(param, "maximum", None),
            )
        elif type_name == "bool":
            prop = _prop(
                "boolean",
                description=str(getattr(param, "help", "") or ""),
                default=getattr(param, "default", None),
            )
        elif type_name == "enum":
            prop = _prop(
                "string",
                description=str(getattr(param, "help", "") or ""),
                default=getattr(param, "default", None),
                enum=getattr(param, "choices", None),
            )
        elif type_name in {"str_list", "tool_list"}:
            prop = _prop(
                "array",
                description=str(getattr(param, "help", "") or ""),
                default=getattr(param, "default", None),
                items="string",
            )
        else:
            prop = _prop(
                "string",
                description=str(getattr(param, "help", "") or ""),
                default=getattr(param, "default", None),
            )
        properties[str(param.name)] = prop
        if bool(getattr(param, "required", False)):
            required.append(str(param.name))
    return _object(properties, required)


def _param_dict(param: Any) -> dict[str, Any]:
    return {
        "name": str(param.name),
        "type": str(param.type),
        "default": getattr(param, "default", None),
        "required": bool(getattr(param, "required", False)),
        "choices": list(getattr(param, "choices", ()) or ()),
        "minimum": getattr(param, "minimum", None),
        "maximum": getattr(param, "maximum", None),
        "help": str(getattr(param, "help", "") or ""),
    }


def _port_dict(port: Any) -> dict[str, Any]:
    return {
        "name": str(port.name),
        "type": str(port.type),
        "required": bool(getattr(port, "required", False)),
        "default": getattr(port, "default", None),
        "help": str(getattr(port, "help", "") or ""),
    }


class BlockProvider:
    kind = ResourceKind.BLOCK

    def items(self) -> list[ResourceDescriptor]:
        from core.scenarios import spec_nodes

        result = []
        for name in spec_nodes.registered_nodes():
            params = spec_nodes.block_params(name)
            ports = spec_nodes.block_ports(name, {})
            label = spec_nodes.block_label(name)
            result.append(
                ResourceDescriptor(
                    kind=ResourceKind.BLOCK,
                    id=name,
                    name=name,
                    label=label,
                    description=spec_nodes.block_desc(name),
                    tags=tuple(
                        dict.fromkeys(
                            (
                                "工作流块",
                                "block",
                                label,
                                *[part for part in name.split("_") if part],
                            )
                        )
                    ),
                    source="core.scenarios.spec_nodes",
                    version=None,
                    metadata={
                        "params": [_param_dict(param) for param in params],
                        "inputs": [_port_dict(port) for port in ports.inputs],
                        "outputs": [_port_dict(port) for port in ports.outputs],
                    },
                    input_schema=_param_schema(params),
                )
            )
        return result

    def get(self, resource_id: str) -> ResourceDescriptor | None:
        return next((item for item in self.items() if item.id == resource_id), None)


def default_providers() -> list[Any]:
    return [ToolProvider(), WorkflowProvider(), ScenarioProvider(), BlockProvider()]
