# -*- coding: utf-8 -*-
"""通用工作流运行时：只执行 Scenario 提供的 LangGraph。

场景层（scenarios/<name>/graph.py）负责挑工具、定义节点和边；
本文件不知道任何业务工作流名，也不 import rag/business 工具。
"""
from __future__ import annotations

import uuid

from core.observability.tracer import TraceCallbackHandler


class WorkflowRuntime:
    def __init__(self, scenario):
        self.scenario = scenario
        factory = getattr(scenario, "workflow_factory", None)
        self.graphs = factory(scenario) if factory else {}
        self.last_trace_id: str | None = None

    def list_workflows(self) -> list[str]:
        return sorted(self.graphs)

    def run(self, name: str, input_text: str):
        if name not in self.graphs:
            available = ", ".join(self.list_workflows()) or "（无）"
            raise FileNotFoundError(f"工作流不存在：{name}（可用：{available}）")
        tracer = TraceCallbackHandler(
            trace_id=f"run-{uuid.uuid4().hex}",
            thread_id=f"workflow-{uuid.uuid4().hex}",
            scenario=getattr(self.scenario, "name", None),
        )
        self.last_trace_id = tracer.trace_id
        try:
            return self.graphs[name].invoke(
                {"input": input_text},
                config={"callbacks": [tracer]},
            )
        finally:
            tracer.finalize_if_needed()

