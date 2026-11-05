# 项目演进：从 RAG 到带评测的 Agent Harness

> 定位：个人项目 / 作品集叙事。
> 数字口径以 `docs/design/scope-freeze-2026-11-05.md` 为准；本文不引用冻结文档之外的“更好看”数字。
> 项目已冻结：之后只修 bug、补文档、改口径，不再加功能或扩评测边界。

## 1. 一句话定位

这是一个**带评测、结构可编辑的单机 Agent Harness**：模型负责决策，框架负责工具、上下文、状态、权限、预算和证据。

它**不是**模型、不是生产平台、不是多 Agent 平台，也不是官方 benchmark 榜单成绩。它是把“RAG 工具 → Agent 循环 → Harness 约束 → 评测闭环 → spec 化编辑”这条演进链走通的一个个人工程样本。

证据：`docs/PROJECT.md:5-45` 把“是什么 / 不是什么”写成了两张表；`docs/design/scope-freeze-2026-11-05.md:30-37` 列了明确不做的边界。

## 2. 演进线：每一阶段都是被上一个阶段的问题逼出来的

### 2.1 RAG：先有“能检索”，但它只是工具

**遇到的问题**：RAG 能回答知识库问题，但检索本身不会决定“什么时候该查、查完怎么用”；它只是被动能力。

**做了什么**：保留基础项目的解析、切片、MD5 去重、Chroma 持久化与混合检索，把 RAG 收成一个 Agent 工具；后来补了 domain/category 元数据过滤、服装语义取样，以及 100问/故障排除/选购指南/维护保养的 FAQ 编号切块。

**取舍**：不重写 RAG 底座，而是复用并把它变成可编排能力；代价是知识库规模仍然很小，当前 **835 chunks**，只适合演示与回归，不代表领域全量。

证据：`core/tools/rag/`、`data/knowledge/`、`docs/design/rag-knowledge-classification.md`；冻结数字见 `docs/design/scope-freeze-2026-11-05.md:13,28`。

### 2.2 Agent：从“检索工具”到“会选工具、会恢复”

**遇到的问题**：模型会调用工具，但会参数错、工具超时、重复调用；一旦抛异常，整个 run 就断。

**做了什么**：用 LangChain `create_agent` 起 ReAct 循环，补工具参数校验、错误重注入、重试、超时、步数/调用上限、HITL 审批、checkpoint 多轮记忆。核心原则是：**错误是 observation，不是崩溃**——参数非法返回一条 `status="error"` 的 ToolMessage，让模型下一轮自己改。

**取舍**：不手写 ReAct 循环，复用 `create_agent`，把精力放在约束和恢复上；代价是运行时行为受 LangChain 中间件语义约束，复杂控制要写成策略而不是任意代码。

证据：`core/agent/framework.py`、`core/agent/pipeline.py`、`core/agent/middleware/`。

### 2.3 Harness：功能变多后，先解决“框架和业务缠在一起”

**遇到的问题**：场景一多，模型、提示词、工具、权限、评测用例全缠在场景目录里；加一个业务要改运行时，边界靠自觉。

**做了什么**：定 `Scenario` 契约，把业务差异压成模型 / 提示词 / 工具 / 中间件 / context / cases 几组字段；运行时按契约装配，场景只实现 `build_scenario()` 并注册。中间件改成固定 slot + 顺序不变量，避免调用方随意拖拽。

**取舍**：不是“所有场景都塞进一个万能 Agent”，而是保留场景隔离；`core/agent` 不 import 任何业务工具，这条边界用 `tests/test_scenario_separation.py` 守住。代价是场景之间不能随便共享状态，跨场景要靠 router 或显式工具。

证据：`core/agent/contracts.py`、`core/scenarios/registry.py`、`core/agent/pipeline.py:39-65`。

### 2.4 评测：功能存在，不代表会被触发

**遇到的问题**：加了很多能力，但日常很难让 Agent 自己 plan / 开 subagent；改完 prompt 或工具，也说不清是变好还是变坏。

**做了什么**：从“看回答”转到三层证据：

- **capability**：直接调工具，看检索/生成本身；
- **behavior**：跑完整 Agent，看工具选择、传参、多步、拒答；
- **outcome**：跑完看环境，文件、SQLite、任务图、路由 trace，不看回答文本。

配套 pass^k、故障注入、任务级 fixture 和失败集。最典型的一次对照：router 行为层 3/4，outcome 层 4/4——回答措辞判失败，但路由目标和 trace 都对，说明“transcript 会撒谎，outcome 不会”。

**取舍**：不追求大而全的官方榜单，改用小样本、可解释的 fixture 矩阵；代价是样本小、没有统计显著性，BFCL 只是抽样 + 简化评分。

证据：`core/quality/agent_eval.py`、`core/quality/outcome_eval.py`、`core/quality/fixtures.py`、`docs/benchmarks/eval-traceability.md`。

### 2.5 spec / 低代码：让“场景结构”可编辑，但不假装能编辑一切

**遇到的问题**：场景结构写在代码里，控制台只能看不能改；想加分支/改路由必须改 Python，演示和迭代都重。

**做了什么**：把 11 个场景的结构迁到 `data/specs/<name>/`，由 `spec.py` 校验并编译成 LangGraph；控制台提供画布 + 表单编辑，支持多路 `branch`（`cases` + `default`）和条件边；发布走 `entry.yml`，对话端只认已发布入口。

**取舍**：spec 只表达“能 schema 化的结构”，不追求任意图/任意 Python。表达不了就 eject 回代码；画布回传一律当不可信输入，必须过 `merge_canvas`。branch 也不是任意表达式，而是“按顺序匹配关键词 + default”，编译器会校验“branch 可能写出的 route 必须有对应条件边”。

证据：`core/scenarios/spec.py:282-300`、`core/scenarios/spec_nodes.py:614-640`、`core/interfaces/dashboard/editor.py`、`data/specs/*/entry.yml`；冻结范围见 `docs/design/scope-freeze-2026-11-05.md:11-12`。

## 3. 大致结构：5 层与依赖方向

| 层 | 目录 | 职责 |
|---|---|---|
| 接口层 | `core/interfaces/` | Streamlit 控制台（对话 / 构建 / 质量）、CLI、工作流 CLI |
| 场景层 | `core/scenarios/` + `data/specs/` | 场景结构、工具、工作流、行为/outcome 用例；spec 是权威 |
| 运行时层 | `core/agent/` | `FrameworkAgent`、`Scenario` 契约、中间件流水线、HITL、checkpoint、trace |
| 能力层 | `core/tools/`、`core/runtime/`、`core/mcp/` | 业务 mock 工具、RAG、任务图/工作区、MCP client、单层 subagent |
| 质量层 | `core/quality/`、`core/benchmarks/`、`core/experiments/`、`core/observability/` | 三层评测、fixture、catalog、优化实验、trace/成本 |

依赖方向：

```text
interfaces ──→ agent / scenarios / quality / observability
scenarios  ──→ agent.contracts ←── agent
      ├──→ tools / runtime / mcp
      └──→ quality / experiments
```

关键不是“分了几层”，而是**方向不能反**：`core/agent` 不 import 具体业务工具；`core/quality` 依赖 Harness 和场景，但不被场景反向依赖；`core/benchmarks` 多数是数据/目录层，不是执行层。

证据：`docs/ARCHITECTURE.md:8-58,254-268`；`tests/test_scenario_separation.py`。

## 4. 关键实现技术

### 4.1 Scenario 契约

`Scenario` 把业务差异收成几组字段：身份/模型、Harness 开关、权限与容错、工作流/输出、扩展。新增业务 = 新目录 + `build_scenario()` + 注册，运行时一行不改。

### 4.2 中间件顺序

`pipeline.py` 用 slot 固定顺序，不是调用方随意拼：

- 权限最外：deny 的工具不进审批、不进超时、不执行；
- HITL 在超时外：人思考的时间不算工具耗时；
- `error` 在 `retry` 外：重试耗尽后才把异常转成 error ToolMessage；
- planning 在 todo 前：先决定是否委派，再进入常规流程。

不变量写在 `core/agent/pipeline.py:59-65`，UI 的中文说明直接读 `POLICY_DOCS`，避免文档漂移。

### 4.3 HITL

高风险工具通过 `high_risk_tools` 触发 `HumanInTheLoopMiddleware`，用 LangGraph checkpoint 中断；恢复时发 `Command(resume=...)`，批准/拒绝都走真实中断，不是伪造。

### 4.4 spec + branch

- spec 是数据，编译前 `validate_spec` 检查节点、参数、端口、可达性、条件边；
- branch 支持多路 `cases` + `default`，旧版 `hit/miss` 兼容；
- 编译期校验：branch 可能写出的 route 必须都有条件边，反之条件边标签必须是 branch 的输出。

### 4.5 trace

`TraceCallbackHandler` 把模型/工具/token/时延写成按天 JSONL；每条事件带 `node`，报告里的 `trace_id` 可以回到具体事件。`docs/benchmarks/eval-traceability.md` 记录了 workspace 15/15、planner 24/24、outcome 40/40 的回查结果。

### 4.6 三层评测与 fixture

- behavior：`cases.jsonl` + `pass^k`；
- outcome：文件 / SQLite / 任务图 / 路由 trace 断言；
- fixture：按任务配工具，`clean / distractor / missing / failure / permission` 变体，不注册产品场景。

冻结时的数字：**408 passed**；selfbuilt **26/26（1-trial）**；新场景 3-trial `clothing_service` **6/6**、`retail_router` **5/5**；workspace **5/5**（11/02 快照）；planning policy **12/12**（baseline 11/12）；outcome **12/12**（13/13 断言）；BFCL fixture 矩阵 **32/40**（missing **2/10**）；catalog **11 来源 / 132 条**；知识库 **835 chunks**。

## 5. 与其它开源项目的区别

只按定位对比，不比较未验证的功能细节。

| 项目 | 它主要是什么 | 本项目与它的关系 |
|---|---|---|
| LangChain / LangGraph | Agent/图运行时与集成库 | 本项目**使用**它们（`create_agent` + LangGraph），不是替代；额外做 Scenario 契约、中间件顺序、spec 归属与评测闭环 |
| Dify / Coze | 产品化的低代码/托管 Agent 平台 | 本项目是单机、代码优先的个人 Harness；有画布/表单，但没有托管、多租户、连接器市场与生产发布 |
| Inspect AI | 评测框架（scorer / metric / reducer 思路） | 本项目借用“评分分层”的思路，把评测嵌进 Harness；评测生态和样本规模远不如它成熟 |
| LangSmith | 托管 trace / 评测平台 | 本项目用本地 JSONL trace + 离线报告，没有托管 UI、协作与云端留存 |
| learn-claude-code 类项目 | 能力清单/工程实践参考 | 本项目参考其工具、权限、上下文、记忆、错误恢复的能力面，但不是复刻产品 |

一句话：**别人提供运行时或平台，我在运行时之上补“场景契约 + 约束顺序 + 可追溯评测 + 受约束的结构编辑”。**

## 6. “不能这么说”的边界

- 不说“生产级 / 高可用 / 多租户 / 已部署”：没有 API、鉴权、限流、并发、高可用与部署。
- 不说“多 Agent 平台”：只有单层只读 fan-out，没有 handoff、多 Agent 治理。
- 不说“官方榜单成绩”：BFCL 是抽样 + 简化评分；τ² 跑的是官方 harness，不是本项目 Harness。
- 不说“真实客服 / 线上用户 / 业务 KPI”：工具、用户、设备、订单都是 mock。
- 不说“多模态 / 语音 / OCR / 端侧 / 安全沙箱”：都没有实现。
- 不说“300 条 benchmark 全量跑通”：catalog 是目录数据，真正执行的只有部分能力层/外部 harness。
- 不说“26/26 是稳定结论”：这是 1-trial；新场景 3-trial 也是小样本，不做统计显著性声明。
- 不说“835 chunks 代表知识库质量”：它只是当前索引规模，重建成本与检索延迟也随之上来。

证据：`docs/PROJECT.md:33-45,119-125`；`docs/design/scope-freeze-2026-11-05.md:30-37`。

## 7. 给面试官的三句话

1. **“这是一个把 RAG 工具收进 Agent、再用 Harness 约束和评测的个人项目：模型负责决策，框架负责工具、上下文、权限、预算和证据。”**
2. **“我能讲清一次 run 的完整链路，也能用 behavior / outcome / fixture 说明改动有没有用；最值钱的是 outcome 和 trace 的可追溯，不是某个好看的分数。”**
3. **“它的边界同样清楚：单机、单 Agent、小样本、非官方榜单；我讲的是机制和评测闭环，不是生产平台。”**
