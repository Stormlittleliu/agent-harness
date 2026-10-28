# -*- coding: utf-8 -*-
"""工具权限与超时中间件。

- ToolPermissionMiddleware：按场景配置（scenarios/<name>/config/agent.yml）的 tool_policy 做 allow / deny；
  高风险工具的审批由 HumanInTheLoopMiddleware 负责，这里只做“能不能调用”的硬拦截。
- ToolTimeoutMiddleware：单次工具执行超时，超时返回 error ToolMessage，
  让模型看到超时观察后改路，而不是整个 run 卡死。

中间件顺序（framework.py）：权限 → 业务中间件 → HITL → 超时 → 重试 → 工具。
wrap_tool_call 的第一个中间件在最外层，所以超时不会包住人工审批。
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from core.utils.logger_handler import logger


class ToolPermissionMiddleware(AgentMiddleware):
    """按策略拦截工具调用。"""

    tools = []

    def __init__(self, policy: dict[str, Any] | None = None):
        self.policy = policy or {}
        self.default = str(self.policy.get("default", "allow")).lower()
        self.allow = {str(name) for name in (self.policy.get("allow") or [])}
        self.deny = {str(name) for name in (self.policy.get("deny") or [])}
        self.risk_levels = self.policy.get("risk_levels") or {}

    def _denied_reason(self, name: str) -> str | None:
        if name in self.deny:
            return "工具在 deny 列表中"
        if self.default == "deny" and name not in self.allow:
            return "工具不在 allow 列表中（default=deny）"
        return None

    @staticmethod
    def _error(request: ToolCallRequest, reason: str) -> ToolMessage:
        name = request.tool_call["name"]
        logger.warning(f"[tool_policy]拦截工具 {name}：{reason}")
        return ToolMessage(
            content=(
                f"[权限策略] 工具 {name} 被禁止执行：{reason}。"
                "请改用其他可用工具，或直接告知用户当前无法执行。"
            ),
            tool_call_id=request.tool_call.get("id", ""),
            name=name,
            status="error",
        )

    def wrap_tool_call(self, request, handler):
        name = request.tool_call["name"]
        reason = self._denied_reason(name)
        if reason:
            return self._error(request, reason)
        risk = self.risk_levels.get(name)
        if risk:
            logger.info(f"[tool_policy]允许工具 {name}（risk={risk}）")
        return handler(request)

    async def awrap_tool_call(self, request, handler):
        name = request.tool_call["name"]
        reason = self._denied_reason(name)
        if reason:
            return self._error(request, reason)
        return await handler(request)


class ToolTimeoutMiddleware(AgentMiddleware):
    """单次工具执行超时。

    同步链路放在线程池里执行，超时后返回 error ToolMessage；
    注意：Python 线程无法被强杀，超时的工具可能仍在后台跑完，
    因此超时只适合读操作，不适合有副作用且不可重入的工具。
    """

    tools = []

    def __init__(self, default_timeout: float = 30, overrides: dict[str, float] | None = None):
        self.default_timeout = float(default_timeout or 0)
        self.overrides = {str(name): float(value) for name, value in (overrides or {}).items()}
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tool-timeout")

    def _timeout(self, name: str) -> float:
        return self.overrides.get(name, self.default_timeout)

    @staticmethod
    def _error(request: ToolCallRequest, timeout: float) -> ToolMessage:
        name = request.tool_call["name"]
        logger.warning(f"[tool_timeout]工具 {name} 超时（>{timeout:g}s）")
        return ToolMessage(
            content=(
                f"[工具超时] 工具 {name} 执行超过 {timeout:g} 秒，已中止。"
                "请改用其他工具，或把请求拆成更小的步骤。"
            ),
            tool_call_id=request.tool_call.get("id", ""),
            name=name,
            status="error",
        )

    def wrap_tool_call(self, request, handler) -> ToolMessage | Command:
        timeout = self._timeout(request.tool_call["name"])
        if timeout <= 0:
            return handler(request)
        future = self._executor.submit(handler, request)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeout:
            return self._error(request, timeout)

    async def awrap_tool_call(self, request, handler) -> ToolMessage | Command:
        timeout = self._timeout(request.tool_call["name"])
        if timeout <= 0:
            return await handler(request)
        try:
            return await asyncio.wait_for(handler(request), timeout=timeout)
        except asyncio.TimeoutError:
            return self._error(request, timeout)
