# -*- coding: utf-8 -*-
"""robot_vacuum 业务中间件：意图路由 + 提示词切换。

这些规则依赖具体业务（报告关键词、客服提示词），所以放在场景层，
不放进 agent/ 的通用中间件。
"""
from __future__ import annotations

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware, ModelRequest
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime

from utils.logger_handler import get_logger, logger
from utils.prompt_loader import load_report_prompts, load_system_prompts

intent_logger = get_logger("intent_router")


def _message_text(message) -> str:
    """从消息对象/字典中提取纯文本，兼容 content 为字符串或内容块列表。"""
    if isinstance(message, dict):
        content = message.get("content", "")
    else:
        content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "\n".join(parts)
    return str(content or "")


def _classify_intent(text: str, report_keywords: list[str]) -> tuple[str, str]:
    """规则关键词分类：命中报告类关键词 -> report，否则 -> qa。"""
    lowered = text.lower()
    for keyword in report_keywords:
        keyword = str(keyword).strip()
        if keyword and keyword.lower() in lowered:
            return "report", keyword
    return "qa", ""


def _route_intent(state: AgentState, runtime: Runtime, report_keywords: list[str]):
    """一次 run 开始时识别用户意图，并写入 runtime.context 供提示词切换使用。"""
    context = runtime.context
    if not isinstance(context, dict):
        logger.warning(
            f"[intent_router]runtime.context 不是字典（收到 {type(context).__name__}），无法写入意图标记；"
            "请给 stream/invoke 传入非空 context，例如 {'intent': None}"
        )
        return None
    if context.get("intent") is not None:
        return None

    messages = state.get("messages", [])
    question = ""
    for message in reversed(messages):
        is_human = isinstance(message, HumanMessage) or (
            isinstance(message, dict) and message.get("role") == "user"
        )
        if is_human:
            question = _message_text(message).strip()
            break

    intent, matched_keyword = _classify_intent(question, report_keywords)
    context["intent"] = intent
    context["intent_keyword"] = matched_keyword

    # 切换日志：时间 / 问题 / 意图 / 命中关键词，复盘 badcase 时直接检索该文件
    intent_logger.info(
        f"question={question!r} | intent={intent} | matched_keyword={matched_keyword!r}"
    )
    return None


class IntentRouterMiddleware(AgentMiddleware):
    tools = []
    name = "intent_router"

    def __init__(self, report_keywords: list[str] | None = None):
        self.report_keywords = report_keywords or []

    def before_agent(self, state: AgentState, runtime: Runtime):
        return _route_intent(state, runtime, self.report_keywords)

    async def abefore_agent(self, state: AgentState, runtime: Runtime):
        return _route_intent(state, runtime, self.report_keywords)


def _select_prompt(request: ModelRequest, prompts_path: str) -> str:
    """按意图路由的结果选择系统提示词。"""
    intent = request.runtime.context.get("intent", "qa") if isinstance(request.runtime.context, dict) else "qa"
    if intent == "report":
        return load_report_prompts(prompts_path)
    return load_system_prompts(prompts_path)


class ReportPromptSwitchMiddleware(AgentMiddleware):
    """按意图路由的结果，在每次模型调用前替换 system prompt。"""

    tools = []
    name = "report_prompt_switch"

    def __init__(self, prompts_path: str):
        self.prompts_path = prompts_path

    def _with_prompt(self, request: ModelRequest) -> ModelRequest:
        return request.override(
            system_message=SystemMessage(content=_select_prompt(request, self.prompts_path))
        )

    def wrap_model_call(self, request: ModelRequest, handler):
        return handler(self._with_prompt(request))

    async def awrap_model_call(self, request: ModelRequest, handler):
        return await handler(self._with_prompt(request))
