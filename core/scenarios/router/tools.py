# -*- coding: utf-8 -*-
"""总路由工具：调用目标场景的 FrameworkAgent，返回答案和目标 trace。"""
from __future__ import annotations

import json
import threading
import uuid

from langchain_core.tools import tool

from core.agent.framework import FrameworkAgent
from core.quality.agent_eval import extract_final_answer
from core.scenarios.registry import get_scenario

_AGENTS: dict[str, FrameworkAgent] = {}
_LOCK = threading.Lock()


def _agent(name: str) -> FrameworkAgent:
    with _LOCK:
        agent = _AGENTS.get(name)
        if agent is None:
            agent = FrameworkAgent(get_scenario(name))
            _AGENTS[name] = agent
        return agent


def _run_target(name: str, query: str) -> str:
    try:
        agent = _agent(name)
        state = agent.invoke(query, thread_id=f"route-{name}-{uuid.uuid4().hex}")
        answer = extract_final_answer(state.get("messages", []))
        return json.dumps(
            {
                "target": name,
                "answer": answer,
                "target_trace_id": agent.last_trace_id,
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as exc:  # noqa: BLE001 - 路由失败返回可读错误
        return json.dumps(
            {"target": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"},
            ensure_ascii=False,
        )


def build_route_tools():
    @tool(
        "route_to_workspace",
        description=(
            "把办公、学习、内容创作、信息管理、跨语言任务交给 workspace_assistant 场景。"
            "例如整理学习笔记、总结文档、翻译、保存笔记。"
        ),
    )
    def route_to_workspace(query: str) -> str:
        return _run_target("workspace_assistant", query)

    @tool(
        "route_to_coding",
        description=(
            "把编码、文件读写、运行测试、修复代码任务交给 coding_demo 场景。"
            "例如写一个 99 乘法表脚本并运行验证。"
        ),
    )
    def route_to_coding(query: str) -> str:
        return _run_target("coding_demo", query)

    @tool(
        "route_to_robot",
        description=(
            "把扫地/扫拖机器人设备使用、故障排查、使用报告交给 robot_vacuum 场景。"
            "例如回充失败、吸力选择、重置设备。"
        ),
    )
    def route_to_robot(query: str) -> str:
        return _run_target("robot_vacuum", query)

    @tool(
        "route_to_research",
        description=(
            "把多资料对比、研究调研、多源汇总任务交给 research_assistant 场景。"
            "例如对比三份资料的观点并给出来源。"
        ),
    )
    def route_to_research(query: str) -> str:
        return _run_target("research_assistant", query)

    return [route_to_workspace, route_to_coding, route_to_robot, route_to_research]
