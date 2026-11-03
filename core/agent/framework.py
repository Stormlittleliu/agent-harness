"""Agent 框架层：只依赖 Scenario 抽象，不 import 任何具体业务工具。

在通用 ReAct 运行时之上，用 LangChain 1.x 内置中间件补齐 Harness 能力：
- TodoListMiddleware：复杂任务规划（参考 learn-claude-code s05/s12）
- SummarizationMiddleware：上下文压缩（s08）
- PIIMiddleware：敏感信息脱敏（s03）
- HumanInTheLoopMiddleware：高风险工具审批（s03）
- ToolRetry / ModelRetry / ModelFallback / ToolError：错误恢复（s11）
- ToolCallLimit：工具调用上限，防止循环
- ToolPermission / ToolTimeout：工具权限与执行超时
- TokenBudget：单次 run 的累计 token 上限（含工具内部模型调用）
- InMemorySaver / SqliteSaver：会话记忆与 checkpoint（s09）
- TraceCallbackHandler：模型/工具/token/耗时写入本地 trace
"""
import uuid

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langgraph.types import Command

from core.agent.checkpoint import build_checkpointer
from core.agent.contracts import Scenario
from core.agent.hooks import HookManager
from core.agent.pipeline import build_pipeline
from core.observability.budget import RunBudget
from core.observability.tracer import TraceCallbackHandler


class FrameworkAgent:
    """通用的 ReAct Agent 运行时。

    业务差异全部由 Scenario 提供；Harness 能力由本层统一装配。
    """

    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self.last_thread_id = None
        self.last_trace_id = None
        self.last_interrupt = None
        runtime = getattr(scenario, "runtime", None)
        self.hook_manager = HookManager(getattr(runtime, "hooks", None))

        # 装配逻辑统一在 core.agent.pipeline：slot 决定顺序，spec 的 policies 只做覆盖。
        self.middleware = build_pipeline(
            scenario,
            self.hook_manager,
            getattr(scenario, "policies", None),
        )
        self.checkpointer = (
            build_checkpointer(scenario.checkpoint_backend, scenario.checkpoint_path)
            if scenario.checkpoint else None
        )
        self.agent = create_agent(
            model=scenario.model,
            system_prompt=scenario.system_prompt,
            tools=scenario.tools,
            middleware=self.middleware,
            checkpointer=self.checkpointer,
            response_format=scenario.response_format,
        )

    @staticmethod
    def _config(thread_id: str, tracer: TraceCallbackHandler | None = None) -> dict:
        config = {"configurable": {"thread_id": thread_id}}
        if tracer is not None:
            config["callbacks"] = [tracer]
            config["metadata"] = {"trace_id": tracer.trace_id, "thread_id": thread_id}
        return config

    def _start_trace(self, thread_id: str, budget: RunBudget | None = None) -> TraceCallbackHandler:
        tracer = TraceCallbackHandler(
            trace_id=f"run-{uuid.uuid4().hex}",
            thread_id=thread_id,
            budget=budget,
            scenario=self.scenario.name,
        )
        self.last_trace_id = tracer.trace_id
        return tracer

    def _run_context(self, budget: RunBudget) -> dict:
        context = dict(self.scenario.context)
        context["_run_budget"] = budget
        return context

    def invoke_tool(self, name: str, args: dict | None = None):
        """能力层入口：直接调用场景工具，不经过模型与中间件。

        用 ToolCall 形式调用，返回 ToolMessage；content_and_artifact 工具的
        artifact 会保留在 `.artifact` 上，供评测读取原始 docs / rank / source。
        仅用于工具级评测/调试；权限、HITL、超时等 Harness 逻辑只在 `invoke` 中生效。
        """
        tool = self.scenario.get_tool(name)
        return tool.invoke({
            "name": name,
            "args": args or {},
            "id": f"invoke-{uuid.uuid4().hex}",
            "type": "tool_call",
        })

    def invoke(self, query: str, thread_id: str | None = None):
        """执行一次对话；thread_id 相同时会保留历史（checkpoint 记忆）。

        不传 thread_id 时生成一次性 ID，保证测试/批量调用互不污染。
        """
        thread_id = thread_id or f"run-{uuid.uuid4().hex}"
        self.last_thread_id = thread_id
        rewritten = self.hook_manager.trigger("UserPromptSubmit", query)
        if isinstance(rewritten, str) and rewritten.strip():
            query = rewritten
        budget = RunBudget(self.scenario.token_budget)
        tracer = self._start_trace(thread_id, budget)
        try:
            result = self.agent.invoke(
                {"messages": [{"role": "user", "content": query}]},
                config=self._config(thread_id, tracer),
                context=self._run_context(budget),
            )
            self.hook_manager.trigger("Stop", result.get("messages", []))
            return result
        finally:
            tracer.finalize_if_needed()

    def resume(self, thread_id: str, decisions: list[dict] | None = None):
        """恢复被 human-in-the-loop 中断的 run。

        decisions 形如 [{"type": "approve"}] 或 [{"type": "reject", "message": "..."}]。
        """
        decisions = decisions or [{"type": "approve"}]
        self.last_thread_id = thread_id
        budget = RunBudget(self.scenario.token_budget)
        tracer = self._start_trace(thread_id, budget)
        try:
            result = self.agent.invoke(
                Command(resume={"decisions": decisions}),
                config=self._config(thread_id, tracer),
                context=self._run_context(budget),
            )
            self.hook_manager.trigger("Stop", result.get("messages", []))
            return result
        finally:
            tracer.finalize_if_needed()

    def get_state(self, thread_id: str):
        return self.agent.get_state(self._config(thread_id))

    def execute_stream(self, query: str, thread_id: str = "default"):
        self.last_thread_id = thread_id
        self.last_interrupt = None
        rewritten = self.hook_manager.trigger("UserPromptSubmit", query)
        if isinstance(rewritten, str) and rewritten.strip():
            query = rewritten
        budget = RunBudget(self.scenario.token_budget)
        tracer = self._start_trace(thread_id, budget)
        input_dict = {
            "messages": [
                {"role": "user", "content": query},
            ]
        }
        seen_message_ids: set[str] = set()
        last_messages: list = []

        try:
            for chunk in self.agent.stream(
                input_dict,
                config=self._config(thread_id, tracer),
                stream_mode="values",
                context=self._run_context(budget),
            ):
                # values 模式在中断时会单独给出 __interrupt__，界面需要据此发起审批
                if "__interrupt__" in chunk:
                    self.last_interrupt = chunk["__interrupt__"]

                messages = chunk.get("messages") or []
                if not messages:
                    continue
                last_messages = messages
                latest_message = messages[-1]

                # 只输出模型回复：跳过 HumanMessage、ToolMessage 和只有工具调用的空 AI 消息
                if not isinstance(latest_message, AIMessage):
                    continue

                # values 模式每步都会重放整个 state，同一条 AI 消息会出现多次，按 id 去重
                message_id = getattr(latest_message, "id", None)
                if message_id:
                    if message_id in seen_message_ids:
                        continue
                    seen_message_ids.add(message_id)

                content = latest_message.content
                if isinstance(content, list):
                    content = "".join(
                        str(block.get("text", ""))
                        for block in content
                        if isinstance(block, dict) and block.get("type") == "text"
                    )
                if isinstance(content, str) and content.strip():
                    yield content.strip() + "\n"
        finally:
            self.hook_manager.trigger("Stop", last_messages)
            tracer.finalize_if_needed()
