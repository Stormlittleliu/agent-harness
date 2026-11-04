# -*- coding: utf-8 -*-
"""spec 场景可用的块库（受约束的伪低代码）。

约束（这是"伪"的来源，别绕开）：

- 节点只有一个通用 state：``input / tool_result / answer / scratch``；
- 节点只能引用这里注册过的块，spec 里不允许内联代码；
- 每个块用 ``ParamSpec`` 声明自己能接什么参数，编辑器据此渲染表单、编译器据此校验；
- 节点失败时把原因写进 ``scratch.error``，不抛异常打断整张图。

节点签名统一为 ``fn(state, scenario=None, **args) -> dict``，
编译时用 ``functools.partial`` 绑定 scenario 和 args。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

REPORT_ROOT = Path("data/runtime/spec_reports")
CITATION_PATTERN = r"\[[^\]]+\]"

NodeFn = Callable[..., dict[str, Any]]
NODE_REGISTRY: dict[str, NodeFn] = {}
NODE_PARAMS: dict[str, tuple["ParamSpec", ...]] = {}
NODE_LABELS: dict[str, str] = {}
NODE_DESCS: dict[str, str] = {}


@dataclass(frozen=True)
class ParamSpec:
    """块的一个参数。UI 用它渲染表单，编译器用它校验 spec。"""

    name: str
    type: str  # str / int / float / bool / enum / str_list / tool_list
    default: Any = None
    required: bool = False
    choices: tuple[str, ...] | None = None
    minimum: float | None = None
    maximum: float | None = None
    help: str = ""


def register_node(
    name: str,
    params: tuple[ParamSpec, ...] | list[ParamSpec] = (),
    *,
    label: str = "",
    desc: str = "",
) -> Callable[[NodeFn], NodeFn]:
    """把函数登记为 spec 可引用的块，并附上中文名、说明与参数契约。"""

    def _wrap(fn: NodeFn) -> NodeFn:
        if name in NODE_REGISTRY:
            raise ValueError(f"块重复注册：{name}")
        NODE_REGISTRY[name] = fn
        NODE_PARAMS[name] = tuple(params)
        NODE_LABELS[name] = label or name
        first_doc_line = (fn.__doc__ or "").strip().splitlines()[0] if (fn.__doc__ or "").strip() else ""
        NODE_DESCS[name] = desc or first_doc_line
        return fn

    return _wrap


def registered_nodes() -> list[str]:
    return sorted(NODE_REGISTRY)


def block_label(name: str) -> str:
    """块的中文短名，例如 ``require_citation`` -> 引用校验。"""
    return NODE_LABELS.get(name, name)


def block_desc(name: str) -> str:
    """块的一句话说明。"""
    return NODE_DESCS.get(name, "")


def block_catalog() -> list[dict[str, Any]]:
    """块清单，供编辑器渲染下拉框与说明。"""
    return [
        {
            "fn": name,
            "label": block_label(name),
            "desc": block_desc(name),
            "params": [param.name for param in block_params(name)],
        }
        for name in registered_nodes()
    ]



def block_params(name: str) -> tuple[ParamSpec, ...]:
    return NODE_PARAMS.get(name, ())


# ---------------------------------------------------------------- 参数校验


def _type_error(fn_name: str, param: ParamSpec) -> str:
    label = f"{fn_name}.args.{param.name}"
    if param.type == "str":
        return f"{label} 必须是字符串"
    if param.type == "int":
        return f"{label} 必须是整数"
    if param.type == "float":
        return f"{label} 必须是数字"
    if param.type == "bool":
        return f"{label} 必须是布尔值"
    if param.type == "enum":
        choices = "、".join(param.choices or ())
        return f"{label} 必须是 {choices} 之一"
    if param.type == "tool_list":
        return f"{label} 必须是工具名列表"
    return f"{label} 必须是字符串列表"


def _check_value(fn_name: str, param: ParamSpec, value: Any) -> list[str]:
    name = param.name
    if param.type == "str":
        return [] if isinstance(value, str) else [_type_error(fn_name, param)]
    if param.type == "bool":
        return [] if isinstance(value, bool) else [_type_error(fn_name, param)]
    if param.type == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            return [_type_error(fn_name, param)]
        return _check_range(fn_name, param, value)
    if param.type == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return [_type_error(fn_name, param)]
        return _check_range(fn_name, param, value)
    if param.type == "enum":
        if value not in (param.choices or ()):
            return [_type_error(fn_name, param)]
        return []
    if param.type in {"str_list", "tool_list"}:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            return [_type_error(fn_name, param)]
        return []
    return []


def _check_range(fn_name: str, param: ParamSpec, value: float) -> list[str]:
    label = f"{fn_name}.args.{param.name}"
    if param.minimum is not None and value < param.minimum:
        return [f"{label} 不能小于 {param.minimum}"]
    if param.maximum is not None and value > param.maximum:
        return [f"{label} 不能大于 {param.maximum}"]
    return []


def validate_args(fn_name: str, args: dict[str, Any]) -> list[str]:
    """按块的参数契约校验 spec 里的 args；未声明契约的块不检查。"""
    params = NODE_PARAMS.get(fn_name)
    if params is None:
        return []
    declared = {param.name: param for param in params}
    errors: list[str] = []
    for key in args:
        if key not in declared:
            allowed = "、".join(sorted(declared)) or "（无）"
            errors.append(f"{fn_name} 不认识参数 {key}；可用参数：{allowed}")
    for param in params:
        if param.required and param.name not in args:
            errors.append(f"{fn_name}.args.{param.name} 是必填参数")
        elif param.name in args:
            errors.extend(_check_value(fn_name, param, args[param.name]))
    return errors


def validate_tool_refs(fn_name: str, args: dict[str, Any], tool_names: set[str]) -> list[str]:
    """``tool_list`` 类型的参数只能引用场景里真实存在的工具。"""
    errors: list[str] = []
    for param in block_params(fn_name):
        if param.type != "tool_list":
            continue
        for item in args.get(param.name) or []:
            if item not in tool_names:
                errors.append(f"{fn_name}.args.{param.name} 引用了不存在的工具：{item}")
    return errors


# ---------------------------------------------------------------- 通用工具


def _content(value: Any) -> str:
    """ToolMessage / AIMessage / 字符串统一取文本。"""
    content = getattr(value, "content", value)
    if isinstance(content, list):
        return "".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content or "")


def _merge_scratch(state: dict[str, Any], **values: Any) -> dict[str, Any]:
    scratch = dict(state.get("scratch") or {})
    scratch.update(values)
    return scratch


def _invoke_tool(scenario: Any, name: str, args: dict[str, Any]) -> str:
    tool = scenario.get_tool(name)
    result = tool.invoke({
        "name": name,
        "args": args,
        "id": f"spec-{name}",
        "type": "tool_call",
    })
    return _content(result)


# ---------------------------------------------------------------- 块


@register_node(
    "retrieve",
    label="检索",
    desc="调用一个检索类工具，把结果写进 tool_result",
    params=(
        ParamSpec("tool", "str", required=True, help="要调用的检索类工具名"),
        ParamSpec("limit", "int", default=5, minimum=1, maximum=20, help="返回条数"),
        ParamSpec("query_key", "str", default="input", help="从 state 的哪个键取问题"),
    ),
)
def retrieve(
    state: dict[str, Any],
    scenario: Any = None,
    tool: str = "",
    limit: int = 5,
    query_key: str = "input",
    **_,
) -> dict[str, Any]:
    """调用一个检索类工具，结果写进 ``tool_result``。"""
    query = str(state.get(query_key) or "").strip()
    if not tool:
        return {"tool_result": "", "scratch": _merge_scratch(state, error="retrieve 没有配置 tool")}
    if not query:
        return {"tool_result": "", "scratch": _merge_scratch(state, error="检索问题为空")}
    try:
        text = _invoke_tool(scenario, tool, {"query": query, "limit": limit})
    except Exception as exc:  # noqa: BLE001 - 节点失败要回注，不让整张图崩
        return {"tool_result": "", "scratch": _merge_scratch(state, error=f"工具 {tool} 失败：{exc}")}
    if not text.strip():
        return {"tool_result": "", "scratch": _merge_scratch(state, error="检索结果为空")}
    return {"tool_result": text, "scratch": _merge_scratch(state, error=None)}


@register_node(
    "llm_answer",
    label="生成回答",
    desc="用问题 + 检索材料生成回答，写进 answer",
    params=(
        ParamSpec("prompt", "str", default="", help="回答指令；留空用默认指令"),
    ),
)
def llm_answer(
    state: dict[str, Any],
    scenario: Any = None,
    prompt: str = "",
    **_,
) -> dict[str, Any]:
    """用问题 + 工具结果生成回答，写进 ``answer``。"""
    model = getattr(scenario, "model", None)
    if model is None:
        return {"answer": "", "scratch": _merge_scratch(state, error="场景没有可用模型")}
    question = str(state.get("input") or "").strip()
    material = str(state.get("tool_result") or "").strip()
    instruction = prompt or "根据材料回答问题，必须用 [来源id] 标注引用；材料不足就明确说无法确定。"
    messages = [
        ("system", getattr(scenario, "system_prompt", "") or "你是一个严谨的助手。"),
        ("human", f"{instruction}\n\n问题：{question}\n\n材料：\n{material}"),
    ]
    try:
        reply = model.invoke(messages)
    except Exception as exc:  # noqa: BLE001
        return {"answer": "", "scratch": _merge_scratch(state, error=f"模型调用失败：{exc}")}
    return {"answer": _content(reply).strip(), "scratch": _merge_scratch(state, error=None)}


@register_node(
    "require_citation",
    label="引用校验",
    desc="回答里没有 [来源id] 就在 scratch.error 里记一笔",
    params=(
        ParamSpec("pattern", "str", default=CITATION_PATTERN, help="引用正则，默认匹配 [id]"),
    ),
)
def require_citation(
    state: dict[str, Any],
    scenario: Any = None,
    pattern: str = CITATION_PATTERN,
    **_,
) -> dict[str, Any]:
    """回答里没有 ``[来源id]`` 就在 ``scratch.error`` 里记一笔。"""
    answer = str(state.get("answer") or "")
    if re.search(pattern, answer):
        return {"scratch": _merge_scratch(state, error=None)}
    return {"scratch": _merge_scratch(state, error="回答缺少 [来源] 引用")}


@register_node(
    "summarize",
    label="材料截断",
    desc="确定性截断材料，不调模型；为了可测、可复现，也不额外烧 token",
    params=(
        ParamSpec("max_chars", "int", default=1200, minimum=100, maximum=8000, help="截断长度"),
    ),
)
def summarize(
    state: dict[str, Any],
    scenario: Any = None,
    max_chars: int = 1200,
    **_,
) -> dict[str, Any]:
    """确定性截断，不调模型：为了可测、可复现，也为了不额外烧 token。"""
    text = str(state.get("tool_result") or "").strip()
    if len(text) <= max_chars:
        return {"tool_result": text}
    return {"tool_result": text[:max_chars] + "\n…（已截断）"}


@register_node(
    "write_report",
    label="写报告文件",
    desc="把 answer 写进 data/runtime/spec_reports，越界路径直接拒绝",
    params=(
        ParamSpec("path", "str", default="report.md", help="相对 data/runtime/spec_reports 的路径"),
    ),
)
def write_report(
    state: dict[str, Any],
    scenario: Any = None,
    path: str = "report.md",
    **_,
) -> dict[str, Any]:
    """把 ``answer`` 写进 ``data/runtime/spec_reports``，越界路径直接拒绝。"""
    root = REPORT_ROOT.resolve()
    target = (REPORT_ROOT / path).resolve()
    if target != root and root not in target.parents:
        return {"scratch": _merge_scratch(state, error=f"非法路径：{path}")}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(str(state.get("answer") or ""), encoding="utf-8")
    return {"scratch": _merge_scratch(state, written=str(target), error=None)}


@register_node(
    "react_loop",
    label="ReAct 循环",
    desc="复合块：内部是一个完整 ReAct 循环，对外只暴露参数",
    params=(
        ParamSpec("prompt", "str", default="", help="系统提示词；留空用场景提示词"),
        ParamSpec("tools", "tool_list", required=True, help="可用工具白名单"),
        ParamSpec("max_steps", "int", default=6, minimum=1, maximum=12, help="工具调用上限"),
        ParamSpec(
            "stop_when",
            "enum",
            default="no_tool_calls",
            choices=("no_tool_calls", "answer_has_citation"),
            help="结束条件",
        ),
    ),
)
def react_loop(
    state: dict[str, Any],
    scenario: Any = None,
    prompt: str = "",
    tools: list[str] | None = None,
    max_steps: int = 6,
    stop_when: str = "no_tool_calls",
    **_,
) -> dict[str, Any]:
    """复合块：内部是一个完整的 ReAct 循环（create_agent），对外只暴露参数。

    它是"原子块"——内部是 create_agent 而不是节点，所以不能展开成子图。
    想手拼循环，需要条件边 + 工具节点，那是另一层能力。
    """
    if scenario is None:
        return {"answer": "", "scratch": _merge_scratch(state, error="react_loop 缺少场景")}
    available = {tool.name: tool for tool in getattr(scenario, "tools", [])}
    requested = list(tools or [])
    if not requested:
        return {"answer": "", "scratch": _merge_scratch(state, error="react_loop 没有配置工具")}
    missing = [name for name in requested if name not in available]
    if missing:
        return {
            "answer": "",
            "scratch": _merge_scratch(state, error=f"react_loop 引用了不存在的工具：{', '.join(missing)}"),
        }
    try:
        from langchain.agents import create_agent
        from langchain.agents.middleware import ToolCallLimitMiddleware
    except ImportError as exc:  # pragma: no cover - 依赖缺失时才触发
        return {"answer": "", "scratch": _merge_scratch(state, error=f"依赖缺失：{exc}")}

    try:
        agent = create_agent(
            model=scenario.model,
            tools=[available[name] for name in requested],
            system_prompt=prompt or getattr(scenario, "system_prompt", "") or "你是一个严谨的助手。",
            middleware=[ToolCallLimitMiddleware(run_limit=max_steps, exit_behavior="end")],
        )
        result = agent.invoke({
            "messages": [{"role": "user", "content": str(state.get("input") or "")}]
        })
    except Exception as exc:  # noqa: BLE001
        return {"answer": "", "scratch": _merge_scratch(state, error=f"react_loop 执行失败：{exc}")}

    messages = result.get("messages") or []
    answer = _content(messages[-1]).strip() if messages else ""
    error = None
    if stop_when == "answer_has_citation" and not re.search(CITATION_PATTERN, answer):
        error = "回答缺少 [来源] 引用"
    return {"answer": answer, "scratch": _merge_scratch(state, error=error)}
