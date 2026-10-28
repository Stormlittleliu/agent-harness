# -*- coding: utf-8 -*-
"""Token 预算中间件：每次模型调用前检查本 run 的累计 token。"""
from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from core.observability.budget import RunBudget
from core.utils.logger_handler import logger


def _budget_exceeded(state: AgentState, runtime: Runtime):
    context = runtime.context
    budget = context.get("_run_budget") if isinstance(context, dict) else None
    if not isinstance(budget, RunBudget) or not budget.exceeded:
        return None

    logger.warning(
        f"[token_budget]本次 run 已用 {budget.total_tokens} tokens，"
        f"超过预算 {budget.max_tokens}，结束"
    )
    return {
        "jump_to": "end",
        "messages": [
            AIMessage(
                content=(
                    f"抱歉，本次运行的 token 预算已用尽（已用 {budget.total_tokens} / "
                    f"上限 {budget.max_tokens}），我先停止，避免继续产生费用。"
                    "请缩小问题范围，或提高 token_budget 后重试。"
                )
            )
        ],
    }


class TokenBudgetMiddleware(AgentMiddleware):
    tools = []
    name = "token_budget"

    def before_model(self, state: AgentState, runtime: Runtime):
        return _budget_exceeded(state, runtime)

    async def abefore_model(self, state: AgentState, runtime: Runtime):
        return _budget_exceeded(state, runtime)


TokenBudgetMiddleware.before_model.__can_jump_to__ = ["end"]
TokenBudgetMiddleware.abefore_model.__can_jump_to__ = ["end"]
