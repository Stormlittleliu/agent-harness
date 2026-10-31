# -*- coding: utf-8 -*-
"""任务执行器：认领 → 跑 Agent → 完成/失败 → 解锁下游。"""
from __future__ import annotations

from typing import Any

from core.runtime.tasks import Task, TaskStore


def _answer_text(messages) -> str:
    for message in reversed(messages or []):
        if getattr(message, "type", "") == "ai":
            content = getattr(message, "content", "")
            if isinstance(content, list):
                content = "".join(
                    str(block.get("text", ""))
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            if isinstance(content, str) and content.strip():
                return content.strip()
    return ""


class TaskRunner:
    def __init__(self, agent: Any, store: TaskStore):
        self.agent = agent
        self.store = store

    def run_task(self, task_id: str, thread_id: str | None = None) -> dict:
        try:
            task = self.store.claim(task_id)
        except (KeyError, ValueError) as exc:
            return {"task_id": task_id, "status": "not_claimed", "error": str(exc)}

        hooks = getattr(self.agent, "hook_manager", None)
        if hooks:
            hooks.trigger("TaskStart", task)

        try:
            state = self.agent.invoke(
                task.description or task.subject,
                thread_id=thread_id or f"task-{task.id}",
            )
            if state.get("__interrupt__"):
                raise RuntimeError("任务被 HITL 中断，等待人工处理")
            answer = _answer_text(state.get("messages", []))
            unblocked = self.store.complete(task.id, answer)
            if hooks:
                hooks.trigger("TaskComplete", task, answer, unblocked)
            return {
                "task_id": task.id,
                "status": "completed",
                "answer": answer,
                "unblocked": [item.id for item in unblocked],
            }
        except Exception as exc:  # noqa: BLE001 - 任务失败要落库
            self.store.fail(task.id, f"{type(exc).__name__}: {exc}")
            if hooks:
                hooks.trigger("TaskFail", task, str(exc))
            return {
                "task_id": task.id,
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
            }

    def run_ready(self, limit: int = 1) -> list[dict]:
        results = []
        for task in self.store.ready()[: max(1, limit)]:
            results.append(self.run_task(task.id))
        return results
