# -*- coding: utf-8 -*-
"""Planning Policy 的离线测试：分类、abstain、首次注入。"""
from langchain_core.messages import AIMessage, HumanMessage

from core.agent.middleware.planning import (
    PlanningPolicy,
    PlanningPolicyMiddleware,
    PlanningRule,
    classify_intent,
)
from core.scenarios.router.scenario import ROUTER_POLICY


def _state(text: str):
    return {"messages": [HumanMessage(content=text)]}


def test_router_scenario_wires_planning_policy():
    from core.scenarios.registry import get_scenario

    assert get_scenario("router").planning_policy is ROUTER_POLICY


def test_router_policy_classifies_four_intents():
    cases = {
        "根据笔记帮我整理一份 Agent 评测的学习计划": "route_to_workspace",
        "帮我写一个输出 99 乘法表的 Python 脚本并运行验证": "route_to_coding",
        "扫地机器人回充失败怎么办": "route_to_robot",
        "对比三份资料，告诉我它们对 Agent 评测的主要差异": "route_to_research",
    }
    for query, tool in cases.items():
        plan = classify_intent(query, ROUTER_POLICY)
        assert plan is not None, query
        assert plan.tool == tool, (query, plan)


def test_strong_keyword_beats_weak_keyword():
    # “笔记”是 workspace 强关键词，“对比”只是 research 弱关键词。
    plan = classify_intent("对比我笔记里的两种评测方法", ROUTER_POLICY)
    assert plan is not None
    assert plan.tool == "route_to_workspace"


def test_tie_abstains_by_default():
    policy = PlanningPolicy(
        rules=(
            PlanningRule(tool="a", strong_keywords=("x",)),
            PlanningRule(tool="b", strong_keywords=("x",)),
        ),
        min_score=1,
        abstain_on_tie=True,
    )
    assert classify_intent("x", policy) is None


def test_priority_breaks_tie_when_configured():
    policy = PlanningPolicy(
        rules=(
            PlanningRule(tool="a", strong_keywords=("x",), priority=1),
            PlanningRule(tool="b", strong_keywords=("x",), priority=2),
        ),
        min_score=1,
        abstain_on_tie=True,
    )
    plan = classify_intent("x", policy)
    assert plan is not None and plan.tool == "b"


def test_middleware_injects_tool_call_on_first_turn():
    middleware = PlanningPolicyMiddleware(ROUTER_POLICY)
    update = middleware.before_model(_state("扫地机器人回充失败怎么办"), None)
    assert update is not None
    assert update["jump_to"] == "tools"
    message = update["messages"][0]
    assert isinstance(message, AIMessage)
    assert message.tool_calls[0]["name"] == "route_to_robot"
    assert message.tool_calls[0]["args"]["query"] == "扫地机器人回充失败怎么办"


def test_middleware_abstains_when_no_rule():
    middleware = PlanningPolicyMiddleware(ROUTER_POLICY)
    assert middleware.before_model(_state("今天天气怎么样"), None) is None


def test_middleware_does_not_reinject_after_ai_message():
    middleware = PlanningPolicyMiddleware(ROUTER_POLICY)
    state = {
        "messages": [
            HumanMessage(content="扫地机器人回充失败怎么办"),
            AIMessage(content="", tool_calls=[{
                "name": "route_to_robot",
                "args": {"query": "扫地机器人回充失败怎么办"},
                "id": "call-1",
                "type": "tool_call",
            }]),
        ]
    }
    assert middleware.before_model(state, None) is None
