# -*- coding: utf-8 -*-
"""中间件流水线：等价性、覆盖、不变量。

基线来自重构前对 8 个场景 `FrameworkAgent.middleware` 的实测（2026-11-03）。
mcp_demo 会拉起外部 MCP server，不在单测里构建。
"""
from dataclasses import replace

import pytest

from core.agent.hooks import HookManager
from core.agent.pipeline import (
    Entry,
    PipelineError,
    _validate_order,
    available_policies,
    build_pipeline,
    default_policies,
    describe_pipeline,
)
from core.scenarios.registry import get_scenario

# 重构前的真实装配顺序（类名），用于等价性回归。
BASELINE = {
    "coding_demo": [
        "ToolPermissionMiddleware",
        "_hook_middleware",
        "TodoListMiddleware",
        "ToolTimeoutMiddleware",
        "ToolErrorMiddleware",
        "ToolRetryMiddleware",
        "ToolCallLimitMiddleware",
        "TokenBudgetMiddleware",
        "ModelRetryMiddleware",
    ],
    "flow_demo": [
        "ToolPermissionMiddleware",
        "SummarizationMiddleware",
        "ToolTimeoutMiddleware",
        "ToolErrorMiddleware",
        "ToolRetryMiddleware",
        "ToolCallLimitMiddleware",
        "TokenBudgetMiddleware",
        "ModelRetryMiddleware",
    ],
    "general": [
        "ToolPermissionMiddleware",
        "TodoListMiddleware",
        "SummarizationMiddleware",
        "ToolTimeoutMiddleware",
        "ToolErrorMiddleware",
        "ToolRetryMiddleware",
        "ToolCallLimitMiddleware",
        "TokenBudgetMiddleware",
        "ModelRetryMiddleware",
    ],
    "research_assistant": [
        "ToolPermissionMiddleware",
        "MonitorToolMiddleware",
        "LogBeforeModelMiddleware",
        "TodoListMiddleware",
        "SummarizationMiddleware",
        "ToolTimeoutMiddleware",
        "ToolErrorMiddleware",
        "ToolRetryMiddleware",
        "ToolCallLimitMiddleware",
        "TokenBudgetMiddleware",
        "ModelRetryMiddleware",
    ],
    "robot_vacuum": [
        "ToolPermissionMiddleware",
        "MonitorToolMiddleware",
        "ValidateToolArgsMiddleware",
        "IntentRouterMiddleware",
        "LogBeforeModelMiddleware",
        "LimitStepsMiddleware",
        "ReportPromptSwitchMiddleware",
        "TodoListMiddleware",
        "SummarizationMiddleware",
        "PIIMiddleware",
        "PIIMiddleware",
        "PIIMiddleware",
        "HumanInTheLoopMiddleware",
        "ToolTimeoutMiddleware",
        "ToolErrorMiddleware",
        "ToolRetryMiddleware",
        "ToolCallLimitMiddleware",
        "TokenBudgetMiddleware",
        "ModelRetryMiddleware",
    ],
    "router": [
        "ToolPermissionMiddleware",
        "MonitorToolMiddleware",
        "LogBeforeModelMiddleware",
        "PlanningPolicyMiddleware",
        "SummarizationMiddleware",
        "ToolTimeoutMiddleware",
        "ToolErrorMiddleware",
        "ToolRetryMiddleware",
        "ToolCallLimitMiddleware",
        "TokenBudgetMiddleware",
        "ModelRetryMiddleware",
    ],
    "structured_demo": [
        "ToolPermissionMiddleware",
        "ToolTimeoutMiddleware",
        "ToolErrorMiddleware",
        "ToolRetryMiddleware",
        "ToolCallLimitMiddleware",
        "TokenBudgetMiddleware",
        "ModelRetryMiddleware",
    ],
    "workspace_assistant": [
        "ToolPermissionMiddleware",
        "MonitorToolMiddleware",
        "LogBeforeModelMiddleware",
        "TodoListMiddleware",
        "SummarizationMiddleware",
        "PIIMiddleware",
        "PIIMiddleware",
        "PIIMiddleware",
        "ToolTimeoutMiddleware",
        "ToolErrorMiddleware",
        "ToolRetryMiddleware",
        "ToolCallLimitMiddleware",
        "TokenBudgetMiddleware",
        "ModelRetryMiddleware",
    ],
}


def _hook_manager(scenario):
    runtime = getattr(scenario, "runtime", None)
    return HookManager(getattr(runtime, "hooks", None))


def _pipeline_names(scenario, overrides=None):
    return [type(item).__name__ for item in build_pipeline(scenario, _hook_manager(scenario), overrides)]


@pytest.mark.parametrize("scenario_name", sorted(BASELINE))
def test_pipeline_is_equivalent_to_legacy_order(scenario_name):
    scenario = get_scenario(scenario_name)
    assert _pipeline_names(scenario) == BASELINE[scenario_name]


def test_framework_agent_uses_pipeline():
    from core.agent.framework import FrameworkAgent

    scenario = get_scenario("workspace_assistant")
    agent = FrameworkAgent(scenario)
    assert [type(item).__name__ for item in agent.middleware] == BASELINE["workspace_assistant"]


def test_default_policies_cover_every_scenario_field():
    scenario = get_scenario("robot_vacuum")
    names = [spec.name for spec in default_policies(scenario, _hook_manager(scenario))]
    for expected in ("permission", "todo", "summarization", "pii", "hitl", "timeout", "error", "retry"):
        assert expected in names


def test_describe_pipeline_lists_slot_order():
    scenario = get_scenario("robot_vacuum")
    names = describe_pipeline(scenario, _hook_manager(scenario))
    assert names[0] == "permission"
    assert names.index("hitl") < names.index("timeout") < names.index("retry")
    assert names.count("pii:email") == 1


def test_override_disables_policy_with_reason():
    scenario = get_scenario("workspace_assistant")
    overrides = [{"name": "retry", "enabled": False, "reason": "只读演示场景不需要重试"}]
    names = describe_pipeline(scenario, _hook_manager(scenario), overrides)
    assert "retry" not in names
    # 不变量里 error 必须在 retry 之前，retry 不在时不报错
    assert "error" in names


def test_disable_without_reason_is_rejected():
    scenario = get_scenario("workspace_assistant")
    with pytest.raises(PipelineError) as excinfo:
        build_pipeline(scenario, _hook_manager(scenario), [{"name": "retry", "enabled": False}])
    assert any("reason" in error for error in excinfo.value.errors)


def test_unknown_policy_is_rejected():
    scenario = get_scenario("workspace_assistant")
    with pytest.raises(PipelineError) as excinfo:
        build_pipeline(scenario, _hook_manager(scenario), [{"name": "telepathy"}])
    assert any("未知策略" in error for error in excinfo.value.errors)


def test_override_can_add_policy_not_in_defaults():
    scenario = replace(get_scenario("general"), token_budget=None)
    defaults = describe_pipeline(scenario, _hook_manager(scenario))
    assert "budget" not in defaults  # token_budget 清空后默认不含 budget
    names = describe_pipeline(scenario, _hook_manager(scenario), [{"name": "budget"}])
    assert "budget" in names


def test_override_can_set_limit_args():
    scenario = replace(get_scenario("general"), tool_call_limit=None)
    names = describe_pipeline(scenario, _hook_manager(scenario), [{"name": "limit", "args": {"run_limit": 3}}])
    assert "limit" in names


def test_custom_middleware_sits_right_after_permission():
    scenario = get_scenario("robot_vacuum")
    names = describe_pipeline(scenario, _hook_manager(scenario))
    assert names[0] == "permission"
    assert names[1].startswith("custom:")
    assert names.index("custom:ReportPromptSwitchMiddleware") < names.index("todo")


def test_invariants_are_enforced_on_entries():
    entries = [
        Entry("timeout", "timeout", 80, 0, lambda: None),
        Entry("permission", "permission", 0, 1, lambda: None),
    ]
    with pytest.raises(PipelineError) as excinfo:
        _validate_order(entries)
    assert any("不变量" in error for error in excinfo.value.errors)


def test_available_policies_exposes_builtins():
    assert {"permission", "hitl", "timeout", "error", "retry", "limit", "budget"} <= set(
        available_policies()
    )


def test_spec_policy_override_reaches_the_pipeline():
    from core.scenarios.spec import ScenarioSpec, build_from_spec

    class _Tool:
        name = "search_notes"

    spec = ScenarioSpec.model_validate({
        "schema_version": 1,
        "name": "policy_demo",
        "tools": ["search_notes"],
        "system_prompt": "你是测试助手。",
        "harness": {"enable_todo": True, "enable_summarization": True},
        "policies": [{"name": "summarization", "enabled": False, "reason": "单轮演示不需要压缩"}],
        "workflows": {
            "qa": {
                "nodes": [
                    {"id": "agent", "fn": "react_loop", "args": {"tools": ["search_notes"]}},
                ],
                "edges": [["__start__", "agent"], ["agent", "__end__"]],
            }
        },
    })
    scenario = build_from_spec(spec, tools=[_Tool()], model=object())

    names = [type(item).__name__ for item in build_pipeline(scenario, HookManager(None), scenario.policies)]
    assert "SummarizationMiddleware" not in names
    assert "TodoListMiddleware" in names
    assert "ToolPermissionMiddleware" in names
