# 项目架构树与模块职责

> 一句话：**模型只负责决策，Harness 负责工具、上下文、状态、权限、预算、trace 和评测。**
> 本文回答三个问题：目录怎么分、每层负责什么、一次请求怎么走。

---

## 1. 分层架构

```text
┌──────────────────────────────────────────────────────────────┐
│ 界面层  core/interfaces/                                      │
│ Streamlit 控制台（总览 + 8 功能页） / CLI / 工作流 CLI         │
└──────────────────────────────┬───────────────────────────────┘
                               │ 用户问题 / 评测命令
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Harness 层  core/agent/                                       │
│ FrameworkAgent = create_agent + Scenario 契约 + 14 层中间件   │
│   ├─ 权限 / 参数校验 / 错误回注 / 重试 / 超时 / 预算          │
│   ├─ Todo / 上下文压缩 / PII / HITL / checkpoint              │
│   ├─ PlanningPolicy（可选，首轮注入工具调用）                  │
│   └─ TraceCallbackHandler（模型/工具/token/时延）             │
└──────────────────────────────┬───────────────────────────────┘
                               │ 按 Scenario 装配
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ 场景层  core/scenarios/<name>/                                │
│ scenario.py（模型/提示词/工具/权限/预算/工作流）               │
│ tools.py（场景工具） / graph.py（LangGraph 工作流）            │
│ cases.jsonl（行为用例） / outcome_cases.jsonl（结果断言）      │
└───────┬───────────────┬───────────────┬──────────────────────┘
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌────────────────────────────┐
│ 工具层       │ │ 运行时扩展   │ │ 协议 / 子 Agent            │
│ core/tools/  │ │ core/runtime │ │ core/mcp/                  │
│ 业务 mock +  │ │ 任务图 /     │ │ Memory + Fetch MCP（stdio）│
│ 文本 RAG     │ │ 工作区 /     │ │ core/agent/subagent.py     │
│              │ │ TaskRunner   │ │ 单层只读 fan-out           │
└──────────────┘ └──────────────┘ └────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ 评测 / 实验 / 可观测层                                        │
│ core/quality/      行为评测 + outcome + gate + 公开集 + 失败集│
│ core/benchmarks/   8 来源 320 条 catalog + 适配器              │
│ core/experiments/  优化循环 + 触发率 + planner A/B            │
│ core/observability/ trace + token budget + 成本/时延报告      │
└──────────────────────────────┬───────────────────────────────┘
                               │ 读写
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ 数据 / 产物                                                   │
│ data/     知识库 / 评测集 / 本地 BGE / Chroma / SQLite / 工作区│
│ outputs/  报告 / trace / cost_report / outcome（gitignored）  │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. 目录树（带职责注释）

```text
my_agent_harness/
├─ app_agent.py                  # Agent 控制台入口（Streamlit）
├─ app_rag.py                    # 旧 RAG 聊天入口（兼容层）
├─ test_entry.py                 # 兼容 CLI（委托给 core.quality.runner）
├─ pytest.ini
├─ requirements.txt
│
├─ config/                       # YAML 配置，不放业务逻辑
│  ├─ rag.yml                    # 模型 / 本地 BGE / 检索参数
│  ├─ chroma.yml                 # Chroma / 切分 / 文档类型
│  ├─ rag_prompts.yml            # RAG 摘要提示词
│  └─ observability.yml          # trace 目录 / 示例单价
│
├─ core/
│  ├─ agent/                     # 【Harness 层】不 import 任何业务场景
│  │  ├─ framework.py            # FrameworkAgent：create_agent + 中间件 + invoke/stream/resume
│  │  ├─ contracts.py            # Scenario dataclass：框架与场景的唯一契约
│  │  ├─ middleware/
│  │  │  ├─ generic.py           # 监控 / 参数校验 / 步数限制 / 模型前日志
│  │  │  ├─ policy.py            # 工具权限 / 超时
│  │  │  ├─ budget.py            # 单次 run token 预算
│  │  │  └─ planning.py          # 确定性 planning policy（首轮注入 + abstain）
│  │  ├─ hooks.py                # UserPromptSubmit / PreToolUse / PostToolUse / Stop / Task*
│  │  ├─ subagent.py             # 单层子 Agent：fresh context + 白名单 + 预算 + 超时
│  │  ├─ workflow.py             # WorkflowRuntime：执行 Scenario 提供的 LangGraph
│  │  └─ checkpoint.py           # InMemorySaver / SqliteSaver
│  │
│  ├─ tools/
│  │  ├─ business/tools.py       # 智能硬件客服 mock 工具（天气/定位/用户/记录/重置）
│  │  └─ rag/                    # 文本 RAG：embedding / Chroma / BM25 / service / tools
│  │
│  ├─ runtime/                   # 【运行时扩展】不依赖 core.agent
│  │  ├─ tasks.py                # SQLite 任务图：状态 / owner / blocked_by
│  │  ├─ task_tools.py           # create/list/get/claim/complete/fail
│  │  ├─ workspace.py            # read/write/edit/glob/grep/run_command + 路径保护
│  │  ├─ runner.py               # TaskRunner：认领 → 跑 Agent → 完成/失败 → 解锁下游
│  │  └─ config.py               # RuntimeConfig / SubagentConfig
│  │
│  ├─ mcp/                       # 【协议层】只有 mcp_demo 场景 import
│  │  ├─ client.py               # MultiServerMCPClient（stdio）
│  │  ├─ fetch_server.py         # 本地 FastMCP Fetch server
│  │  └─ runner.py               # async MCP 工具 → 同步 LangChain 工具
│  │
│  ├─ scenarios/                 # 【场景层】8 个场景 + registry
│  │  ├─ registry.py             # get_scenario(name)
│  │  ├─ router/                 # 4 个 route_to_*，默认控制台入口
│  │  ├─ workspace_assistant/    # 办公/学习/内容/跨语言，9 工具 + 4 工作流
│  │  ├─ research_assistant/     # 多源研究，只读 fan-out + deep_research
│  │  ├─ coding_demo/            # 文件/命令/任务图/subagent
│  │  ├─ robot_vacuum/           # 模拟智能硬件客服，7 工具 + 2 工作流
│  │  ├─ mcp_demo/               # Memory + Fetch MCP
│  │  ├─ structured_demo/        # Pydantic ReportSchema
│  │  └─ general/                # 无业务工具的基线
│  │
│  ├─ quality/                   # 【评测层】
│  │  ├─ agent_eval.py           # 行为评测：44 条 cases，支持 --trials
│  │  ├─ outcome_eval.py         # outcome 评测：文件/SQLite/任务图/路由 trace
│  │  ├─ metrics.py              # 关键词覆盖 / 工具命中 / 拒答
│  │  ├─ judge.py                # LLM-as-judge
│  │  ├─ gate.py                 # 读报告 + 阈值断言
│  │  ├─ structured_eval.py      # 结构化输出 schema 评测
│  │  ├─ bfcl_simplified.py      # BFCL 抽样 + 简化评分
│  │  ├─ public_sample.py        # RGB / MultiHop 抽样
│  │  ├─ multihop_full.py        # MultiHop 全量检索
│  │  ├─ failures.py             # 失败集归档
│  │  └─ runner.py               # 统一 CLI：agent / outcome / rag / public / bfcl / structured / gate
│  │
│  ├─ benchmarks/                # 【基准层】catalog / 适配器 / 分层抽样
│  ├─ experiments/               # 【实验层】optimize / trigger_rate / planner_eval
│  ├─ observability/             # 【可观测层】tracer / budget / cost_report / trace_report
│  ├─ interfaces/                # 【界面层】CLI / Streamlit / dashboard / workflow_cli
│  ├─ llm/factory.py             # 模型 provider 抽象（DeepSeek / DashScope）
│  ├─ utils/                     # 配置 / 日志 / 文件 / 路径
│  └─ tests/                     # 演示脚本（HITL / memory / token budget），不是 pytest
│
├─ data/                         # 数据，不放代码
│  ├─ knowledge/                 # 智能硬件客服知识库
│  ├─ evals/datasets/            # 42 条历史业务集 + RGB 20 + MultiHop 12
│  ├─ benchmarks/                # 320 条 catalog + manifest
│  ├─ models/                    # 本地 BGE（gitignored）
│  ├─ runtime/                   # Chroma / SQLite / 工作区 / 日志（gitignored）
│  ├─ workspace_assistant/notes/ # 办公助手 seed 笔记
│  └─ research_assistant/sources/# 研究资料
│
├─ docs/                         # 项目文档
│  ├─ PROJECT.md                 # 边界 / 能力 / 不做什么
│  ├─ ARCHITECTURE.md            # 本文件
│  ├─ benchmarks/                # 结果总览 / 优化循环 / P0
│  ├─ design/                    # 优化方向全景
│  └─ interview/                 # JD 对齐 / 简历 / 面试包 / Q&A
│
├─ outputs/                      # 生成物（gitignored）
│  ├─ agent/  rag/  public/  bfcl/  tau2/
│  ├─ structured/  outcome/  experiments/
│  ├─ traces/  cost_report.json
│  └─ demo/                      # 优化循环报告
│
├─ tests/                        # 76 项 pytest（确定性，不调真实模型）
└─ README.md
```

---

## 3. 模块职责表

| 层 | 目录 | 负责 | 不负责 |
|---|---|---|---|
| 界面 | `core/interfaces/` | CLI、Streamlit、三产品控制台（对话 / 构建 / 质量；`console/`）、工作流 CLI | 业务工具、评测逻辑 |
| Harness | `core/agent/` | ReAct 运行时、中间件编排、Scenario 契约、subagent、workflow runtime、checkpoint | 具体业务工具、UI、评测 |
| 场景 | `core/scenarios/` | 8 个场景的模型/提示词/工具/权限/预算/工作流/用例 | 运行时内部实现 |
| 工具 | `core/tools/` | 业务 mock 工具 + 文本 RAG | Agent 循环、权限 |
| 运行时 | `core/runtime/` | 任务图、工作区文件/命令、TaskRunner、hooks 配置 | 模型调用 |
| MCP | `core/mcp/` | MCP client、Fetch server、async→sync 包装 | Agent 决策 |
| 评测 | `core/quality/` | 行为/outcome 评测、metrics、gate、结构化、公开集、失败集 | 模型定义 |
| 基准 | `core/benchmarks/` | 8 来源 catalog、分层抽样、适配器 | 大部分 adapter 是数据/目录层，不是端到端执行 |
| 实验 | `core/experiments/` | 优化循环、触发率、planner A/B | 生产调度 |
| 可观测 | `core/observability/` | trace、token budget、成本/时延报告 | 评分逻辑 |
| 模型 | `core/llm/` | provider 抽象 | 提示词、工具 |
| 配置 | `config/` | YAML 参数 | 代码 |
| 数据 | `data/` | 知识库、评测集、模型、运行时状态 | 代码 |
| 产物 | `outputs/` | 报告、trace、成本 | 源码 |

---

## 4. 一次请求的调用链

```text
用户问题
  │
  ▼
界面（Streamlit / CLI）
  │  选择 Scenario，构造 FrameworkAgent
  ▼
FrameworkAgent.invoke(query, thread_id)
  ├─ UserPromptSubmit hooks（可改写 query）
  ├─ RunBudget + TraceCallbackHandler
  ├─ create_agent 图开始
  │   ├─ PlanningPolicy（可选）：首轮命中唯一规则 → 注入 tool_call → jump_to tools
  │   ├─ before_model 中间件：Todo / Summarization / PII / 步数 / token 预算
  │   ├─ 模型决定：调用工具 or 最终回答
  │   ├─ 工具执行链：权限 → HITL → 超时 → 重试 → 错误回注
  │   ├─ 工具结果回到模型，继续循环
  │   └─ Stop hooks / trace finalize
  ▼
返回消息 / structured_response
  │
  ├─ 行为评测：回答关键词 + 工具名
  ├─ outcome 评测：文件 / SQLite / 任务图 / 路由 trace
  └─ Dashboard：trace 时间线 / 成本 / 失败下钻
```

---

## 5. Scenario 包的标准结构

每个场景是一个独立包，新增场景不改运行时：

```text
core/scenarios/<name>/
├─ __init__.py
├─ scenario.py          # build_scenario(): model / prompt / tools / policy / budget / checkpoint
├─ tools.py             # 场景工具
├─ graph.py             # LangGraph 工作流（可选）
├─ cases.jsonl          # 行为用例（id / question / expected_points / expected_tools）
└─ outcome_cases.jsonl  # outcome 用例（question_template + checks）
```

注册：在 `core/scenarios/registry.py` 加一个 builder，`get_scenario(name)` 即可。

---

## 6. 8 个场景与 7 条工作流

| 场景 | 定位 | 工具 / 工作流 | 用例 |
|---|---|---|---|
| `router` | 对话式前台，场景级分发 | 4 个 `route_to_*` | 4 行为 + 4 outcome |
| `workspace_assistant` | 办公/学习/内容/信息管理/跨语言 | 9 工具；`document_qa` / `study_notes` / `cross_lingual` / `content_draft` | 5 行为 + 3 outcome |
| `research_assistant` | 多源研究、只读 fan-out | 5 工具（含 `subagent`）；`deep_research` | 3 行为 + 3 outcome |
| `coding_demo` | 编码运行时 | 文件/命令/任务图/subagent | 7 行为 + 2 outcome |
| `robot_vacuum` | 模拟智能硬件客服 | 7 工具；`rag_qa` / `report` | 13 行为 |
| `mcp_demo` | MCP 演示 | Memory + Fetch（stdio） | 3 行为 |
| `structured_demo` | 结构化输出 | Pydantic `ReportSchema` | 5 行为 |
| `general` | 无业务工具基线 | Harness 本身 | 4 行为 |

工作流合计 **7 条**：robot 2 + workspace 4 + research 1。
评测合计：**44 条行为用例 + 12 条 outcome 用例 / 13 个断言**。

---

## 7. 依赖方向与边界

```text
scenarios ──→ agent.contracts ←── agent
     │                              │
     ├──→ tools / runtime / mcp     │
     └──→ quality / experiments     │
interfaces ──→ agent / scenarios / quality / observability
```

- `core/agent` 不 import 任何具体业务工具或场景；`tests/test_scenario_separation.py` 强制这条边界。
- `core/runtime` 不依赖 `core/agent`，场景按需组合。
- `core/mcp` 只被 `mcp_demo` 场景 import；其他场景不依赖 MCP。
- `core/quality` 依赖 Harness 和场景，但不反向被依赖。
- `core/benchmarks` 的适配器多数是数据/目录层，只有 BFCL/公开集部分真正执行。

---

## 8. 架构文档入口

- 本文件：完整目录树 + 职责 + 调用链。
- `docs/PROJECT.md`：能力边界、不做什么、AgentGuide 对照。
- `core/runtime/README.md`：任务图 / 工作区 / hooks / subagent 的运行时细节。
- `README.md`：快速开始、场景矩阵、评测入口。
- Dashboard「架构」视图：运行时渲染工具、中间件顺序、LangGraph 图，并带 `module:line`，可作为“活架构树”。

---

## 9. 一句话记忆

```text
界面选场景 → Harness 跑 ReAct → 场景给工具/工作流 → 工具执行 → trace/评测 → dashboard 下钻
```
