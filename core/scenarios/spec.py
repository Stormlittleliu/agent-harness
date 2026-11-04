# -*- coding: utf-8 -*-
"""spec 驱动的场景定义：受约束的伪低代码。

它只做三件事：

1. 校验一份 spec（节点/边/函数引用是否成立）；
2. 把 spec 编译成 LangGraph（``StateGraph``）；
3. 版本化读写 spec（``data/specs/<scenario>/vN.json`` + ``active.json``）。

它**不**做的事（这是刻意的）：

- 不把现有代码场景序列化成 spec；
- 不追求任意图 -> spec -> 图的完备往返；
- 删节点后不自动重连，悬空边直接报错。

所以 spec 是"新增场景的一种方式"，不是"所有场景的格式"。
"""
from __future__ import annotations

import json
from functools import partial
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core.agent.pipeline import available_policies
from core.scenarios.spec_nodes import NODE_REGISTRY, validate_args, validate_tool_refs

SPEC_VERSION = 1
SPEC_ROOT = Path("data/specs")
ACTIVE_FILE = "active.json"
RESERVED_ARGS = {"scenario", "state", "config", "runtime"}


class SpecError(ValueError):
    """spec 不合法；``errors`` 是逐条可展示的原因。"""

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__("；".join(self.errors))


class SpecState(TypedDict, total=False):
    """spec 场景只有一个通用 state，节点只能读写这几个键。"""

    input: str
    tool_result: str
    answer: str
    scratch: dict


class NodeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    fn: str
    args: dict[str, Any] = Field(default_factory=dict)


class WorkflowSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[NodeSpec] = Field(default_factory=list)
    edges: list[tuple[str, str]] = Field(default_factory=list)


class HarnessSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enable_todo: bool = False
    enable_summarization: bool = True
    tool_call_limit: int | None = 8
    token_budget: int | None = None


class PolicySpecModel(BaseModel):
    """策略覆盖项：默认开启、显式移除、参数可配。"""

    model_config = ConfigDict(extra="forbid")

    name: str
    enabled: bool = True
    args: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None


class ScenarioSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = SPEC_VERSION
    name: str
    description: str = ""
    # 场景类型：agent / router（router 靠 planning 规则分流，界面上多一个路由配置面板）
    kind: str = "agent"
    tools: list[str] = Field(default_factory=list)
    system_prompt: str = ""
    # 行为用例文件（相对仓库根）；留空则找 data/specs/<name>/cases.jsonl。
    # 仿造现有场景时指向原来的 cases，保证两边是同一把尺子。
    cases_path: str | None = None
    harness: HarnessSpec = Field(default_factory=HarnessSpec)
    policies: list[PolicySpecModel] | None = None
    workflows: dict[str, WorkflowSpec] = Field(default_factory=dict)


# ---------------------------------------------------------------- 校验


def _walk(seed: str, adjacency: dict[str, set[str]]) -> set[str]:
    seen = {seed}
    stack = [seed]
    while stack:
        current = stack.pop()
        for nxt in adjacency.get(current, ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def _validate_workflow(name: str, workflow: WorkflowSpec, tool_names: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    prefix = f"workflow[{name}]"
    node_ids = [node.id for node in workflow.nodes]
    if not node_ids:
        return [f"{prefix} 没有节点"]
    if len(set(node_ids)) != len(node_ids):
        duplicates = sorted({node_id for node_id in node_ids if node_ids.count(node_id) > 1})
        errors.extend(f"{prefix} 节点 id 重复：{node_id}" for node_id in duplicates)
    for node in workflow.nodes:
        if not node.id.strip():
            errors.append(f"{prefix} 存在空节点 id")
        if node.fn not in NODE_REGISTRY:
            errors.append(f"{prefix}.{node.id} 引用了未注册的块：{node.fn}")
        reserved = sorted(RESERVED_ARGS & set(node.args))
        if reserved:
            errors.append(f"{prefix}.{node.id} 的参数名被保留：{', '.join(reserved)}")
        errors.extend(f"{prefix}.{node.id}：{error}" for error in validate_args(node.fn, node.args))
        if tool_names is not None:
            errors.extend(
                f"{prefix}.{node.id}：{error}"
                for error in validate_tool_refs(node.fn, node.args, tool_names)
            )

    known = set(node_ids) | {START, END}
    adjacency: dict[str, set[str]] = {}
    reverse: dict[str, set[str]] = {}
    for source, target in workflow.edges:
        if source not in known:
            errors.append(f"{prefix} 边起点不存在：{source}")
            continue
        if target not in known:
            errors.append(f"{prefix} 边终点不存在：{target}")
            continue
        adjacency.setdefault(source, set()).add(target)
        reverse.setdefault(target, set()).add(source)

    if not adjacency.get(START):
        errors.append(f"{prefix} 缺少从 START 出发的边")
    if not reverse.get(END):
        errors.append(f"{prefix} 缺少指向 END 的边")

    reachable = _walk(START, adjacency)
    for node_id in node_ids:
        if node_id not in reachable:
            errors.append(f"{prefix}.{node_id} 从 START 不可达")
    finishing = _walk(END, reverse)
    for node_id in node_ids:
        if node_id not in finishing:
            errors.append(f"{prefix}.{node_id} 走不到 END")
    return errors


def validate_spec(spec: ScenarioSpec, tool_names: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    if spec.schema_version != SPEC_VERSION:
        errors.append(f"schema_version 必须是 {SPEC_VERSION}，收到 {spec.schema_version}")
    if not spec.name.strip():
        errors.append("scenario.name 不能为空")
    # 允许没有 workflow：纯 ReAct 场景（general / coding / router…）只有一个 agent 循环。
    known_policies = set(available_policies())
    for policy in spec.policies or []:
        if policy.name not in known_policies:
            errors.append(
                f"未知策略：{policy.name}（可用：{', '.join(sorted(known_policies))}）"
            )
        if not policy.enabled and not (policy.reason or "").strip():
            errors.append(f"策略 {policy.name} 被关闭但没有写 reason：移除守卫必须可审计")
    for name, workflow in spec.workflows.items():
        errors.extend(_validate_workflow(name, workflow, tool_names))
    return errors


# ---------------------------------------------------------------- 编译


def build_workflows(spec: ScenarioSpec, scenario: Any) -> dict[str, Any]:
    """把 spec 编译成 ``{workflow_name: compiled_graph}``，可直接传给 ``Scenario.workflow_factory``。"""
    tool_names = {getattr(tool, "name", "") for tool in getattr(scenario, "tools", [])}
    errors = validate_spec(spec, tool_names=tool_names)
    if errors:
        raise SpecError(errors)

    graphs: dict[str, Any] = {}
    for name, workflow in spec.workflows.items():
        graph = StateGraph(SpecState)
        for node in workflow.nodes:
            fn = NODE_REGISTRY[node.fn]
            graph.add_node(node.id, partial(fn, scenario=scenario, **node.args))
        for source, target in workflow.edges:
            if source == START:
                graph.add_edge(START, target)
            elif target == END:
                graph.add_edge(source, END)
            else:
                graph.add_edge(source, target)
        graphs[name] = graph.compile()
    return graphs


def build_from_spec(
    spec: ScenarioSpec,
    *,
    tools: list[Any],
    model: Any,
    cases_path: Path | None = None,
    checkpoint_backend: str = "memory",
    checkpoint_path: str = "data/runtime/spec_checkpoints.sqlite",
    runtime: Any = None,
) -> Any:
    """用 spec 组装一个 ``Scenario``；工具按 ``spec.tools`` 白名单过滤。"""
    from core.agent.contracts import Scenario

    errors = validate_spec(spec)
    if errors:
        raise SpecError(errors)

    by_name = {getattr(tool, "name", ""): tool for tool in tools}
    missing = [name for name in spec.tools if name not in by_name]
    if missing:
        raise SpecError([f"场景缺少工具：{', '.join(missing)}"])
    # 允许没有工具：白板 / 结构化输出这类场景只有一个 agent 循环。
    selected = [by_name[name] for name in spec.tools]

    # 工具白名单确定后再校验一次：块里引用的 tool_list 必须真的可用。
    errors = validate_spec(spec, tool_names={tool.name for tool in selected})
    if errors:
        raise SpecError(errors)

    harness = spec.harness
    return Scenario(
        name=spec.name,
        description=spec.description,
        model=model,
        system_prompt=spec.system_prompt,
        tools=selected,
        kind=spec.kind,
        middleware=[],
        policies=[policy.model_dump() for policy in spec.policies] if spec.policies is not None else None,
        context={},
        cases_path=cases_path,
        enable_todo=harness.enable_todo,
        enable_summarization=harness.enable_summarization,
        tool_call_limit=harness.tool_call_limit,
        token_budget=harness.token_budget,
        checkpoint=True,
        checkpoint_backend=checkpoint_backend,
        checkpoint_path=checkpoint_path,
        workflow_factory=(lambda scenario: build_workflows(spec, scenario)) if spec.workflows else None,
        runtime=runtime,
    )


def resolve_cases_path(spec: ScenarioSpec, root: Path | str = SPEC_ROOT) -> Path | None:
    """行为用例路径：spec 显式指定优先，否则找 spec 目录下的 cases.jsonl。"""
    if spec.cases_path:
        candidate = Path(spec.cases_path)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        return candidate if candidate.is_file() else None
    fallback = Path(root) / spec.name / "cases.jsonl"
    return fallback if fallback.is_file() else None


# ---------------------------------------------------------------- 读写


def spec_to_dict(spec: ScenarioSpec) -> dict[str, Any]:
    return spec.model_dump(mode="json")


def spec_from_dict(data: dict[str, Any]) -> ScenarioSpec:
    try:
        return ScenarioSpec.model_validate(data)
    except ValidationError as exc:
        raise SpecError([str(exc)]) from exc


def save_spec(
    spec: ScenarioSpec,
    root: Path | str = SPEC_ROOT,
    make_active: bool = True,
) -> Path:
    """原子写入新版本；编译失败请先校验，再调用本函数。"""
    directory = Path(root) / spec.name
    directory.mkdir(parents=True, exist_ok=True)
    versions = [
        int(path.stem[1:])
        for path in directory.glob("v*.json")
        if path.stem[1:].isdigit()
    ]
    version = (max(versions) + 1) if versions else 1
    target = directory / f"v{version}.json"
    payload = json.dumps(spec_to_dict(spec), ensure_ascii=False, indent=2)
    tmp = directory / f"v{version}.json.tmp"
    # 固定 LF：spec 是给人和 git 看的文本，不该因为平台不同产生假 diff。
    tmp.write_text(payload, encoding="utf-8", newline="\n")
    tmp.replace(target)
    if make_active:
        pointer = {"version": version, "file": target.name}
        (directory / ACTIVE_FILE).write_text(
            json.dumps(pointer, ensure_ascii=False, indent=2),
            encoding="utf-8",
            newline="\n",
        )
    return target


def load_spec(path: Path | str) -> ScenarioSpec:
    return spec_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def active_spec_path(name: str, root: Path | str = SPEC_ROOT) -> Path | None:
    directory = Path(root) / name
    pointer = directory / ACTIVE_FILE
    if not pointer.exists():
        return None
    try:
        data = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    candidate = directory / str(data.get("file") or "")
    return candidate if candidate.is_file() else None


def load_active_spec(name: str, root: Path | str = SPEC_ROOT) -> ScenarioSpec | None:
    path = active_spec_path(name, root)
    return load_spec(path) if path is not None else None
