# -*- coding: utf-8 -*-
"""总路由工具：调用目标场景的 FrameworkAgent，返回答案和目标 trace。

路由表在 ``data/routes/router.json``（见 ``routes.py``），这里只负责"调目标场景"。
"""
from __future__ import annotations

import json
import threading
import uuid

from core.agent.framework import FrameworkAgent
from core.quality.agent_eval import extract_final_answer
from core.scenarios.registry import get_scenario

_AGENTS: dict[str, FrameworkAgent] = {}
_LOCK = threading.Lock()


def _agent(name: str) -> FrameworkAgent:
    with _LOCK:
        agent = _AGENTS.get(name)
        if agent is None:
            agent = FrameworkAgent(get_scenario(name))
            _AGENTS[name] = agent
        return agent


def run_target(name: str, query: str) -> str:
    """把请求转给目标场景，返回 JSON 字符串（含目标 trace）。"""
    try:
        agent = _agent(name)
        state = agent.invoke(query, thread_id=f"route-{name}-{uuid.uuid4().hex}")
        answer = extract_final_answer(state.get("messages", []))
        return json.dumps(
            {
                "target": name,
                "answer": answer,
                "target_trace_id": agent.last_trace_id,
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as exc:  # noqa: BLE001 - 路由失败返回可读错误
        return json.dumps(
            {"target": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"},
            ensure_ascii=False,
        )


def build_route_tools(routes=None):
    """兼容入口：按路由表（默认 data/routes/router.json）生成工具。"""
    from core.scenarios.router.routes import build_route_tools as _build

    return _build(routes)
