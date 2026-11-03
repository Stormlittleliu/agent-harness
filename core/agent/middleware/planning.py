# -*- coding: utf-8 -*-
"""Planning Policy：用确定性规则决定第一次模型调用前是否注入工具调用。

定位不是“自主 planner”，而是可测、可审计的 Harness 策略：
- 命中唯一规则：注入一条带 tool_calls 的 AIMessage，并 jump_to="tools"；
- 无命中 / 分数不足 / 平局：返回 None，交回模型自主决策（abstain）。

这样把“模型是否愿意委派”从 prompt 行为变成 Harness 决策，同时保留不委派的能力。
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime


@dataclass(frozen=True)
class PlanningRule:
    """一条委派/路由规则：命中关键词后调用指定工具。"""

    tool: str
    strong_keywords: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    priority: int = 0
    arg_name: str = "query"
    arg_prefix: str = ""
    max_arg_chars: int = 4000


@dataclass(frozen=True)
class PlanningPolicy:
    """一组规则 + 触发阈值；平局默认 abstain，避免误路由。"""

    rules: tuple[PlanningRule, ...]
    min_score: int = 1
    abstain_on_tie: bool = True


@dataclass(frozen=True)
class Plan:
    tool: str
    args: dict[str, Any]
    score: int
    reason: str


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def _score(query: str, rule: PlanningRule) -> tuple[int, list[str]]:
    q = _normalize(query)
    hits: list[str] = []
    score = 0
    for keyword in rule.strong_keywords:
        key = _normalize(keyword)
        if key and key in q:
            score += 3
            hits.append(keyword)
    for keyword in rule.keywords:
        key = _normalize(keyword)
        if key and key in q:
            score += 1
            hits.append(keyword)
    return score, hits


def classify_intent(query: str, policy: PlanningPolicy) -> Plan | None:
    """按规则打分；最高分唯一（或优先级唯一）才返回 Plan，否则 abstain。"""
    scored = []
    for rule in policy.rules:
        score, hits = _score(query, rule)
        if score >= policy.min_score:
            scored.append((score, rule.priority, rule, hits))
    if not scored:
        return None

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best_score = scored[0][0]
    same_score = [item for item in scored if item[0] == best_score]
    top_priority = max(item[1] for item in same_score)
    top = [item for item in same_score if item[1] == top_priority]

    if policy.abstain_on_tie and len(top) > 1:
        return None

    score, _priority, rule, hits = top[0]
    arg = (rule.arg_prefix + str(query))[: rule.max_arg_chars]
    return Plan(
        tool=rule.tool,
        args={rule.arg_name: arg},
        score=score,
        reason=f"{rule.tool} 命中关键词 {hits}（score={score}）",
    )


class PlanningPolicyMiddleware(AgentMiddleware):
    """第一次模型调用前注入一次工具调用；不命中就交回模型。"""

    name = "planning_policy"
    tools = []

    def __init__(self, policy: PlanningPolicy):
        self.policy = policy

    @staticmethod
    def _first_turn(state: AgentState) -> bool:
        return not any(isinstance(message, AIMessage) for message in state.get("messages", []))

    @staticmethod
    def _last_user_text(state: AgentState) -> str:
        for message in reversed(state.get("messages", [])):
            content = getattr(message, "content", "")
            if isinstance(content, str) and content.strip():
                return content
        return ""

    def _plan(self, state: AgentState) -> dict | None:
        if not self._first_turn(state):
            return None
        plan = classify_intent(self._last_user_text(state), self.policy)
        if plan is None:
            return None
        tool_call = {
            "name": plan.tool,
            "args": plan.args,
            "id": f"policy-{uuid.uuid4().hex}",
            "type": "tool_call",
        }
        return {
            "jump_to": "tools",
            "messages": [AIMessage(content="", tool_calls=[tool_call])],
        }

    def before_model(self, state: AgentState, runtime: Runtime):
        return self._plan(state)

    async def abefore_model(self, state: AgentState, runtime: Runtime):
        return self._plan(state)


# Agent 工厂从钩子方法上读取可跳转目标；同步/异步都要标记。
PlanningPolicyMiddleware.before_model.__can_jump_to__ = ["tools"]
PlanningPolicyMiddleware.abefore_model.__can_jump_to__ = ["tools"]
