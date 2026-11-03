# -*- coding: utf-8 -*-
"""中间件流水线：声明式装配 + 顺序不变量。

装配逻辑从 ``framework.py`` 的 if 链搬到这里，解决三个问题：

1. **顺序不靠调用方拖拽**：每个策略有固定 slot，编译时统一排序；
2. **可增删可配参**：spec 场景用 ``policies`` 覆盖默认策略，不用改框架代码；
3. **不变量可校验**：违反"权限最外 / 审批在超时外 / error 在 retry 外"直接报错。

默认策略从 ``Scenario`` 的现有字段推导，所以代码场景的行为与重构前完全一致；
``policies`` 只是叠加在上面的覆盖层（默认开启、显式移除）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
from typing import Any, Callable

from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    ModelFallbackMiddleware,
    ModelRetryMiddleware,
    PIIMiddleware,
    SummarizationMiddleware,
    TodoListMiddleware,
    ToolCallLimitMiddleware,
    ToolErrorMiddleware,
    ToolRetryMiddleware,
)

from core.agent.hooks import make_hook_middleware
from core.agent.middleware import (
    PlanningPolicyMiddleware,
    TokenBudgetMiddleware,
    ToolPermissionMiddleware,
    ToolTimeoutMiddleware,
)

# slot 越小越靠外。同一个 slot 内保持声明顺序。
SLOTS: dict[str, int] = {
    "permission": 0,
    "custom": 10,
    "hooks": 20,
    "planning": 30,
    "todo": 40,
    "summarization": 50,
    "pii": 60,
    "hitl": 70,
    "timeout": 80,
    "error": 90,
    "retry": 100,
    "limit": 110,
    "budget": 120,
    "fallback": 130,
    "model_retry": 140,
}

# 只校验真正影响语义的顺序，其余只管默认值。
INVARIANTS: tuple[tuple[str, str, str], ...] = (
    ("permission", "hitl", "权限层必须在审批外层：被拒绝的工具不该进入审批"),
    ("permission", "timeout", "权限层必须在超时外层：被拒绝的工具不该执行"),
    ("hitl", "timeout", "审批必须在超时之外：人思考的时间不算工具耗时"),
    ("error", "retry", "error 必须在 retry 外层：重试耗尽后才转成 error ToolMessage"),
    ("planning", "todo", "policy 先决定是否委派，再进入常规 todo 流程"),
)


class PipelineError(ValueError):
    """策略配置不合法。"""

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__("；".join(self.errors))


@dataclass(frozen=True)
class PolicySpec:
    name: str
    enabled: bool = True
    args: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PolicySpec":
        return cls(
            name=str(data.get("name") or ""),
            enabled=bool(data.get("enabled", True)),
            args=dict(data.get("args") or {}),
            reason=data.get("reason"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "enabled": self.enabled, "args": self.args, "reason": self.reason}


@dataclass(frozen=True)
class Entry:
    name: str  # 展示名，如 permission / pii:email / custom:MonitorToolMiddleware
    policy: str  # 注册名，如 permission / pii / custom
    slot: int
    seq: int
    factory: Callable[[], Any]


def _on_tool_error(exc: Exception, request) -> str:
    """把工具执行异常转成中文 error ToolMessage，让 Agent 有机会换一种方式继续。"""
    tool_name = getattr(request, "tool_call", {}).get("name", "unknown")
    return (
        f"[工具执行异常] 工具 {tool_name} 执行失败（{type(exc).__name__}）。"
        "请不要重复同样的调用，检查参数或改用其他工具。"
    )


# ---------------------------------------------------------------- 策略构建器

_BUILDERS: dict[str, Callable[[Any, dict[str, Any]], Any]] = {}


def register_policy(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def _wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        if name in _BUILDERS:
            raise ValueError(f"策略重复注册：{name}")
        _BUILDERS[name] = fn
        return fn

    return _wrap


@register_policy("permission")
def _build_permission(scenario: Any, args: dict[str, Any]) -> Any:
    return ToolPermissionMiddleware(scenario.tool_policy)


@register_policy("hooks")
def _build_hooks(scenario: Any, args: dict[str, Any]) -> Any:
    return make_hook_middleware(args["manager"])


@register_policy("planning")
def _build_planning(scenario: Any, args: dict[str, Any]) -> Any:
    return PlanningPolicyMiddleware(scenario.planning_policy)


@register_policy("todo")
def _build_todo(scenario: Any, args: dict[str, Any]) -> Any:
    return TodoListMiddleware()


@register_policy("summarization")
def _build_summarization(scenario: Any, args: dict[str, Any]) -> Any:
    return SummarizationMiddleware(
        model=scenario.model,
        trigger=scenario.summarization_trigger,
        keep=scenario.summarization_keep,
    )


@register_policy("pii")
def _build_pii(scenario: Any, args: dict[str, Any]) -> Any:
    return PIIMiddleware(
        args["type"],
        strategy="redact",
        apply_to_input=True,
        apply_to_output=False,
        apply_to_tool_results=False,
    )


@register_policy("hitl")
def _build_hitl(scenario: Any, args: dict[str, Any]) -> Any:
    return HumanInTheLoopMiddleware(interrupt_on=scenario.high_risk_tools)


@register_policy("timeout")
def _build_timeout(scenario: Any, args: dict[str, Any]) -> Any:
    return ToolTimeoutMiddleware(
        default_timeout=scenario.tool_timeout_seconds,
        overrides=scenario.tool_timeouts,
    )


@register_policy("error")
def _build_error(scenario: Any, args: dict[str, Any]) -> Any:
    return ToolErrorMiddleware(on_error=_on_tool_error)


@register_policy("retry")
def _build_retry(scenario: Any, args: dict[str, Any]) -> Any:
    return ToolRetryMiddleware(max_retries=1, on_failure="error")


@register_policy("limit")
def _build_limit(scenario: Any, args: dict[str, Any]) -> Any:
    run_limit = args.get("run_limit") or scenario.tool_call_limit
    return ToolCallLimitMiddleware(run_limit=run_limit, exit_behavior="end")


@register_policy("budget")
def _build_budget(scenario: Any, args: dict[str, Any]) -> Any:
    return TokenBudgetMiddleware()


@register_policy("fallback")
def _build_fallback(scenario: Any, args: dict[str, Any]) -> Any:
    return ModelFallbackMiddleware(scenario.fallback_model)


@register_policy("model_retry")
def _build_model_retry(scenario: Any, args: dict[str, Any]) -> Any:
    return ModelRetryMiddleware(max_retries=1)


# ---------------------------------------------------------------- 装配


def available_policies() -> list[str]:
    return sorted(_BUILDERS)


def default_policies(scenario: Any, hook_manager: Any = None) -> list[PolicySpec]:
    """从 Scenario 字段推导默认策略，复刻重构前的装配顺序。"""
    specs: list[PolicySpec] = [PolicySpec("permission")]
    if scenario.planning_policy is not None:
        specs.append(PolicySpec("planning"))
    if scenario.enable_todo:
        specs.append(PolicySpec("todo"))
    if scenario.enable_summarization:
        specs.append(PolicySpec("summarization"))
    if scenario.pii_types:
        specs.append(PolicySpec("pii", args={"types": list(scenario.pii_types)}))
    if scenario.high_risk_tools:
        specs.append(PolicySpec("hitl"))
    specs.extend([PolicySpec("timeout"), PolicySpec("error"), PolicySpec("retry")])
    if scenario.tool_call_limit:
        specs.append(PolicySpec("limit", args={"run_limit": scenario.tool_call_limit}))
    if scenario.token_budget:
        specs.append(PolicySpec("budget"))
    if scenario.fallback_model is not None:
        specs.append(PolicySpec("fallback"))
    specs.append(PolicySpec("model_retry"))
    if hook_manager is not None and hook_manager.has_hooks():
        specs.append(PolicySpec("hooks", args={"manager": hook_manager}))
    return specs


def _merge(base: list[PolicySpec], overrides: list[Any] | None) -> list[PolicySpec]:
    merged = {spec.name: spec for spec in base}
    for raw in overrides or []:
        spec = raw if isinstance(raw, PolicySpec) else PolicySpec.from_dict(raw)
        if not spec.name:
            raise PipelineError(["policies 里有一项缺少 name"])
        if spec.name not in _BUILDERS:
            raise PipelineError([
                f"未知策略：{spec.name}（可用：{', '.join(available_policies())}）"
            ])
        current = merged.get(spec.name)
        merged[spec.name] = PolicySpec(
            name=spec.name,
            enabled=spec.enabled,
            args={**(current.args if current else {}), **spec.args},
            reason=spec.reason,
        )
    return list(merged.values())


def _validate_specs(specs: list[PolicySpec]) -> None:
    errors = [
        f"策略 {spec.name} 被关闭但没有写 reason：移除一层守卫必须可审计"
        for spec in specs
        if not spec.enabled and not (spec.reason or "").strip()
    ]
    if errors:
        raise PipelineError(errors)


def _entries(
    scenario: Any,
    hook_manager: Any = None,
    overrides: list[Any] | None = None,
) -> list[Entry]:
    specs = _merge(default_policies(scenario, hook_manager), overrides)
    _validate_specs(specs)

    entries: list[Entry] = []
    seq = 0
    for spec in specs:
        if not spec.enabled:
            continue
        if spec.name == "pii":
            for pii_type in spec.args.get("types") or ():
                entries.append(Entry(
                    name=f"pii:{pii_type}",
                    policy="pii",
                    slot=SLOTS["pii"],
                    seq=seq,
                    factory=partial(_BUILDERS["pii"], scenario, {"type": pii_type}),
                ))
                seq += 1
            continue
        entries.append(Entry(
            name=spec.name,
            policy=spec.name,
            slot=SLOTS[spec.name],
            seq=seq,
            factory=partial(_BUILDERS[spec.name], scenario, dict(spec.args)),
        ))
        seq += 1

    for middleware in getattr(scenario, "middleware", None) or []:
        entries.append(Entry(
            name=f"custom:{type(middleware).__name__}",
            policy="custom",
            slot=SLOTS["custom"],
            seq=seq,
            factory=partial(_keep, middleware),
        ))
        seq += 1

    entries.sort(key=lambda entry: (entry.slot, entry.seq))
    _validate_order(entries)
    return entries


def _keep(middleware: Any) -> Any:
    return middleware


def _validate_order(entries: list[Entry]) -> None:
    position: dict[str, int] = {}
    for index, entry in enumerate(entries):
        position.setdefault(entry.policy, index)
    errors: list[str] = []
    for outer, inner, why in INVARIANTS:
        if outer in position and inner in position and position[outer] > position[inner]:
            errors.append(f"策略顺序违反不变量：{outer} 必须在 {inner} 之前（{why}）")
    if errors:
        raise PipelineError(errors)


def build_pipeline(
    scenario: Any,
    hook_manager: Any = None,
    overrides: list[Any] | None = None,
) -> list[Any]:
    """编译出最终的中间件列表（由外到内）。"""
    return [entry.factory() for entry in _entries(scenario, hook_manager, overrides)]


def describe_pipeline(
    scenario: Any,
    hook_manager: Any = None,
    overrides: list[Any] | None = None,
) -> list[str]:
    """返回装配后的策略名（由外到内），用于测试、UI 与排查。"""
    return [entry.name for entry in _entries(scenario, hook_manager, overrides)]
