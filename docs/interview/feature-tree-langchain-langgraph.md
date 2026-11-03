# Agent Harness 功能树 × LangChain / LangGraph 机制

> 用途：面试前掌握“哪个功能、哪个函数、靠框架什么特性实现”。
> 原则：**框架给的能力 vs 自己写的 Harness** 要分清；不要把 LangChain 自带的说成自研。

---

## 0. 总览树

```text
Agent Harness
├─ 1. Runtime / Agent Loop
│  ├─ create_agent 工厂
│  ├─ invoke / stream / resume
│  └─ Scenario 契约
├─ 2. Tool Calling
│  ├─ @tool 注册
│  ├─ 参数校验 / 错误回注
│  ├─ 权限 / 超时 / 重试 / 调用上限
│  └─ content_and_artifact
├─ 3. Middleware / Reliability
│  ├─ 14 层中间件编排
│  ├─ HITL / PII / Todo / Summarization
│  └─ TokenBudget / ModelRetry / ModelFallback
├─ 4. Planning / Routing
│  ├─ 确定性 PlanningPolicy
│  ├─ Router 场景分发
│  ├─ Todo + SQLite 任务图
│  └─ Research 计划节点
├─ 5. Context Engineering
│  ├─ Summarization
│  ├─ Token 预算
│  ├─ 工具结果截断
│  └─ Subagent 上下文隔离
├─ 6. Memory / Checkpoint
│  ├─ InMemorySaver / SqliteSaver
│  ├─ thread_id 会话
│  └─ SQLite KV 长期偏好
├─ 7. Workflow Orchestration
│  ├─ StateGraph
│  ├─ 条件边 / 拒绝分支
│  └─ 7 条工作流
├─ 8. Subagent / Multi-Agent
│  ├─ 单层子 Agent
│  ├─ 工具白名单 / 预算 / 超时
│  └─ 只读 fan-out
├─ 9. MCP
│  ├─ MultiServerMCPClient
│  ├─ Memory server
│  └─ Fetch server（stdio）
├─ 10. RAG
│  ├─ BGE Embedding
│  ├─ Chroma
│  ├─ BM25 / Hybrid
│  └─ RAG tools
├─ 11. Structured Output
│  ├─ Pydantic schema
│  └─ response_format / structured_response
├─ 12. Evaluation
│  ├─ Behavior eval
│  ├─ Outcome eval
│  ├─ Public benchmark / gate
│  └─ 优化循环 / 故障注入
├─ 13. Observability
│  ├─ BaseCallbackHandler trace
│  ├─ token / cost / latency
│  └─ Dashboard
├─ 14. Scenario / Config
└─ 15. UI / Interfaces
```

---

## 1. Runtime / Agent Loop

| 功能 | 我们的实现 | LangChain / LangGraph 机制 | 一句话 |
|---|---|---|---|
| Agent 工厂 | `FrameworkAgent.__init__`（`core/agent/framework.py`） | `langchain.agents.create_agent` | 把 model、tools、middleware、checkpointer、response_format 组装成一个 LangGraph agent |
| ReAct 循环 | `create_agent` 内部 | LangChain agent loop（底层是 LangGraph `StateGraph`） | 模型决定 tool call → ToolNode 执行 → ToolMessage 回注 → 再决策 |
| 同步调用 | `FrameworkAgent.invoke` | `agent.invoke(input, config, context)` | `configurable.thread_id` + callbacks + runtime context |
| 流式输出 | `FrameworkAgent.execute_stream` | `agent.stream(..., stream_mode="values")` | values 模式重放 state，按 message id 去重 |
| 中断恢复 | `FrameworkAgent.resume` | `Command(resume=...)`（`langgraph.types`） | HITL 中断后用 Command 恢复 |
| 读取状态 | `FrameworkAgent.get_state` | `agent.get_state(config)` | 读某个 thread 的 checkpoint state |
| 直接调工具 | `FrameworkAgent.invoke_tool` | `tool.invoke(ToolCall)` | 能力层评测绕过模型和中间件 |
| 模型抽象 | `core/llm/factory.py` | `ChatOpenAI` / `ChatTongyi` | DeepSeek 走 OpenAI 兼容接口 |

---

## 2. Tool Calling

| 功能 | 我们的实现 | LangChain / LangGraph 机制 | 一句话 |
|---|---|---|---|
| 工具定义 | `@tool` in `core/tools/`、`core/scenarios/*/tools.py` | `langchain_core.tools.tool` | 函数签名 + docstring 生成 tool schema |
| 工具注册 | `Scenario.tools`、`Scenario.get_tool` | `create_agent(tools=...)` | 场景声明工具，Harness 统一装配 |
| 参数校验 | `ValidateToolArgsMiddleware` | `AgentMiddleware.wrap_tool_call` + `ToolCallRequest` | 校验失败返回 error `ToolMessage`，模型修正 |
| 错误回注 | `ToolErrorMiddleware(on_error=...)` | LangChain built-in middleware | 工具异常转成可读中文消息 |
| 重试 | `ToolRetryMiddleware(max_retries=1)` | LangChain built-in middleware | 失败后重试一次 |
| 超时 | `ToolTimeoutMiddleware` | `wrap_tool_call` + `ThreadPoolExecutor` / `asyncio.wait_for` | 超时返回 error ToolMessage |
| 权限 | `ToolPermissionMiddleware` | `wrap_tool_call` | allow/deny，deny 不进入 HITL/超时/重试 |
| 调用上限 | `ToolCallLimitMiddleware` | LangChain built-in middleware | 防止死循环 |
| 步数上限 | `LimitStepsMiddleware` | `before_model` + `jump_to="end"` | 模型调用次数上限 |
| 结果 + artifact | `rag_summarize` / `rag_retrieve` | `@tool(response_format="content_and_artifact")` | content 给模型，artifact 给评测 |
| MCP 工具 | `core/mcp/client.py` | `MultiServerMCPClient` + `StructuredTool.from_function` | async MCP tool 包装成 sync LangChain tool |

---

## 3. Middleware / Reliability

| 功能 | 我们的实现 | 框架机制 | 一句话 |
|---|---|---|---|
| 中间件基类 | `_MiddlewareBase(AgentMiddleware)` | `langchain.agents.middleware.AgentMiddleware` | 统一声明 `tools = []`，按需实现 hook |
| HITL | `HumanInTheLoopMiddleware` | LangChain built-in；`interrupt_on=` | 高风险工具审批，approve 才执行 |
| PII | `PIIMiddleware` | LangChain built-in；`strategy="redact"` | 输入侧脱敏 |
| Todo | `TodoListMiddleware` | LangChain built-in | 复杂任务自动维护 todo |
| 上下文压缩 | `SummarizationMiddleware` | LangChain built-in；`trigger=("messages", 30)`、`keep=("messages", 12)` | 历史过长先摘要 |
| Token 预算 | `TokenBudgetMiddleware` | 自定义 `before_model`；`RunBudget` 放在 `runtime.context` | 每次模型调用前检查累计 token |
| 模型重试 | `ModelRetryMiddleware` | LangChain built-in | 模型失败重试一次 |
| 模型回退 | `ModelFallbackMiddleware` | LangChain built-in | 主模型失败时切备用模型（当前未启用） |
| Planning Policy | `PlanningPolicyMiddleware` | 自定义 `before_model` + `jump_to="tools"` + `__can_jump_to__` | 首轮按规则注入工具调用，不命中则 abstain |
| Hooks | `HookManager` + `make_hook_middleware` | `@wrap_tool_call`；`UserPromptSubmit`/`Stop` 在 `invoke` 里手动触发 | 把扩展逻辑挂在事件上，不写进 loop |

> 面试关键：14 层中间件里，**只有少数是自研**；HITL/PII/Todo/Summarization/Retry/Fallback 是 LangChain 自带，我负责选型、顺序和场景配置。

---

## 4. Planning / Routing

| 功能 | 我们的实现 | 框架机制 | 一句话 |
|---|---|---|---|
| 意图分类 | `classify_intent`（`core/agent/middleware/planning.py`） | 自定义关键词/优先级 | 规则级分类，不调用模型 |
| 工具注入 | `PlanningPolicyMiddleware._plan` | `before_model` 返回 `jump_to` + `AIMessage(tool_calls=[...])` | 首轮注入一次，省一次模型调用 |
| 可跳转声明 | `__can_jump_to__ = ["tools"]` | LangChain agent 工厂读取 hook 元数据 | 等价于 `hook_config(can_jump_to=[...])` |
| Router | `core/scenarios/router/tools.py` | `@tool` + 缓存目标 `FrameworkAgent` | route_to_* 调目标场景，不是多 Agent 协商 |
| Todo | `TodoListMiddleware` | LangChain built-in | 任务清单 |
| 任务图 | `TaskStore` / `TaskRunner`（`core/runtime/`） | 自定义 SQLite 任务图 | blocked_by、认领、完成、解锁下游 |
| Research 计划 | `_plan_queries`（`research_assistant/graph.py`） | `PromptTemplate | chat_model | StrOutputParser` + `StateGraph` | 把问题拆成 3 个子问题再 fan-out |
| Planner A/B | `core/experiments/planner_eval.py` | `dataclasses.replace` + `FrameworkAgent` | baseline vs policy 对比 |

---

## 5. Context Engineering

| 功能 | 我们的实现 | 框架机制 | 一句话 |
|---|---|---|---|
| 历史压缩 | `SummarizationMiddleware` | LangChain built-in | 30 条消息触发，保留 12 条 |
| Token 预算 | `RunBudget` + `TokenBudgetMiddleware` | 自定义 `before_model` + `runtime.context` | 超预算直接结束，避免继续烧钱 |
| 工具结果截断 | 工具实现 + MCP `_content_text` | 自定义 | 返回给模型的内容有上限 |
| 子 Agent 隔离 | `build_subagent_tool` | 子 `FrameworkAgent` fresh context | 子任务噪声不污染主上下文 |
| Todo 后置 | `TodoListMiddleware` | LangChain built-in | 任务状态放在上下文后部，缓解 lost-in-the-middle |
| PII 脱敏 | `PIIMiddleware` | LangChain built-in | 输入侧 redact |
| **缺** | — | — | offloading / context editing / cache 友好前缀 / prompt 版本化 |

---

## 6. Memory / Checkpoint

| 功能 | 我们的实现 | 框架机制 | 一句话 |
|---|---|---|---|
| 短期记忆 | `build_checkpointer`（`core/agent/checkpoint.py`） | `InMemorySaver` / `SqliteSaver`（LangGraph） | 按 thread 保存 state |
| 会话隔离 | `FrameworkAgent._config` | `config={"configurable": {"thread_id": ...}}` | 不同 thread 互不污染 |
| 长期偏好 | `MemoryStore`（workspace `tools.py`） | 自定义 SQLite KV | remember / recall / list |
| Memory MCP | `mcp_demo` | 外部 MCP server | 跨会话记忆演示，不是用户画像 |
| **缺** | — | — | 语义记忆 / 巩固 / 冲突消解 / 衰减 |

---

## 7. Workflow Orchestration

| 功能 | 我们的实现 | 框架机制 | 一句话 |
|---|---|---|---|
| 工作流运行时 | `WorkflowRuntime`（`core/agent/workflow.py`） | `scenario.workflow_factory(scenario)` + `graph.invoke({"input": ...})` | 只执行 Scenario 提供的 LangGraph |
| 状态定义 | `WorkflowState` / `ResearchState` / `WorkspaceState` | `TypedDict` | 节点共享 typed state |
| 节点 / 边 | `graph.add_node` / `add_edge` | `langgraph.graph.StateGraph` | 固定步骤显式编排 |
| 条件分支 | `add_conditional_edges` | LangGraph | 检索为空走 refuse 分支 |
| 7 条工作流 | robot 2 + workspace 4 + research 1 | LangGraph | `rag_qa`、`report`、`document_qa`、`study_notes`、`cross_lingual`、`content_draft`、`deep_research` |
| **缺** | — | — | durable execution / 队列 / 分布式 |

---

## 8. Subagent / Multi-Agent

| 功能 | 我们的实现 | 框架机制 | 一句话 |
|---|---|---|---|
| 子 Agent 工厂 | `build_subagent_tool`（`core/agent/subagent.py`） | `@tool` + 子 `FrameworkAgent` | 子 Agent 只返回最终摘要 |
| 工具白名单 | `select_subagent_tools` | 自定义 | 排除 `subagent` 自身，禁止递归 |
| 独立上下文 | 子 `Scenario(checkpoint=False)` | 自定义 | fresh context，不继承父对话 |
| 超时 | `ThreadPoolExecutor` + `future.result(timeout)` | Python 并发 | 超时返回可读消息 |
| 并行 fan-out | `_fan_out`（research graph） | `ThreadPoolExecutor` + `subagent` | 3 个子 Agent 并行读 3 篇资料 |
| Router | `route_to_*` | `@tool` + 缓存目标 Agent | 场景级分发，不是 handoff |
| **缺** | — | — | supervisor / handoff / 共享状态 / A2A |

---

## 9. MCP

| 功能 | 我们的实现 | 框架机制 | 一句话 |
|---|---|---|---|
| MCP 客户端 | `core/mcp/client.py` | `langchain_mcp_adapters.client.MultiServerMCPClient` | 多 server、工具名前缀 |
| Memory server | `memory_connection()` | 官方 Node Memory server（stdio） | 跨会话记忆 |
| Fetch server | `fetch_connection()` + `fetch_server.py` | FastMCP；`mcp.run(transport="stdio")` | 本地 Fetch，域名白名单/私网拦截 |
| async → sync | `_to_sync_tool` | `StructuredTool.from_function` + `run_async` | 把 MCP async 工具接进 LangChain |
| 安全 | `fetch_server.py` | 自定义 | allowlist、private IP block、200KB、untrusted 标记 |
| **缺** | — | — | HTTP/SSE、auth、多 server 治理、健康检查、注入分类器 |

---

## 10. RAG

| 功能 | 我们的实现 | 框架机制 | 一句话 |
|---|---|---|---|
| Embedding | `LazyLocalEmbeddings` / `EmbeddingsFactory` | `langchain_huggingface.HuggingFaceEmbeddings` / `DashScopeEmbeddings` | 本地 BGE，CPU |
| 向量库 | `VectorStoreService` | `langchain_chroma.Chroma` | 持久化到本地 |
| 切分 | `_get_splitter` | `langchain_text_splitters.RecursiveCharacterTextSplitter` | 按文件类型切分 |
| BM25 | `KeywordBM25Retriever` | `langchain_core.retrievers.BaseRetriever` | 自定义 jieba/bigram/char 分词 |
| Hybrid | `TopKEnsembleRetriever` | `langchain_classic.retrievers.EnsembleRetriever` | 加权 RRF，截断 top-k |
| RAG 链 | `RagSummarizeService` | `PromptTemplate | chat_model | StrOutputParser` | 检索 → 格式化 context → 生成 |
| RAG 工具 | `build_rag_tools` | `@tool(response_format="content_and_artifact")` | content 给模型，artifact 给评测 |
| **缺** | — | — | rerank / query rewrite / GraphRAG / agentic retrieval |

---

## 11. Structured Output

| 功能 | 我们的实现 | 框架机制 | 一句话 |
|---|---|---|---|
| Schema | `ReportSchema`（`structured_demo/schema.py`） | Pydantic `BaseModel` + `Field` | summary / evidence / confidence / next_actions / risks |
| 接线 | `Scenario.response_format` | `create_agent(response_format=ReportSchema)` | LangChain 结构化输出 |
| 读取 | `structured_eval.extract_report` | `state["structured_response"]` | 评测直接读 schema 结果 |
| 评测 | `structured_eval.evaluate_case` | 自定义 | schema 合法、证据、confidence、next_actions |

---

## 12. Evaluation

| 功能 | 我们的实现 | 框架机制 | 一句话 |
|---|---|---|---|
| 行为评测 | `agent_eval.evaluate_case` | `FrameworkAgent.invoke` + messages | 跑完整 Agent，看工具选择/传参/回答 |
| 工具调用提取 | `extract_tool_calls` | `AIMessage.tool_calls` | 从消息里拿工具名和参数 |
| 评分 | `score_case` | 自定义 | 关键词覆盖 + 工具命中 + 拒答 |
| pass^k | `aggregate_trials` | 自定义 | 所有 trial 都通过才算过 |
| Outcome | `outcome_eval.evaluate_case` | `FrameworkAgent` / `WorkflowRuntime` + 文件/SQLite/trace | 不看回答，检查真实环境状态 |
| 结构化评测 | `structured_eval` | `structured_response` | 严格 schema 评测 |
| 公开基准 | `bfcl_simplified` / `public_sample` / `multihop_full` | 自定义适配器 + 抽样 | 抽样/简化评分，不是官方 |
| 门禁 | `gate.py` | 自定义读报告 + 阈值 | 不是 CI |
| 故障注入 | `tests/test_fault_injection.py` | pytest + fake tools | 超时/权限/参数/空检索/拒答 |
| 优化循环 | `experiments/optimize.py` | 自定义 3-trial | baseline → 改动 → 复跑 → 回归 |
| **缺** | — | — | 官方 scorer / CI / 5–10 trial / bootstrap CI |

---

## 13. Observability

| 功能 | 我们的实现 | 框架机制 | 一句话 |
|---|---|---|---|
| Trace | `TraceCallbackHandler`（`core/observability/tracer.py`） | `langchain_core.callbacks.BaseCallbackHandler` | 写 JSONL：model/tool/run_end |
| 回调方法 | `on_chat_model_start` / `on_llm_end` / `on_tool_start` / `on_tool_end` / `on_tool_error` / `on_chain_end` / `on_chain_error` | LangChain callback 协议 | 每个模型/工具事件都能抓到 |
| Token / 成本 | `RunBudget` / `cost_report` | 自定义；读 usage_metadata | p50/p95、token、估算成本 |
| Trace 查看 | `trace_report` | 自定义 JSONL | `--last N` / `--trace-id` |
| Dashboard | `core/interfaces/dashboard/` | Streamlit | 总览 / 架构 / 任务 / 用例 / 评测 / 优化 / 目录 |
| **缺** | — | — | OTel / LangSmith / 采样 / 告警 / trace PII 脱敏 |

---

## 14. Scenario / Config / UI

| 功能 | 我们的实现 | 框架机制 | 一句话 |
|---|---|---|---|
| Scenario 契约 | `Scenario` dataclass（`core/agent/contracts.py`） | 自定义边界 | model / prompt / tools / policy / budget / checkpoint / workflow |
| 场景注册 | `core/scenarios/registry.py` | 自定义 | `get_scenario(name)` |
| 配置 | `config/*.yml` | YAML | RAG / Chroma / prompts / pricing |
| 运行时配置 | `RuntimeConfig` / `SubagentConfig` | 自定义 | hooks / workspace / task store / subagent |
| UI | `agent_dashboard.py` | Streamlit | 9 → 7 视图（合并评测页） |
| 兼容层 | `core/interfaces/react_agent.py` | 自定义 | 旧 API 不变 |

---

## 15. 框架 vs 自研（面试必须分清）

| 来源 | 提供的 |
|---|---|
| **LangChain** | `create_agent`、`AgentMiddleware`、`TodoListMiddleware`、`SummarizationMiddleware`、`HumanInTheLoopMiddleware`、`PIIMiddleware`、`ToolRetryMiddleware`、`ToolErrorMiddleware`、`ToolCallLimitMiddleware`、`ModelRetryMiddleware`、`ModelFallbackMiddleware`、`@tool`、`StructuredTool`、`BaseRetriever`、`EnsembleRetriever`、`Chroma`、`HuggingFaceEmbeddings`、`PromptTemplate`、`StrOutputParser`、`BaseCallbackHandler`、`MultiServerMCPClient` |
| **LangGraph** | `StateGraph`、`START`/`END`、`add_node`/`add_edge`/`add_conditional_edges`、`InMemorySaver`/`SqliteSaver`、`Command(resume=...)`、`Runtime`、`create_agent` 底层图 |
| **你写的** | Scenario 契约、中间件组合与顺序、`ToolPermissionMiddleware`、`ToolTimeoutMiddleware`、`TokenBudgetMiddleware`、`LimitStepsMiddleware`、`PlanningPolicyMiddleware`、`HookManager`、`build_subagent_tool`、7 条工作流、BM25/Hybrid retriever、Fetch MCP server、行为/outcome 评测、gate、优化循环、trace/cost、dashboard、8 个场景与工具 |

**一句话**：
> “LangChain 给我 agent 工厂、中间件和工具/检索原语；LangGraph 给我状态图、checkpoint 和中断恢复；我写的是 Scenario 契约、中间件编排、planning policy、subagent、评测和可观测。”

---

## 16. 最可能被追问的 10 个“哪个函数 / 哪个特性”

1. **Agent 是怎么跑起来的？**
   `FrameworkAgent.__init__` 调 `create_agent(...)`；`invoke` 调 `agent.invoke(...)`。
2. **工具调用链？**
   `@tool` → `create_agent(tools=...)` → 模型 `tool_calls` → `ToolNode` → 中间件链 → `ToolMessage` → 模型。
3. **HITL 怎么恢复？**
   `HumanInTheLoopMiddleware(interrupt_on=...)` → `Command(resume=...)`。
4. **记忆怎么持久化？**
   `SqliteSaver` + `config={"configurable": {"thread_id": ...}}`。
5. **结构化输出？**
   `create_agent(response_format=ReportSchema)` → `state["structured_response"]`。
6. **工作流？**
   `StateGraph` + `add_node` / `add_edge` / `add_conditional_edges` + `compile()`。
7. **Planning policy？**
   自定义 `AgentMiddleware.before_model` 返回 `{"jump_to": "tools", "messages": [AIMessage(tool_calls=...)]}`，并设置 `__can_jump_to__ = ["tools"]`。
8. **Token 预算？**
   自定义 `TokenBudgetMiddleware.before_model` 读 `runtime.context["_run_budget"]`。
9. **MCP 怎么接？**
   `MultiServerMCPClient` → `get_tools()` → `StructuredTool.from_function` 包装成 sync。
10. **Trace 怎么来的？**
    `TraceCallbackHandler(BaseCallbackHandler)` 挂在 `config["callbacks"]`，写 JSONL。

---

## 17. 一句话总结

> **LangChain 是 agent 工厂 + 中间件 + 工具/检索原语；LangGraph 是状态图 + checkpoint + 中断恢复；我的价值是把这些原语组装成可约束、可评测、可观测的 Harness。**
