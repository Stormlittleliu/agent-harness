# -*- coding: utf-8 -*-
"""把 BFCL 的函数 schema 变成 LangChain 工具，跑我们的 FrameworkAgent。"""
from __future__ import annotations

import json
from typing import Any, Optional

from langchain.agents.middleware import wrap_tool_call
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import Field, create_model

from core.agent.contracts import Scenario
from core.agent.framework import FrameworkAgent
from core.llm.factory import chat_model
from core.quality.bfcl_simplified import arg_matches, eval_simple, normalize_schema, safe_tool_name


@wrap_tool_call
def validate_required_args(request, handler):
    """工具执行前检查必填参数；缺参数时回注错误，让模型重试。"""
    tool = request.tool
    schema = getattr(tool, "args_schema", None) if tool is not None else None
    if schema is None:
        return handler(request)
    try:
        json_schema = schema.model_json_schema()
    except Exception:
        return handler(request)

    required = json_schema.get("required") or []
    args = request.tool_call.get("args") or {}
    missing = [name for name in required if name not in args or args[name] in (None, "")]
    if not missing:
        return handler(request)
    return ToolMessage(
        content=f"缺少必填参数：{', '.join(missing)}。请补齐后重新调用工具。",
        tool_call_id=request.tool_call.get("id", ""),
        name=request.tool_call.get("name", ""),
        status="error",
    )


@wrap_tool_call
def suppress_repeat_tool_calls(request, handler):
    """同一个 run 内同一工具只执行一次；重复调用回注提示，避免 extra_call。"""
    state = request.state
    messages = state.get("messages", []) if isinstance(state, dict) else []
    current = request.tool_call or {}
    current_id = current.get("id")
    name = current.get("name")
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            if call.get("id") == current_id:
                continue
            if call.get("name") == name:
                return ToolMessage(
                    content=f"工具 {name} 已经调用过，请直接使用上一次结果，不要重复调用。",
                    tool_call_id=current_id or "",
                    name=name or "",
                    status="error",
                )
    return handler(request)


def _py_type(schema: dict):
    schema_type = schema.get("type")
    return {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }.get(schema_type, Any)


def _build_args_model(name: str, schema: dict):
    schema = normalize_schema(schema or {"type": "object", "properties": {}})
    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    fields = {}
    for param, prop in properties.items():
        if not isinstance(prop, dict):
            prop = {}
        py_type = _py_type(prop)
        if param in required:
            fields[param] = (py_type, Field(..., description=prop.get("description", "")))
        else:
            fields[param] = (Optional[py_type], Field(None, description=prop.get("description", "")))
    return create_model(f"{name}_args", **fields)


def build_tools(functions):
    tools = []
    name_map = {}
    used = set()
    for function in functions or []:
        original = function.get("name", "")
        safe = safe_tool_name(original)
        base = safe
        suffix = 2
        while safe in used:
            safe = f"{base}_{suffix}"
            suffix += 1
        used.add(safe)
        name_map[safe] = original
        try:
            args_model = _build_args_model(safe, function.get("parameters") or {})
        except Exception as exc:  # noqa: BLE001
            return [], {}, f"{original}: {type(exc).__name__}: {exc}"

        def _stub(_original=original, **kwargs):
            return json.dumps({"ok": True, "tool": _original, "args": kwargs}, ensure_ascii=False)

        tools.append(StructuredTool.from_function(
            func=_stub,
            name=safe,
            description=function.get("description", ""),
            args_schema=args_model,
        ))
    return tools, name_map, None


def _expr_normalize(value) -> str:
    """数学表达式的等价归一：2*x**2 与 2x**2 视为同一写法；不把 ^ 当成 **。"""
    text = str(value).replace(" ", "").lower()
    return text.replace("*", "")


def _score_case(case, calls):
    """BFCL 简化评分 + 可选参数容忍。

    官方 ground truth 用 "" / 0 / None 表示可选参数可省略；
    模型如果补了一个合法值，严格 equal 会判错。这里对“非 required 且
    ground truth 允许为空”的参数放宽，避免把评分口径当成模型错误。
    """
    expected_calls = case.get("expected_calls") or []
    if not expected_calls:
        return {"name_ok": False, "args_ok": False, "exact": False,
                "expected_name": None, "expected_args": {}}
    expected = expected_calls[0]
    expected_name = next(iter(expected))
    expected_args = expected[expected_name]
    name_ok = len(calls) == 1 and calls[0].get("name") == expected_name
    args_ok = False
    if name_ok:
        function = next(
            (item for item in case.get("functions", []) if item.get("name") == expected_name),
            {},
        )
        required = set((function.get("parameters") or {}).get("required") or [])
        actual_args = calls[0].get("args") or {}

        def arg_ok(key, candidates):
            candidates = candidates if isinstance(candidates, list) else [candidates]
            if key in actual_args:
                if arg_matches(actual_args[key], candidates):
                    return True
                actual_expr = _expr_normalize(actual_args[key])
                if any(actual_expr == _expr_normalize(candidate) for candidate in candidates):
                    return True
                if key not in required and any(candidate in ("", 0, None) for candidate in candidates):
                    return True
                return False
            return arg_matches(None, candidates)

        args_ok = all(arg_ok(key, candidates) for key, candidates in expected_args.items())
    return {
        "name_ok": name_ok,
        "args_ok": args_ok,
        "exact": name_ok and args_ok,
        "expected_name": expected_name,
        "expected_args": expected_args,
    }


def _tool_calls(messages, name_map):
    # 被中间件拒绝的调用（status=error）不算真正执行，避免 duplicate/缺参重试污染评分
    rejected = {
        getattr(message, "tool_call_id", None)
        for message in messages
        if isinstance(message, ToolMessage) and getattr(message, "status", "") == "error"
    }
    calls = []
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            call_id = call.get("id") if isinstance(call, dict) else getattr(call, "id", None)
            if call_id in rejected:
                continue
            name = call.get("name", "") if isinstance(call, dict) else getattr(call, "name", "")
            args = call.get("args", {}) if isinstance(call, dict) else getattr(call, "args", {})
            calls.append({"name": name_map.get(name, name), "args": args})
    return calls


def _answer_text(messages):
    for message in reversed(messages):
        if getattr(message, "type", "") == "ai":
            content = getattr(message, "content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return ""


def run_case(
    case,
    system_prompt: str,
    max_tool_calls: int = 4,
    validate_args: bool = False,
    suppress_repeats: bool = False,
) -> dict:
    tools, name_map, error = build_tools(case["functions"])
    if error:
        return {
            "id": case["id"], "kind": case["kind"], "passed": False,
            "failure_type": "setup_error", "error": error, "calls": [], "answer": "",
            "trace_id": None,
        }

    scenario = Scenario(
        name="bfcl_demo",
        description="BFCL tool-calling demo",
        model=chat_model,
        system_prompt=system_prompt,
        tools=tools,
        middleware=(
            ([suppress_repeat_tool_calls] if suppress_repeats else [])
            + ([validate_required_args] if validate_args else [])
        ),
        context={},
        cases_path=None,
        enable_todo=False,
        enable_summarization=False,
        tool_call_limit=max_tool_calls,
        token_budget=20000,
        pii_types=[],
        checkpoint=False,
        tool_policy={"default": "allow"},
    )
    agent = FrameworkAgent(scenario)
    state = agent.invoke(case["question"])
    calls = _tool_calls(state["messages"], name_map)

    if case["kind"] == "irrelevance":
        passed = not calls
        failure_type = None if passed else "unnecessary_call"
        return {
            "id": case["id"], "kind": case["kind"], "passed": passed,
            "failure_type": failure_type, "calls": calls,
            "answer": _answer_text(state["messages"]),
            "trace_id": agent.last_trace_id,
        }

    score = _score_case(case, calls)
    strict = eval_simple(case, case["expected_calls"], calls)
    if not calls:
        failure_type = "no_call"
    elif len(calls) > 1:
        failure_type = "extra_call"
    elif not score["name_ok"]:
        failure_type = "wrong_name"
    elif not score["args_ok"]:
        failure_type = "wrong_args"
    else:
        failure_type = None
    return {
        "id": case["id"], "kind": case["kind"], "passed": bool(score["exact"]),
        "failure_type": failure_type, "calls": calls,
        "expected_name": score.get("expected_name"),
        "expected_args": score.get("expected_args"),
        "strict_exact": bool(strict["exact"]),
        "optional_arg_override": bool(score["exact"] and not strict["exact"]),
        "answer": _answer_text(state["messages"]),
        "trace_id": agent.last_trace_id,
    }
