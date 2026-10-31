# -*- coding: utf-8 -*-
"""Subagent：父 Agent 派生子 Agent，子 Agent 使用全新上下文。

设计要点：
- 子 Agent 只拿基础工具，默认排除 subagent 自身，避免递归；
- 子 Agent 不继承父对话 / checkpoint，只返回最终摘要；
- 通过场景层 RuntimeConfig.subagent 配置 allowed_tools / 预算 / 超时。
"""
from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from core.agent.contracts import Scenario
from core.agent.framework import FrameworkAgent
from core.agent.middleware import LimitStepsMiddleware
from core.runtime.config import RuntimeConfig, SubagentConfig


def _answer_text(messages) -> str:
    for message in reversed(messages or []):
        if isinstance(message, AIMessage):
            content = message.content
            if isinstance(content, list):
                content = "".join(
                    str(block.get("text", ""))
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            if isinstance(content, str) and content.strip():
                return content.strip()
    return ""


def select_subagent_tools(parent_tools, config: SubagentConfig):
    """子 Agent 工具：排除 subagent 自身；有 allowed_tools 时只保留白名单。"""
    allowed = set(config.allowed_tools) if config.allowed_tools else None
    return [
        item for item in parent_tools
        if item.name != config.name and (allowed is None or item.name in allowed)
    ]


def build_subagent_tool(
    model,
    parent_tools,
    config: SubagentConfig,
    parent_runtime: RuntimeConfig | None = None,
):
    child_tools = select_subagent_tools(parent_tools, config)
    child_runtime = None
    if parent_runtime and parent_runtime.hooks:
        child_runtime = RuntimeConfig(hooks={
            event: list(callbacks)
            for event, callbacks in parent_runtime.hooks.items()
        })

    @tool(config.name, description=config.description)
    def subagent(description: str) -> str:
        child = Scenario(
            name=f"{config.name}_child",
            description="subagent",
            model=model,
            system_prompt=config.system_prompt,
            tools=child_tools,
            middleware=[LimitStepsMiddleware(config.max_model_calls)],
            context={},
            cases_path=None,
            high_risk_tools={},
            fallback_model=None,
            enable_todo=False,
            enable_summarization=False,
            tool_call_limit=config.max_model_calls,
            token_budget=config.token_budget,
            pii_types=[],
            checkpoint=False,
            tool_policy={"default": "allow"},
            tool_timeout_seconds=60,
            runtime=child_runtime,
        )
        agent = FrameworkAgent(child)
        thread_id = f"subagent-{uuid.uuid4().hex}"
        # 不用 with：超时后 with 会 shutdown(wait=True)，仍然阻塞到子线程结束，
        # 让 timeout 形同虚设。这里只放弃等待，线程本身无法被 Python 强杀。
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            future = pool.submit(agent.invoke, description, thread_id)
            state = future.result(timeout=config.timeout_seconds)
        except FutureTimeout:
            return f"Subagent 超时（>{config.timeout_seconds:.0f}s），任务未完成。"
        except Exception as exc:  # noqa: BLE001 - 子 Agent 失败不拖垮父 Agent
            return f"Subagent 执行失败：{type(exc).__name__}: {exc}"
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

        answer = _answer_text(state.get("messages", []))
        if not answer:
            return "Subagent 没有返回文本结论。"
        return answer

    return subagent
