# -*- coding: utf-8 -*-
"""把一个线性范式编译成候选 spec（M2）。

边界（刻意的）：

- 只允许 ``spec_nodes`` 里已注册的块，不内联代码；
- 只编译**线性**范式；带 ``branch`` 的范式需要条件边，M2 直接拒绝；
- 不覆盖 active：候选写到 ``data/specs/<scenario>/candidates/<pattern_id>.json``，
  不写 ``active.json``，也不产生 ``vN.json``；
- 编译结果必须过 ``validate_spec`` + ``build_workflows`` 才算成功。

节点名怎么映射成块：

1. 优先在源 spec 的节点里按 id 找（复用它的 fn 和 args）；
2. 其次把节点名本身当块名（``retrieve`` / ``llm_answer``）；
3. ``tool:<name>`` 映射成 ``call_tool``（query={input}，save_to=tool_result）；
4. ``model`` 映射成 ``llm_answer``；
5. 其余报错，不猜。
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

from core.scenarios.spec import (
    SPEC_ROOT,
    NodeSpec,
    ScenarioSpec,
    SpecError,
    WorkflowSpec,
    build_workflows,
    load_active_spec,
    spec_to_dict,
    validate_spec,
)
from core.scenarios.spec_nodes import NODE_REGISTRY, block_params

CANDIDATE_WORKFLOW = "mined"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")

CANDIDATE_DIR = "candidates"
GENERIC_MODEL_STEPS = {"model", "llm"}
GENERIC_SKIP_STEPS = {"tools", "agent", "chain"}


class PatternCompileError(ValueError):
    """范式无法编译；``errors`` 是逐条可展示的原因。"""

    def __init__(self, errors: Iterable[str]):
        self.errors = list(errors)
        super().__init__("；".join(self.errors))


@dataclass
class Candidate:
    spec: ScenarioSpec
    path: Path | None = None


def _get(pattern: Any, key: str, default: Any = None) -> Any:
    if isinstance(pattern, dict):
        return pattern.get(key, default)
    return getattr(pattern, key, default)


def _block_defaults(fn: str) -> dict[str, Any]:
    args: dict[str, Any] = {}
    for param in block_params(fn):
        if param.required:
            continue
        if param.default is not None:
            args[param.name] = param.default
    return args


def _source_nodes(source_spec: ScenarioSpec | None) -> dict[str, NodeSpec]:
    if source_spec is None:
        return {}
    nodes: dict[str, NodeSpec] = {}
    for workflow in (source_spec.workflows or {}).values():
        for node in workflow.nodes:
            nodes.setdefault(node.id, node)
    return nodes


def _pick_tool(tool_names: set[str]) -> str:
    return sorted(tool_names)[0]


def _fill_required(fn: str, args: dict[str, Any], tool_names: set[str]) -> dict[str, Any]:
    """补必填参数；补不出来就报错，不生成一个跑不起来的 candidate。"""
    filled = dict(args)
    for param in block_params(fn):
        if not param.required or param.name in filled:
            continue
        if param.type == "tool_list":
            if not tool_names:
                raise PatternCompileError([f"{fn}.{param.name} 需要工具，但场景没有可用工具"])
            filled[param.name] = sorted(tool_names)
        elif param.name == "tool":
            if not tool_names:
                raise PatternCompileError([f"{fn}.{param.name} 需要工具，但场景没有可用工具"])
            filled[param.name] = _pick_tool(tool_names)
        else:
            raise PatternCompileError([
                f"{fn}.{param.name} 是必填参数，范式里没有提供；"
                "M2 不猜业务文案，请在源 spec 或范式中补齐"
            ])
    return filled


def _resolve_step(
    step: str,
    *,
    source_nodes: dict[str, NodeSpec],
    tool_names: set[str],
) -> tuple[str, dict[str, Any]]:
    name = str(step or "").strip()
    if not name:
        raise PatternCompileError(["范式里有空步骤"])

    source = source_nodes.get(name)
    if source is not None:
        return source.fn, dict(source.args)

    if name.startswith("tool:"):
        tool = name.split(":", 1)[1].strip()
        if not tool:
            raise PatternCompileError(["tool: 后面没有工具名"])
        if tool_names and tool not in tool_names:
            raise PatternCompileError([f"工具 {tool} 不在场景工具白名单里"])
        return "call_tool", {
            "tool": tool,
            "args": '{"query": "{input}"}',
            "save_to": "tool_result",
        }

    if name in GENERIC_MODEL_STEPS:
        return "llm_answer", {}
    if name in GENERIC_SKIP_STEPS:
        raise PatternCompileError([f"{name} 是运行时通用节点，不能直接编译成工作流块"])

    if name in NODE_REGISTRY:
        return name, _block_defaults(name)

    raise PatternCompileError([
        f"步骤 {name} 既不是已注册的块，也不在源 spec 里；"
        f"可用块：{', '.join(sorted(NODE_REGISTRY))}"
    ])


def _node_id(fn: str, used: set[str]) -> str:
    base = re.sub(r"[^0-9A-Za-z_]", "_", fn) or "step"
    node_id = base
    index = 2
    while node_id in used:
        node_id = f"{base}_{index}"
        index += 1
    used.add(node_id)
    return node_id


def _pattern_steps(pattern: Any) -> list[str]:
    steps = _get(pattern, "steps") or _get(pattern, "nodes") or []
    return [str(item.get("block") if isinstance(item, dict) else item) for item in steps]


def _pattern_provenance(pattern: Any) -> dict[str, Any]:
    pattern_id = str(_get(pattern, "pattern_id") or _get(pattern, "id") or "")
    evidence = [str(item) for item in (_get(pattern, "evidence") or [])]
    run_ids = sorted({item.split(":", 1)[0] for item in evidence if item})
    return {
        "source": "mined",
        "pattern_id": pattern_id,
        "pattern_name": str(_get(pattern, "name") or ""),
        "pattern_kind": str(_get(pattern, "kind") or ""),
        "scope": dict(_get(pattern, "scope") or {}),
        "steps": _pattern_steps(pattern),
        "support": int(_get(pattern, "support") or 0),
        "success_rate": float(_get(pattern, "success_rate") or 0.0),
        "lift": float(_get(pattern, "lift") or 0.0),
        "evidence_runs": run_ids,
        "created_at": _now(),
        "status": "candidate",
    }


def pattern_to_spec(
    pattern: Any,
    *,
    scenario: str | None = None,
    source_spec: ScenarioSpec | None = None,
    tool_names: set[str] | None = None,
) -> ScenarioSpec:
    """把线性范式编译成候选 ``ScenarioSpec``；失败抛 ``PatternCompileError``。

    ``source_spec`` 用于复用节点 fn/args、提示词、harness 和工具清单；
    传 ``None`` 时只根据范式步骤和白名单工具生成最小 spec。
    """
    scope = dict(_get(pattern, "scope") or {})
    scenario = (scenario or scope.get("scenario") or (source_spec.name if source_spec else "")).strip()
    if not scenario:
        raise PatternCompileError(["没有场景名：pattern.scope.scenario 为空"])

    steps = _pattern_steps(pattern)
    if not steps:
        raise PatternCompileError(["范式没有步骤"])
    if "branch" in steps or any(
        item in NODE_REGISTRY and item == "branch" for item in steps
    ):
        raise PatternCompileError(["M2 只编译线性范式；branch 需要条件边，暂不支持"])

    if tool_names is None:
        tool_names = set(source_spec.tools) if source_spec is not None else set()
    tool_names = {str(name) for name in tool_names}

    source_nodes = _source_nodes(source_spec)
    used: set[str] = set()
    nodes: list[NodeSpec] = []
    for step in steps:
        fn, args = _resolve_step(step, source_nodes=source_nodes, tool_names=tool_names)
        if fn == "branch":
            raise PatternCompileError(["M2 只编译线性范式；branch 需要条件边，暂不支持"])
        args = _fill_required(fn, args, tool_names)
        nodes.append(NodeSpec(id=_node_id(fn, used), fn=fn, args=args))

    edges: list[list[str]] = [["__start__", nodes[0].id]]
    for source, target in zip(nodes, nodes[1:]):
        edges.append([source.id, target.id])
    edges.append([nodes[-1].id, "__end__"])
    workflow = WorkflowSpec(nodes=nodes, edges=edges)

    if source_spec is not None:
        spec = source_spec.model_copy(deep=True)
        spec.name = scenario
        spec.description = f"{source_spec.description or scenario}（候选工作流，未采纳）"
        spec.workflows = {CANDIDATE_WORKFLOW: workflow}
        spec.provenance = _pattern_provenance(pattern)
    else:
        spec = ScenarioSpec(
            name=scenario,
            description="由轨迹范式编译的候选工作流（未采纳）",
            tools=sorted(tool_names),
            system_prompt="你是严谨的助手。回答必须用 [来源id] 标注引用；资料不足就明确说无法确定。",
            workflows={CANDIDATE_WORKFLOW: workflow},
            provenance=_pattern_provenance(pattern),
        )

    errors = validate_spec(spec, tool_names=tool_names)
    if errors:
        raise PatternCompileError(errors)

    # 结构校验不够，还要真的编译一次：块参数、端口、边都要能进 StateGraph。
    stub = SimpleNamespace(
        tools=[SimpleNamespace(name=name) for name in sorted(tool_names)]
    )
    try:
        build_workflows(spec, stub)
    except SpecError as exc:
        raise PatternCompileError(exc.errors) from exc
    return spec


def candidate_path(
    name: str,
    pattern_id: str,
    root: Path | str = SPEC_ROOT,
) -> Path:
    safe = re.sub(r"[^0-9A-Za-z_-]", "_", str(pattern_id or "pattern")).strip("._-")
    return Path(root) / name / CANDIDATE_DIR / f"{safe or 'pattern'}.json"


def save_candidate(
    spec: ScenarioSpec,
    pattern_id: str,
    *,
    root: Path | str = SPEC_ROOT,
) -> Path:
    """原子写候选文件；不碰 ``vN.json`` / ``active.json``。"""
    target = candidate_path(spec.name, pattern_id, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(
        json.dumps(spec_to_dict(spec), ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(target)
    return target


def compile_pattern(
    pattern: Any,
    *,
    scenario: str | None = None,
    source_spec: ScenarioSpec | None = None,
    tool_names: set[str] | None = None,
    root: Path | str = SPEC_ROOT,
    write: bool = True,
) -> Candidate:
    """编译并（默认）落候选文件；返回 ``Candidate``。"""
    spec = pattern_to_spec(
        pattern,
        scenario=scenario,
        source_spec=source_spec,
        tool_names=tool_names,
    )
    pattern_id = str(_get(pattern, "pattern_id") or _get(pattern, "id") or "pattern")
    path = save_candidate(spec, pattern_id, root=root) if write else None
    return Candidate(spec=spec, path=path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把线性范式编译成候选 spec（不采纳）")
    parser.add_argument("--patterns", required=True, help="patterns.json 路径")
    parser.add_argument("--pattern-id", help="默认取第一条")
    parser.add_argument("--scenario", help="覆盖 pattern.scope.scenario")
    parser.add_argument("--tools", help="逗号分隔的工具白名单；没有 active spec 时必填")
    parser.add_argument("--root", default=str(SPEC_ROOT))
    parser.add_argument("--dry-run", action="store_true", help="只校验，不写候选文件")
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.patterns).read_text(encoding="utf-8"))
    patterns = payload.get("patterns") or []
    if not patterns:
        print("patterns.json 里没有范式")
        return 1
    pattern = patterns[0]
    if args.pattern_id:
        pattern = next(
            (item for item in patterns if item.get("pattern_id") == args.pattern_id), None
        )
        if pattern is None:
            print(f"找不到 pattern_id：{args.pattern_id}")
            return 1

    scenario = args.scenario or (pattern.get("scope") or {}).get("scenario")
    source_spec = load_active_spec(scenario) if scenario else None
    if args.tools:
        tool_names = {item.strip() for item in args.tools.split(",") if item.strip()}
    else:
        tool_names = set(source_spec.tools) if source_spec is not None else None
    try:
        candidate = compile_pattern(
            pattern,
            scenario=scenario,
            source_spec=source_spec,
            tool_names=tool_names,
            root=args.root,
            write=not args.dry_run,
        )
    except PatternCompileError as exc:
        print("编译失败：")
        for error in exc.errors:
            print(f"  - {error}")
        return 1

    print(f"scenario={candidate.spec.name} workflow={CANDIDATE_WORKFLOW}")
    print(f"nodes={[node.fn for node in candidate.spec.workflows[CANDIDATE_WORKFLOW].nodes]}")
    print(f"candidate={candidate.path or '（dry-run，未写盘）'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
