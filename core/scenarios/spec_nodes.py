# -*- coding: utf-8 -*-
"""spec 场景可用的块库（受约束的伪低代码）。

约束（这是"伪"的来源，别绕开）：

- 节点只有一个通用 state：``input / tool_result / answer / scratch``；
- 节点只能引用这里注册过的块，spec 里不允许内联代码；
- 每个块用 ``ParamSpec`` 声明自己能接什么参数，编辑器据此渲染表单、编译器据此校验；
- 每个块用 ``PortSpec`` 声明自己读/写哪些 state 槽位（输入/输出端口），
  编译器据此做数据流校验；参数层（params）和端口层（ports）是两件事；
- 节点失败时把原因写进 ``scratch.error``，不抛异常打断整张图。

节点签名统一为 ``fn(state, scenario=None, **args) -> dict``，
编译时用 ``functools.partial`` 绑定 scenario 和 args。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

REPORT_ROOT = Path("data/runtime/spec_reports")
CITATION_PATTERN = r"\[[^\]]+\]"

NodeFn = Callable[..., dict[str, Any]]
NODE_REGISTRY: dict[str, NodeFn] = {}
NODE_PARAMS: dict[str, tuple["ParamSpec", ...]] = {}
NODE_INPUTS: dict[str, tuple["PortSpec", ...]] = {}
NODE_OUTPUTS: dict[str, tuple["PortSpec", ...]] = {}
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


# 端口类型只描述"这个 state 槽位里装的是哪类值"。它比 Python 类型粗，
# 因为节点之间传的是文本、JSON 这类业务语义，不是任意对象。
PORT_TYPES = frozenset({"text", "number", "boolean", "json", "any"})
TYPE_ALIASES = {
    "str": "text",
    "string": "text",
    "int": "number",
    "float": "number",
    "bool": "boolean",
    "dict": "json",
    "object": "json",
    "*": "any",
}


def _canonical_type(value: str) -> str:
    key = str(value or "").strip().lower()
    if key in PORT_TYPES:
        return key
    return TYPE_ALIASES.get(key, "")


@dataclass(frozen=True)
class PortSpec:
    """块的一个输入/输出端口：读或写 state 的哪个槽位、期望什么类型。

    ``params`` 回答"这个块能配什么"，``ports`` 回答"这个块吃/吐什么"。
    两者分开，是因为 ``save_to`` / ``queries_from`` 这类参数会让端口随配置变化。
    """

    name: str  # input / tool_result / answer / scratch.<key>
    type: str = "text"
    required: bool = False
    default: Any = None
    help: str = ""

    def __post_init__(self) -> None:
        canonical = _canonical_type(self.type)
        if not canonical:
            raise ValueError(f"未知端口类型：{self.type}")
        object.__setattr__(self, "type", canonical)


@dataclass(frozen=True)
class ResolvedPorts:
    """某个节点（块 + 实际参数）的具体端口。"""

    inputs: tuple[PortSpec, ...] = ()
    outputs: tuple[PortSpec, ...] = ()


def types_compatible(source_type: str, target_type: str) -> bool:
    """上游输出类型能否喂给下游输入类型。

    ``any`` 双向兼容；其余要求规范化后相同。类型不匹配返回 False，
    不抛异常——校验器要把"哪条边不兼容"当成可展示的错误。
    """
    source = _canonical_type(source_type)
    target = _canonical_type(target_type)
    if not source or not target:
        return False
    return source == "any" or target == "any" or source == target


def register_node(
    name: str,
    params: tuple[ParamSpec, ...] | list[ParamSpec] = (),
    *,
    inputs: tuple[PortSpec, ...] | list[PortSpec] = (),
    outputs: tuple[PortSpec, ...] | list[PortSpec] = (),
    label: str = "",
    desc: str = "",
) -> Callable[[NodeFn], NodeFn]:
    """把函数登记为 spec 可引用的块，并附上中文名、说明、参数与端口契约。"""

    def _wrap(fn: NodeFn) -> NodeFn:
        if name in NODE_REGISTRY:
            raise ValueError(f"块重复注册：{name}")
        NODE_REGISTRY[name] = fn
        NODE_PARAMS[name] = tuple(params)
        NODE_INPUTS[name] = tuple(inputs)
        NODE_OUTPUTS[name] = tuple(outputs)
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


def _port_dict(port: PortSpec) -> dict[str, Any]:
    return {
        "name": port.name,
        "type": port.type,
        "required": port.required,
        "default": port.default,
        "help": port.help,
    }


def block_catalog() -> list[dict[str, Any]]:
    """块清单，供编辑器渲染下拉框与说明。"""
    return [
        {
            "fn": name,
            "label": block_label(name),
            "desc": block_desc(name),
            "params": [param.name for param in block_params(name)],
            "inputs": [_port_dict(port) for port in block_inputs(name)],
            "outputs": [_port_dict(port) for port in block_outputs(name)],
        }
        for name in registered_nodes()
    ]


def block_params(name: str) -> tuple[ParamSpec, ...]:
    return NODE_PARAMS.get(name, ())


def block_inputs(name: str) -> tuple[PortSpec, ...]:
    """块的静态输入端口；随参数变化的端口由 ``block_ports`` 解析。"""
    return NODE_INPUTS.get(name, ())


def block_outputs(name: str) -> tuple[PortSpec, ...]:
    """块的静态输出端口；随参数变化的端口由 ``block_ports`` 解析。"""
    return NODE_OUTPUTS.get(name, ())


def _param_default(fn: str, name: str) -> Any:
    for param in block_params(fn):
        if param.name == name:
            return param.default
    return None


def _arg_or_default(fn: str, args: dict[str, Any], name: str, fallback: Any = None) -> Any:
    value = args.get(name)
    if value not in (None, ""):
        return value
    default = _param_default(fn, name)
    return fallback if default is None else default


def _is_save_target(name: str) -> bool:
    """``_save`` 只接受 answer / tool_result / scratch.<key>。"""
    text = str(name or "")
    return text in {"answer", "tool_result"} or (
        text.startswith("scratch.") and bool(text.split(".", 1)[1])
    )


def _is_state_slot(name: str) -> bool:
    """可以出现在端口上的 state 槽位（含只读的 input）。"""
    return str(name or "") == "input" or _is_save_target(name)


def _template_inputs(*texts: Any) -> list[PortSpec]:
    """从 ``{input}`` / ``{scratch.key}`` 占位符里提取输入端口。

    占位符缺失时 ``render_template`` 会替换成空串，所以这些端口是"可选"的：
    校验器不该因为模板里写了一个可空字段就报错。
    """
    found: list[PortSpec] = []
    seen: set[str] = set()
    for text in texts:
        for match in PLACEHOLDER.finditer(str(text or "")):
            key = match.group(1)
            if key in seen or not _is_state_slot(key):
                continue
            seen.add(key)
            found.append(PortSpec(key, "text", required=False, help="模板占位符"))
    return found


_SAVE_DEFAULTS = {
    "call_tool": "answer",
    "constant": "answer",
    "llm_text": "answer",
    "fan_out": "scratch.findings",
}


def block_ports(fn: str, args: dict[str, Any] | None = None) -> ResolvedPorts:
    """把块声明 + 实际参数解析成具体端口。

    动态端口来源：

    - ``save_to``（call_tool / constant / llm_text / fan_out）：写到哪个槽位；
    - ``queries_from``（fan_out）/ ``field``（branch）/ ``query_key``（retrieve）：
      从哪个槽位读；
    - 文本参数里的 ``{...}`` 占位符：模型生成 / 固定文本 / 工具参数实际读了什么。
    """
    args = dict(args or {})
    inputs = list(block_inputs(fn))
    outputs = list(block_outputs(fn))

    def add_input(port: PortSpec) -> None:
        if port.name and all(item.name != port.name for item in inputs):
            inputs.append(port)

    def add_output(port: PortSpec) -> None:
        if port.name and all(item.name != port.name for item in outputs):
            outputs.append(port)

    if fn in _SAVE_DEFAULTS:
        target = str(
            _arg_or_default(fn, args, "save_to", _SAVE_DEFAULTS[fn]) or _SAVE_DEFAULTS[fn]
        ).strip()
        if _is_save_target(target):
            add_output(PortSpec(target, "text", required=True, help="save_to 的目标槽位"))
        if fn == "call_tool" and target != "tool_result":
            add_output(
                PortSpec("tool_result", "text", required=False, help="工具带 docs 时的材料")
            )

    if fn == "fan_out":
        source = str(_arg_or_default(fn, args, "queries_from", "scratch.queries") or "")
        if _is_state_slot(source):
            add_input(PortSpec(source, "text", required=True, help="子问题列表"))

    if fn == "branch":
        field = str(_arg_or_default(fn, args, "field", "tool_result") or "")
        if _is_state_slot(field):
            add_input(PortSpec(field, "text", required=True, help="被检查的字段"))

    if fn == "retrieve":
        key = str(_arg_or_default(fn, args, "query_key", "input") or "")
        if _is_state_slot(key):
            add_input(PortSpec(key, "text", required=True, help="问题字段"))

    templates: dict[str, list[Any]] = {
        "call_tool": [args.get("args", "{}")],
        "llm_text": [args.get("prompt", "")],
        "constant": [args.get("text", "")],
        "fan_out": [args.get("template", "")],
    }
    for port in _template_inputs(*templates.get(fn, [])):
        add_input(port)

    return ResolvedPorts(tuple(inputs), tuple(outputs))


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


# ---------------------------------------------------------------- 参数插值
#
# 节点之间靠 state 传值。让 spec 里能写 "{input}" / "{scratch.user_id}"，就不用为
# 每个"第 N 步要带出第 N-1 步结果"的场景各写一个块。

PLACEHOLDER = re.compile(r"\{([a-zA-Z_][\w.]*)\}")


def _lookup(state: dict[str, Any], key: str) -> str:
    if key.startswith("scratch."):
        value = (state.get("scratch") or {}).get(key.split(".", 1)[1])
    else:
        value = state.get(key)
    return "" if value is None else str(value)


def render_template(text: Any, state: dict[str, Any]) -> str:
    """把 ``{key}`` / ``{scratch.key}`` 换成 state 里的值；未知 key 变空串。"""
    return PLACEHOLDER.sub(lambda match: _lookup(state, match.group(1)), str(text or ""))


def _save(result: dict[str, Any], state: dict[str, Any], save_to: str, text: str) -> dict[str, Any]:
    """按 ``save_to`` 把文本写回 state（answer / tool_result / scratch.<key>）。"""
    target = (save_to or "answer").strip()
    if target.startswith("scratch."):
        return {"scratch": _merge_scratch(state, **{target.split(".", 1)[1]: text})}
    if target in {"answer", "tool_result"}:
        return {target: text}
    return {"scratch": _merge_scratch(state, error=f"save_to 不合法：{save_to}")}


@register_node(
    "call_tool",
    label="调用工具",
    desc="按参数 JSON 调用一个工具，结果写回 answer / tool_result / scratch.<key>；返回值里带 docs 时会顺手存成材料",
    params=(
        ParamSpec("tool", "str", required=True, help="工具名，必须在场景工具白名单里"),
        ParamSpec(
            "args",
            "str",
            default="{}",
            help='参数 JSON；可用 {input} / {answer} / {tool_result} / {scratch.key} 插值',
        ),
        ParamSpec(
            "save_to",
            "str",
            default="answer",
            help="answer / tool_result / scratch.<key>",
        ),
    ),
)
def call_tool(
    state: dict[str, Any],
    scenario: Any = None,
    tool: str = "",
    args: str = "{}",
    save_to: str = "answer",
    **_,
) -> dict[str, Any]:
    """调一个工具，把结果按 ``save_to`` 写回。参数支持从 state 插值。"""
    if scenario is None:
        return {"scratch": _merge_scratch(state, error="call_tool 缺少场景")}
    try:
        payload = json.loads(render_template(args or "{}", state) or "{}")
    except json.JSONDecodeError as exc:
        return {"scratch": _merge_scratch(state, error=f"call_tool 参数不是合法 JSON：{exc}")}
    if not isinstance(payload, dict):
        return {"scratch": _merge_scratch(state, error="call_tool 参数必须是 JSON 对象")}
    try:
        result = scenario.get_tool(tool).invoke({
            "name": tool,
            "args": payload,
            "id": f"spec-{tool}",
            "type": "tool_call",
        })
    except Exception as exc:  # noqa: BLE001 - 节点失败回注，不打断整张图
        return {"scratch": _merge_scratch(state, error=f"工具 {tool} 失败：{exc}")}

    updates = _save({}, state, save_to, _content(result).strip())
    artifact = getattr(result, "artifact", None)
    docs = artifact.get("docs") if isinstance(artifact, dict) else None
    if docs and save_to != "tool_result":
        material = "\n\n".join(str(item.get("content", "")) for item in docs if isinstance(item, dict))
        if material.strip():
            updates["tool_result"] = material
    return updates


@register_node(
    "fan_out",
    label="并发子任务",
    desc="把一段「每行一个子问题」的文本拆开，并发交给 subagent，结果合并成材料",
    params=(
        ParamSpec("subagent", "str", default="subagent", help="子 Agent 工具名"),
        ParamSpec("queries_from", "str", default="scratch.queries", help="子问题列表所在的 state key，按行拆分"),
        ParamSpec("save_to", "str", default="scratch.findings", help="合并结果写回的 key"),
        ParamSpec(
            "template",
            "str",
            default="",
            help="每个子任务的指令模板，{query} 会替换成子问题；留空用默认指令",
        ),
        ParamSpec("max_workers", "int", default=3, minimum=1, maximum=8, help="并发数"),
    ),
)
def fan_out(
    state: dict[str, Any],
    scenario: Any = None,
    subagent: str = "subagent",
    queries_from: str = "scratch.queries",
    save_to: str = "scratch.findings",
    template: str = "",
    max_workers: int = 3,
    **_,
) -> dict[str, Any]:
    """并发跑 subagent：每个子问题一次，结果按"子问题 / 结论"拼接。"""
    from concurrent.futures import ThreadPoolExecutor

    if scenario is None:
        return {"scratch": _merge_scratch(state, error="fan_out 缺少场景")}
    raw = _lookup(state, queries_from)
    queries = [line.strip(" -•\t") for line in raw.splitlines() if line.strip(" -•\t")]
    if not queries:
        return {"scratch": _merge_scratch(state, error="fan_out 没有子问题")}
    try:
        tool = scenario.get_tool(subagent)
    except KeyError:
        return {"scratch": _merge_scratch(state, error=f"没有子 Agent 工具：{subagent}")}

    instruction = template or "阅读研究资料并回答这个子问题：{query}。只返回结论和引用的资料 id。"

    def _run(query: str) -> str:
        try:
            result = tool.invoke({
                "name": subagent,
                "args": {"description": instruction.replace("{query}", query)},
                "id": f"spec-fan-{abs(hash(query))}",
                "type": "tool_call",
            })
            return _content(result).strip()
        except Exception as exc:  # noqa: BLE001 - 单个子任务失败不影响整体
            return f"子 Agent 失败：{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=max(1, min(int(max_workers), len(queries)))) as pool:
        results = list(pool.map(_run, queries))
    findings = "\n\n".join(
        f"子问题：{query}\n结论：{answer}" for query, answer in zip(queries, results)
    )
    return _save({}, state, save_to, findings)


@register_node(
    "branch",
    label="分支判断",
    desc="看一个 state 字段（关键词命中 / 是否为空），把结果写进 scratch.route，配合条件边决定走哪条路",
    params=(
        ParamSpec(
            "mode",
            "enum",
            default="keywords",
            choices=("keywords", "empty"),
            help="keywords：命中任一关键词走 hit；empty：字段为空走 hit",
        ),
        ParamSpec("field", "str", default="tool_result", help="要检查的 state key（可用 scratch.xxx）"),
        ParamSpec("keywords", "str_list", default=None, help="keywords 模式的触发词"),
        ParamSpec("hit", "str", default="hit", help="命中时写入的 route 值（对应条件边标签）"),
        ParamSpec("miss", "str", default="miss", help="未命中时写入的 route 值"),
    ),
    outputs=(PortSpec("scratch.route", "text", required=True, help="条件边读取的路由值"),),
)
def branch(
    state: dict[str, Any],
    scenario: Any = None,
    mode: str = "keywords",
    field: str = "tool_result",
    keywords: list[str] | None = None,
    hit: str = "hit",
    miss: str = "miss",
    **_,
) -> dict[str, Any]:
    """把分支结果写进 ``scratch.route``；条件边靠它选路。"""
    value = _lookup(state, field)
    if mode == "empty":
        matched = not value.strip()
    else:
        words = [str(word) for word in (keywords or []) if str(word).strip()]
        matched = any(word in value for word in words)
    return {"scratch": _merge_scratch(state, route=hit if matched else miss)}


@register_node(
    "constant",
    label="固定文本",
    desc="把一段固定文本写回 state（拒答话术这类不需要模型的内容）",
    params=(
        ParamSpec("text", "str", required=True, help="要写入的文本"),
        ParamSpec("save_to", "str", default="answer", help="answer / tool_result / scratch.<key>"),
    ),
)
def constant(
    state: dict[str, Any],
    scenario: Any = None,
    text: str = "",
    save_to: str = "answer",
    **_,
) -> dict[str, Any]:
    """不调模型，直接写固定文本。"""
    return _save({}, state, save_to, render_template(text, state))


@register_node(
    "llm_text",
    label="模型生成",
    desc="把 prompt 渲染后交给模型，结果写回 answer / scratch.<key>（适合核查、报告这类固定话术）",
    params=(
        ParamSpec("prompt", "str", required=True, help="指令；可用 {input} / {answer} / {tool_result} / {scratch.key} 插值"),
        ParamSpec("save_to", "str", default="answer", help="answer / tool_result / scratch.<key>"),
    ),
)
def llm_text(
    state: dict[str, Any],
    scenario: Any = None,
    prompt: str = "",
    save_to: str = "answer",
    **_,
) -> dict[str, Any]:
    """渲染 prompt → 调模型 → 按 ``save_to`` 写回。"""
    model = getattr(scenario, "model", None)
    if model is None:
        return {"scratch": _merge_scratch(state, error="场景没有可用模型")}
    messages = [
        ("system", getattr(scenario, "system_prompt", "") or "你是一个严谨的助手。"),
        ("human", render_template(prompt, state)),
    ]
    try:
        reply = model.invoke(messages)
    except Exception as exc:  # noqa: BLE001
        return {"scratch": _merge_scratch(state, error=f"模型调用失败：{exc}")}
    return _save({}, state, save_to, _content(reply).strip())


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
    outputs=(PortSpec("tool_result", "text", required=True, help="检索材料"),),
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
    inputs=(
        PortSpec("input", "text", required=True, help="用户问题"),
        PortSpec("tool_result", "text", required=False, help="检索材料，可为空"),
    ),
    outputs=(PortSpec("answer", "text", required=True, help="最终回答"),),
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
    inputs=(PortSpec("answer", "text", required=True, help="待校验的回答"),),
    outputs=(PortSpec("scratch.error", "text", required=False, help="校验失败原因"),),
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
    inputs=(PortSpec("tool_result", "text", required=True, help="原始材料"),),
    outputs=(PortSpec("tool_result", "text", required=True, help="截断后的材料"),),
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
    inputs=(PortSpec("answer", "text", required=True, help="要落盘的正文"),),
    outputs=(PortSpec("scratch.written", "text", required=False, help="实际写入路径"),),
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
    inputs=(PortSpec("input", "text", required=True, help="用户问题"),),
    outputs=(PortSpec("answer", "text", required=True, help="循环结束时的回答"),),
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
