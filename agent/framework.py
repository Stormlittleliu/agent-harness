"""Agent 框架层：只依赖 Scenario 抽象，不 import 任何具体业务工具。

在通用 ReAct 运行时之上，用 LangChain 1.x 内置中间件补齐 Harness 能力：
- TodoListMiddleware：复杂任务规划（参考 learn-claude-code s05/s12）
- SummarizationMiddleware：上下文压缩（s08）
- PIIMiddleware：敏感信息脱敏（s03）
- HumanInTheLoopMiddleware：高风险工具审批（s03）
- ToolRetry / ModelRetry / ModelFallback / ToolError：错误恢复（s11）
- ToolCallLimit：工具调用上限，防止循环
- InMemorySaver：会话记忆与 checkpoint（s09）
"""
import uuid

from langchain.agents import create_agent
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
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from scenarios.base import Scenario


def _on_tool_error(exc: Exception, request) -> str:
    """把工具执行异常转成中文 error ToolMessage，让 Agent 有机会换一种方式继续。"""
    tool_name = request.tool_call.get("name", "unknown")
    return (
        f"[工具执行异常] 工具 {tool_name} 执行失败（{type(exc).__name__}）。"
        "请不要重复同样的调用，检查参数或改用其他工具。"
    )


class FrameworkAgent:
    """通用的 ReAct Agent 运行时。

    业务差异全部由 Scenario 提供；Harness 能力由本层统一装配。
    """

    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self.last_thread_id = None

        middleware = [*scenario.middleware]

        # 规划：复杂任务自动维护 todo
        if scenario.enable_todo:
            middleware.append(TodoListMiddleware())

        # 上下文压缩：历史过长时摘要，避免上下文溢出
        if scenario.enable_summarization:
            middleware.append(SummarizationMiddleware(
                model=scenario.model,
                trigger=scenario.summarization_trigger,
                keep=scenario.summarization_keep,
            ))

        # 敏感信息脱敏（输入侧）
        for pii_type in scenario.pii_types:
            middleware.append(PIIMiddleware(
                pii_type,
                strategy="redact",
                apply_to_input=True,
                apply_to_output=False,
                apply_to_tool_results=False,
            ))

        # 高风险工具审批：审批通过才执行
        if scenario.high_risk_tools:
            middleware.append(HumanInTheLoopMiddleware(interrupt_on=scenario.high_risk_tools))

        # 工具/模型重试与降级
        middleware.append(ToolRetryMiddleware(max_retries=1))
        if scenario.tool_call_limit:
            middleware.append(ToolCallLimitMiddleware(
                run_limit=scenario.tool_call_limit,
                exit_behavior="end",
            ))
        if scenario.fallback_model is not None:
            middleware.append(ModelFallbackMiddleware(scenario.fallback_model))
        middleware.append(ModelRetryMiddleware(max_retries=1))
        middleware.append(ToolErrorMiddleware(on_error=_on_tool_error))

        self.checkpointer = InMemorySaver() if scenario.checkpoint else None
        self.agent = create_agent(
            model=scenario.model,
            system_prompt=scenario.system_prompt,
            tools=scenario.tools,
            middleware=middleware,
            checkpointer=self.checkpointer,
        )

    @staticmethod
    def _config(thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    def invoke(self, query: str, thread_id: str | None = None):
        """执行一次对话；thread_id 相同时会保留历史（checkpoint 记忆）。

        不传 thread_id 时生成一次性 ID，保证测试/批量调用互不污染。
        """
        thread_id = thread_id or f"run-{uuid.uuid4().hex}"
        self.last_thread_id = thread_id
        return self.agent.invoke(
            {"messages": [{"role": "user", "content": query}]},
            config=self._config(thread_id),
            context=dict(self.scenario.context),
        )

    def resume(self, thread_id: str, decisions: list[dict] | None = None):
        """恢复被 human-in-the-loop 中断的 run。

        decisions 形如 [{"type": "approve"}] 或 [{"type": "reject", "message": "..."}]。
        """
        decisions = decisions or [{"type": "approve"}]
        self.last_thread_id = thread_id
        return self.agent.invoke(
            Command(resume={"decisions": decisions}),
            config=self._config(thread_id),
            context=dict(self.scenario.context),
        )

    def get_state(self, thread_id: str):
        return self.agent.get_state(self._config(thread_id))

    def execute_stream(self, query: str, thread_id: str = "default"):
        self.last_thread_id = thread_id
        input_dict = {
            "messages": [
                {"role": "user", "content": query},
            ]
        }

        for chunk in self.agent.stream(
            input_dict,
            config=self._config(thread_id),
            stream_mode="values",
            context=dict(self.scenario.context),
        ):
            latest_message = chunk["messages"][-1]

            # 只输出模型回复：跳过 HumanMessage、ToolMessage 和只有工具调用的空 AI 消息
            if not isinstance(latest_message, AIMessage):
                continue
            content = latest_message.content
            if isinstance(content, list):
                content = "".join(
                    str(block.get("text", ""))
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            if isinstance(content, str) and content.strip():
                yield content.strip() + "\n"
