# -*- coding: utf-8 -*-
"""总路由场景：一个对话式前台 Agent，把请求分流到不同场景。

路由表在 ``data/routes/router.json``：工具、确定性规则、系统提示词都从那里生成，
所以"加一个可路由子场景"不用改这个文件。
"""
from pathlib import Path

from core.agent.contracts import Scenario
from core.agent.middleware import log_before_model, monitor_tool
from core.llm.factory import chat_model
from core.scenarios.router import routes as route_table
from core.scenarios.router.tools import build_route_tools

CASES_PATH = Path(__file__).with_name("cases.jsonl")


def build_scenario() -> Scenario:
    table = route_table.load_routes("router")
    return Scenario(
        name="router",
        description="总路由：从对话式前台分流到各子场景",
        kind="router",
        model=chat_model,
        system_prompt=route_table.build_system_prompt(table),
        tools=build_route_tools(table),
        middleware=[monitor_tool, log_before_model],
        context={},
        cases_path=CASES_PATH,
        enable_todo=False,
        enable_summarization=True,
        summarization_trigger=("messages", 30),
        summarization_keep=("messages", 12),
        tool_call_limit=4,
        token_budget=40000,
        checkpoint=True,
        checkpoint_backend="sqlite",
        checkpoint_path="data/runtime/router_checkpoints.sqlite",
        tool_policy={
            "default": "allow",
            "risk_levels": route_table.risk_levels(table),
        },
        tool_timeout_seconds=180,
        tool_timeouts=route_table.timeouts(table),
        planning_policy=route_table.build_policy(table),
    )
