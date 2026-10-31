# -*- coding: utf-8 -*-
"""Hook 机制：把扩展逻辑从 loop 里挪到事件上。

事件：
- UserPromptSubmit：用户输入进入模型前，可返回新 query；
- PreToolUse：工具执行前，返回非 None 即拦截；
- PostToolUse：工具执行后，用于日志/告警；
- Stop：一轮 run 结束；
- TaskStart / TaskComplete / TaskFail：任务执行器触发。
"""
from __future__ import annotations

from typing import Any, Callable

from langchain.agents.middleware import wrap_tool_call
from langchain_core.messages import ToolMessage

from core.utils.logger_handler import logger

EVENTS = (
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Stop",
    "TaskStart",
    "TaskComplete",
    "TaskFail",
)


class HookManager:
    def __init__(self, hooks: dict[str, list[Callable]] | None = None):
        self.hooks: dict[str, list[Callable]] = {event: [] for event in EVENTS}
        for event, callbacks in (hooks or {}).items():
            self.hooks.setdefault(event, []).extend(callbacks or [])

    def has_hooks(self) -> bool:
        return any(self.hooks.values())

    def trigger(self, event: str, *args, **kwargs) -> Any:
        for callback in self.hooks.get(event, []):
            try:
                result = callback(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - hook 不能拖垮主流程
                logger.warning(f"[hook:{event}] {type(exc).__name__}: {exc}")
                continue
            if result is not None:
                return result
        return None


def make_hook_middleware(manager: HookManager):
    @wrap_tool_call
    def _hook_middleware(request, handler):
        blocked = manager.trigger("PreToolUse", request)
        if blocked:
            tool_call = request.tool_call or {}
            return ToolMessage(
                content=str(blocked),
                tool_call_id=tool_call.get("id", ""),
                name=tool_call.get("name", ""),
                status="error",
            )
        result = handler(request)
        manager.trigger("PostToolUse", request, result)
        return result

    return _hook_middleware
