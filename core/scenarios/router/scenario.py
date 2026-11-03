# -*- coding: utf-8 -*-
"""总路由场景：一个对话式前台 Agent，把请求分流到不同场景。"""
from pathlib import Path

from core.agent.contracts import Scenario
from core.agent.middleware import PlanningPolicy, PlanningRule, log_before_model, monitor_tool
from core.llm.factory import chat_model
from core.scenarios.router.tools import build_route_tools

CASES_PATH = Path(__file__).with_name("cases.jsonl")

# 确定性路由：命中唯一意图时直接注入 route_to_*；平局/无命中 abstain 交回模型。
ROUTER_POLICY = PlanningPolicy(
    rules=(
        PlanningRule(
            tool="route_to_robot",
            strong_keywords=("扫地", "扫拖", "回充", "吸力", "滤网", "基站", "固件", "机器人"),
            keywords=("清洁", "设备", "故障"),
        ),
        PlanningRule(
            tool="route_to_coding",
            strong_keywords=("脚本", "代码", "编程", "python", "乘法表", "报错", "调试"),
            keywords=("运行", "测试", "修复", "文件读写"),
        ),
        PlanningRule(
            tool="route_to_research",
            strong_keywords=("资料", "文献", "调研", "综述", "多源"),
            keywords=("对比", "研究", "来源", "差异"),
        ),
        PlanningRule(
            tool="route_to_workspace",
            strong_keywords=("笔记", "翻译", "办公", "学习", "内容", "记住", "偏好", "待办"),
            keywords=("总结", "摘要", "跨语言", "信息管理"),
        ),
    ),
    min_score=1,
    abstain_on_tie=True,
)


def build_scenario() -> Scenario:
    return Scenario(
        name="router",
        description="总路由：从对话式前台分流到 workspace / coding / robot / research 场景",
        model=chat_model,
        system_prompt=(
            "你是总路由 / 前台，不直接处理专业任务。\n"
            "先判断用户意图，调用对应的 route_to_* 工具：\n"
            "- 办公/学习/内容/信息管理/跨语言 -> route_to_workspace\n"
            "- 编码/文件/测试/修复代码 -> route_to_coding\n"
            "- 扫地/扫拖机器人设备与使用问题 -> route_to_robot\n"
            "- 多资料对比/研究调研 -> route_to_research\n"
            "调用后，把目标场景的最终答案用用户的语言返回，并说明“已路由到哪个场景”。"
            "不要编造目标场景没有给出的内容；如果目标场景返回错误，如实说明。"
        ),
        tools=build_route_tools(),
        middleware=[monitor_tool, log_before_model],
        context={},
        cases_path=CASES_PATH,
        high_risk_tools={},
        fallback_model=None,
        enable_todo=False,
        enable_summarization=True,
        summarization_trigger=("messages", 30),
        summarization_keep=("messages", 12),
        tool_call_limit=4,
        token_budget=40000,
        pii_types=[],
        checkpoint=True,
        checkpoint_backend="sqlite",
        checkpoint_path="data/runtime/router_checkpoints.sqlite",
        tool_policy={
            "default": "allow",
            "risk_levels": {
                "route_to_workspace": "low",
                "route_to_coding": "medium",
                "route_to_robot": "medium",
                "route_to_research": "medium",
            },
        },
        tool_timeout_seconds=180,
        tool_timeouts={
            "route_to_workspace": 120,
            "route_to_coding": 180,
            "route_to_robot": 180,
            "route_to_research": 240,
        },
        workflow_factory=None,
        planning_policy=ROUTER_POLICY,
    )
