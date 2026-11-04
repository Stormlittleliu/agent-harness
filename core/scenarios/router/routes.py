# -*- coding: utf-8 -*-
"""路由表：把"这一句该交给哪个场景"从代码里搬到数据里。

一份 ``data/routes/<name>.json`` 同时决定三件事：

1. 生成哪些 ``route_to_*`` 工具（工具名 / 描述 / 目标场景）；
2. 生成确定性路由规则（强关键词 + 弱关键词，命中唯一就注入工具调用）；
3. 生成路由场景的系统提示词（让模型知道有哪些下游）。

这样"加一个可路由子场景"= 在界面上加一行，不用改 Python。
路由表本身只认场景库里存在的目标，指向自己或不存在的一律拒绝（防递归）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.utils.path_tool import get_abs_path

ROUTES_DIR = Path(get_abs_path("data/routes"))
DEFAULT_TOOL_PREFIX = "route_to_"


class RouteError(ValueError):
    """路由表不合法。"""


def routes_path(name: str, root: Path | str = ROUTES_DIR) -> Path:
    return Path(root) / f"{name}.json"


def default_routes() -> list[dict[str, Any]]:
    """仓库自带的四条路由（第一次启动时写盘用）。"""
    return [
        {
            "target": "workspace_assistant",
            "tool": "route_to_workspace",
            "label": "办公 / 学习 / 内容",
            "description": "整理学习笔记、总结文档、翻译、保存笔记。",
            "strong": ["笔记", "翻译", "办公", "学习", "内容", "记住", "偏好", "待办"],
            "keywords": ["总结", "摘要", "跨语言", "信息管理"],
            "risk": "low",
            "timeout": 120,
        },
        {
            "target": "coding_demo",
            "tool": "route_to_coding",
            "label": "编码 / 文件 / 测试",
            "description": "写脚本、改代码、跑测试、修复报错。",
            "strong": ["脚本", "代码", "编程", "python", "乘法表", "报错", "调试"],
            "keywords": ["运行", "测试", "修复", "文件读写"],
            "risk": "medium",
            "timeout": 180,
        },
        {
            "target": "robot_vacuum",
            "tool": "route_to_robot",
            "label": "扫地机器人",
            "description": "设备使用、故障排查、使用报告。",
            "strong": ["扫地", "扫拖", "回充", "吸力", "滤网", "基站", "固件", "机器人"],
            "keywords": ["清洁", "设备", "故障"],
            "risk": "medium",
            "timeout": 180,
        },
        {
            "target": "research_assistant",
            "tool": "route_to_research",
            "label": "研究调研",
            "description": "多资料对比、多源汇总、研究综述。",
            "strong": ["资料", "文献", "调研", "综述", "多源"],
            "keywords": ["对比", "研究", "来源", "差异"],
            "risk": "medium",
            "timeout": 240,
        },
    ]


def load_routes(name: str = "router", root: Path | str = ROUTES_DIR) -> list[dict[str, Any]]:
    """读路由表；文件缺失就用默认表（不落盘，构建期只读）。"""
    path = routes_path(name, root)
    if not path.is_file():
        return default_routes()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RouteError(f"路由表读取失败：{path}：{exc}") from exc
    routes = data.get("routes") if isinstance(data, dict) else data
    if not isinstance(routes, list):
        raise RouteError(f"路由表格式错误（需要 routes 数组）：{path}")
    return [dict(item) for item in routes if isinstance(item, dict)]


def save_routes(
    routes: list[dict[str, Any]],
    name: str = "router",
    root: Path | str = ROUTES_DIR,
) -> Path:
    path = routes_path(name, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"routes": routes}, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    return path


def validate_routes(
    routes: list[dict[str, Any]],
    known_scenarios: list[str] | None = None,
    self_name: str = "router",
) -> list[str]:
    """校验路由表：目标必须存在且不是自己，工具名不能重复，关键词不能全空。"""
    errors: list[str] = []
    seen_tools: set[str] = set()
    for index, route in enumerate(routes, 1):
        target = str(route.get("target") or "").strip()
        tool_name = str(route.get("tool") or "").strip()
        if not target:
            errors.append(f"第 {index} 条路由缺少 target")
        elif target == self_name:
            errors.append(f"第 {index} 条路由指向自己（{self_name}），会递归")
        elif known_scenarios is not None and target not in known_scenarios:
            errors.append(f"第 {index} 条路由的目标场景不存在：{target}")
        if not tool_name:
            errors.append(f"第 {index} 条路由缺少 tool")
        elif tool_name in seen_tools:
            errors.append(f"工具名重复：{tool_name}")
        else:
            seen_tools.add(tool_name)
        strong = route.get("strong") or []
        keywords = route.get("keywords") or []
        if not strong and not keywords:
            errors.append(f"第 {index} 条路由没有任何触发词：{target or tool_name}")
    return errors


def build_route_tools(routes: list[dict[str, Any]] | None = None):
    """按路由表生成 ``route_to_*`` 工具；每个工具把请求转给目标场景的 Agent。"""
    from langchain_core.tools import tool

    from core.scenarios.router.tools import run_target

    items = list(routes) if routes is not None else load_routes()
    tools = []
    for route in items:
        target = str(route.get("target") or "").strip()
        tool_name = str(route.get("tool") or f"{DEFAULT_TOOL_PREFIX}{target}").strip()
        if not target or not tool_name:
            continue
        description = str(route.get("description") or "").strip()
        label = str(route.get("label") or target)
        text = f"把{label}相关任务交给 {target} 场景。{description}".strip()

        def _make(name: str, destination: str, desc: str):
            @tool(name, description=desc)
            def _route(query: str) -> str:
                return run_target(destination, query)

            return _route

        tools.append(_make(tool_name, target, text))
    return tools


def build_policy(routes: list[dict[str, Any]] | None = None, min_score: int = 1):
    """按路由表生成确定性路由规则（命中唯一意图就注入工具调用）。"""
    from core.agent.middleware import PlanningPolicy, PlanningRule

    items = list(routes) if routes is not None else load_routes()
    rules = []
    for route in items:
        target = str(route.get("target") or "").strip()
        tool_name = str(route.get("tool") or f"{DEFAULT_TOOL_PREFIX}{target}").strip()
        strong = tuple(str(item) for item in (route.get("strong") or []) if str(item).strip())
        keywords = tuple(str(item) for item in (route.get("keywords") or []) if str(item).strip())
        if not tool_name or (not strong and not keywords):
            continue
        rules.append(PlanningRule(tool=tool_name, strong_keywords=strong, keywords=keywords))
    return PlanningPolicy(rules=tuple(rules), min_score=min_score, abstain_on_tie=True)


def build_system_prompt(routes: list[dict[str, Any]] | None = None) -> str:
    """路由场景的提示词：下游列表从路由表生成，别写死在代码里。"""
    items = list(routes) if routes is not None else load_routes()
    lines = [
        "你是总路由 / 前台，不直接处理专业任务。",
        "先判断用户意图，调用对应的 route_to_* 工具：",
    ]
    for route in items:
        target = str(route.get("target") or "").strip()
        tool_name = str(route.get("tool") or f"{DEFAULT_TOOL_PREFIX}{target}").strip()
        label = str(route.get("label") or target)
        if target and tool_name:
            lines.append(f"- {label} -> {tool_name}")
    lines.append(
        "调用后，把目标场景的最终答案用用户的语言返回，并说明“已路由到哪个场景”。"
        "不要编造目标场景没有给出的内容；如果目标场景返回错误，如实说明。"
    )
    return "\n".join(lines)


def risk_levels(routes: list[dict[str, Any]] | None = None) -> dict[str, str]:
    items = list(routes) if routes is not None else load_routes()
    levels: dict[str, str] = {}
    for route in items:
        tool_name = str(route.get("tool") or "").strip()
        if tool_name:
            levels[tool_name] = str(route.get("risk") or "medium")
    return levels


def timeouts(routes: list[dict[str, Any]] | None = None) -> dict[str, float]:
    items = list(routes) if routes is not None else load_routes()
    result: dict[str, float] = {}
    for route in items:
        tool_name = str(route.get("tool") or "").strip()
        if tool_name and route.get("timeout"):
            result[tool_name] = float(route["timeout"])
    return result
