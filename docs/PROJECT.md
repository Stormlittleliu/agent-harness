# 项目边界与总结：Agent Harness

> 一句话：**模型只负责决策，Harness 负责工具、上下文、状态、权限、预算和评测。**

## 1. 项目是什么

一个**个人项目**，单进程、单 Agent、工具调用型 Agent Harness，包含：

- ReAct 运行时与中间件；
- 7 个业务工具 + 本地 RAG；
- 权限、HITL、超时、重试、错误回注、步数/调用上限、上下文压缩、PII、token 预算；
- LangGraph checkpoint / 多轮记忆 / 中断恢复；
- LangGraph 工作流：检索问答、报告生成；
- 两层评测：工具层 / 行为层；
- 公开 benchmark 适配层：8 个来源、320 条统一样例；
- 最小优化循环：跑 → badcase 归因 → 定向改 → 复跑 → 查回归；
- 运行时扩展：hooks、SQLite 任务图（blocked_by 依赖）、文件读写 / 编辑 / glob / grep / 命令执行、运行窗口、单层 subagent；
- 结构化输出：`Scenario.response_format` → `create_agent` → Pydantic `ReportSchema`，评测直接读 `structured_response`；
- 成本 / 时延报告：聚合 trace 的成功率、p50/p95、token、估算成本；
- 评测门禁 + 故障注入：BFCL / MultiHop / coding / structured 阈值断言，超时 / 权限 / 参数 / 空检索 / 拒答；
- 触发率实验：natural / routed / policy 三版下 subagent 与任务工具的使用率；
- **确定性 planning policy（2026-11-02）**：`before_model` 按规则注入 `route_to_*` /
  `subagent` / `create_task`，不命中或平局 abstain；router 12 条路由 12/12，coding
  eligible 3/10 → 3/3；
- **outcome 评测（2026-11-02）**：12 条文件 / SQLite / 任务图 / 路由 trace 断言，区分
  transcript 与 outcome；
- **新场景 3-trial 行为回归（2026-11-02）**：workspace 5/5、research 2/3、router 3/4；
- 7 个功能视图 + 总览工作台的 Streamlit 控制台（侧边栏单视图渲染）：架构、任务、测试、评测（场景报告 + 成本/时延 + 公开基准 + 记录）、复核（judge + 人工标注）、优化循环、Benchmark 目录；`coding_demo` 另有运行窗口。总览是工作台入口，不会一次性加载全部页面；测试用例详情提供“对象链路”，可从案例定位到工具/中间件/评测函数/trace 的具体源码位置。

验证场景包括**办公 / 学习 / 内容 / 跨语言助手、研究调研、编码运行时、模拟智能硬件客服**，
不是真实业务系统。

## 2. 项目不是什么

| 不是 | 说明 |
|:---|:---|
| 不是模型 | 没有训练、微调、推理优化；模型是 DeepSeek API |
| 不是生产服务 | 没有 API/鉴权/限流/并发/高可用/部署 |
| 不是真实客服系统 | 工具、用户、使用记录、设备重置都是 mock |
| 不是官方榜单成绩 | BFCL / τ² / RGB / MultiHop 都是抽样或简化评分 |
| 不是多 Agent 平台 / MCP 网关 | 有 stdio MCP client（Memory + Fetch）与单层 subagent；没有 handoff、多 Agent 治理、HTTP/SSE/auth 网关 |
| 不是多模态 Agent | 没有语音、图像、OCR、端侧推理 |
| 不是安全沙箱 | `run_command` 是进程内 shell，只做字符串拒绝，没有容器隔离 |
| 不是分布式任务队列 | 任务是单机 SQLite 任务图，没有 worker/锁/重试队列 |
| 不是长期记忆系统 | 有 checkpoint 短期状态 + workspace 场景级 SQLite key-value 偏好；没有用户画像、向量语义记忆、巩固/冲突消解 |

## 3. 边界：四层

### 3.1 能力边界

```text
有：单 Agent、工具调用、RAG、状态、权限、预算、工作流、评测、trace
有：MCP client（stdio，Memory + Fetch）
有：hooks、SQLite 任务图、read_file / write_file / edit_file / glob / grep / run_command、运行窗口、单层 subagent
有：结构化输出（Pydantic response_format）、成本 / 时延报告、评测门禁
有：确定性 planning policy、12 条 outcome 用例 / 13 个断言、新场景 3-trial 回归
有：workspace 场景级 SQLite 长期偏好（key-value）
无：多 Agent handoff / supervisor、多模态、沙箱、分布式任务队列、用户画像/向量语义记忆、在线学习
```

### 3.2 数据边界

```text
有：公开 benchmark 的本地副本 / 抽样；模拟客服数据；本地 BGE + Chroma
无：真实用户流量、真实工单、生产知识库、业务 KPI
```

### 3.3 评测边界

```text
有：pass^k、3 trial、工具/行为两层、公开 benchmark 抽样、失败集
有：可编程门禁（阈值断言）、5 类故障注入、结构化输出 schema 评测
无：5–10 trial、bootstrap CI、官方 scorer、human calibration、CI 平台接入
```

### 3.4 工程边界

```text
有：单进程、SQLite checkpoint、本地 trace、Streamlit 控制台
无：服务化、并发、鉴权、限流、容器、监控告警
```

## 4. 对照 AgentGuide

| AgentGuide 原则 | 本项目状态 |
|:---|:---|
| Agent = Model + Harness | 已分开：BFCL/τ² 是模型能力；自建机制/回归是 Harness |
| Task / Trial / Grader / Transcript / Outcome | 有 Task/Trial/Grader/Trace；新增 12 条 outcome 用例 / 13 个断言（文件 / SQLite / 任务图 / 路由 trace），未接 CI |
| Capability vs Regression | 320 条 catalog 是 capability；13 条自建是 regression；demo 60/45 混合 |
| Code-based → LLM judge → human | 有 code-based + DeepSeek judge；没有人工校准 |
| 150 task benchmark | 320 条 catalog，但真正跑过的只有 60/45 demo；大量来源未执行 |
| 5–10 trial + CI | 目前 3 trial，没有置信区间/CI 门禁 |
| 三层质量门 / 四级 Ship Gate | 有离线 gate + 故障注入；没有 shadow / A/B / 灰度 |
| 读 transcript | 有 trace 时间线和失败分析，但没有固定“每次读 15 条”的流程 |
| Eval 是 living artifact | 有失败集、优化循环和 gate；未接 CI 平台 |

## 5. 可讲 / 不可讲

### 可以讲

- 用 LangChain + LangGraph 实现了通用 ReAct Harness 和中间件编排；
- 工具、状态、权限、预算、记忆、工作流、评测是分开的；
- 有两层评测和失败集，能定位“改完是变好还是变坏”；
- hybrid 检索在 45 条 MultiHop 抽样上把 RAG 从 40/45 提到 44/45，0 回归；
- Python 语法提示把 BFCL 60 条抽样从 55/60 提到 59/60，组合配置两轮 60/60；
- 公开 benchmark 数字都带“抽样 / 简化评分 / 非官方 judge”；
- 接了外部 MCP：Memory（跨会话记忆）+ Fetch（网页读取），async 工具包装成同步 LangChain 工具；
- 用确定性 planning policy 把“模型自发委派 0/10”变成可测策略：router 12/12（baseline 11/12），
  policy eligible 3/10 → 3/3；不命中/平局 abstain，交回模型；
- 新增 12 条 outcome 用例 / 13 个断言：文件、SQLite、任务图、路由 trace；新场景 3-trial：
  workspace 5/5、research 2/3、router 3/4；
- 补了 hooks、SQLite 任务图、文件读写 / 编辑 / 搜索 / 命令执行、运行窗口和单层 subagent；运行时按场景配置；
- 用 `create_agent(response_format=...)` + Pydantic 做结构化报告，5 条跨场景用例 schema 合法 5/5；
- 把 3203 条 trace（历史快照）聚合成成本 / 时延报告：成功率 98.3%，p50 2.50s，p95 8.54s，约 ¥0.015/run（示例价）；最新 3495 条聚合含故意失败用例与实验，以 `outputs/cost_report.json` 为准；
- 评测门禁覆盖 BFCL / MultiHop / coding / structured，另有 5 类故障注入；
- 触发率实验显示：10 条自然任务中 subagent / 任务工具触发 0/10；加确定性 policy 后
  eligible 3/10 全部触发，7/10 保持不委派。

### 不可以讲

- “BFCL 官方 100%”；
- “τ² 测的是我的 Harness”——τ² 跑的是它自己的 LLMAgent；
- “真实客服系统 / 线上用户 / 业务指标”；
- “多 Agent / 生产级 MCP 网关 / 多模态 / 沙箱”；
- “RAG 42 条是扫地机器人结果”——它是服装域历史数据。

## 6. 交付物

```text
core/agent/            # Harness
core/tools/            # 业务工具 + RAG
core/runtime/          # 任务图 / 工作区 / TaskRunner（hooks 在 core/agent/hooks.py）
core/scenarios/        # router / workspace_assistant / research_assistant / coding_demo / general / mcp_demo / robot_vacuum / structured_demo
core/interfaces/       # CLI / Streamlit / 6 功能视图 + 总览工作台
core/quality/          # 两层评测 + outcome / 公开基准 / 失败集 / 门禁 / 结构化评测
core/observability/    # trace + token budget + 成本时延报告
core/mcp/              # MCP client + Fetch server
core/benchmarks/       # 8 个公开 benchmark 适配器
core/experiments/      # 最小优化循环 + 触发率 + planner A/B
tests/                 # pytest：runtime / workspace / metrics / dashboard / 故障注入
data/benchmarks/       # 320 条统一样例
docs/benchmarks/       # 结果总览 / 复盘
```

## 7. 最终结论

> 这是一个**可运行、可评测、可定位失败的单机 Agent Harness**，不是模型、不是生产服务、不是官方榜单。
> 它的价值在于：把“Agent 好不好”拆成工具、状态、权限、预算、检索、评测六件事，并且能用同一批 case 证明改动是否有效。

## 8. 后续方向（不纳入当前冻结）

- planner 语义化 / 学习化（当前是规则级确定性 policy）；
- 官方 BFCL scorer / τ² adapter；
- MCP HTTP/SSE、认证、多 server 治理、prompt-injection 分类器；
- outcome 断言接入 CI 平台（当前是本地 CLI）；
- 5–10 trial + bootstrap CI；
- 后台任务 / 定时调度 / 多 worker；
- rerank / 查询改写；
- 服务化、并发、鉴权、沙箱、长期记忆。

## 9. 当前边界（v0.2，2026-11-02 面试增补）

本仓库当前冻结为 **v0.2（单机、单 Agent、可评测 + 可路由的 Harness）**。v0.2 在 v0.1
基础上只补了三件事：确定性 planning policy、12 条 outcome 用例 / 13 个断言、新场景 3-trial 回归。
到此为止不再新增能力；后续只做 bugfix、文档修正和评测口径校准；新方向另开分支或仓库。

**纳入本边界**

- 单进程、单 Agent 的 ReAct Harness 与中间件；
- 7 个 mock 业务工具 + 本地 RAG（BGE / Chroma / BM25）；
- 8 个场景：router / workspace_assistant / research_assistant / robot_vacuum / mcp_demo / coding_demo / general / structured_demo；
- 两层评测、公开 benchmark 抽样、失败集、优化循环、阈值门禁、5 类故障注入；
- trace / token 预算 / 成本时延报告；
- MCP stdio（Memory + Fetch）、hooks、SQLite 任务图、workspace 工具、运行窗口、单层 subagent；
- **v0.2**：确定性 planning policy（router 12/12；coding eligible 3/10 → 3/3）、
  12 条 outcome 用例 / 13 个断言、新场景 3-trial 回归；
- 6 功能视图 + 总览工作台（侧边栏单视图渲染；评测页合并了场景报告 / 成本时延 / 公开基准 / 记录；coding_demo 多一个运行窗口）。

**不纳入本边界**

- 多 Agent handoff / supervisor / 多 Agent 治理（只读 fan-out 纳入）；
- 多模态、语音、OCR、端云协同、端侧推理；
- 生产级 MCP 网关（HTTP/SSE/auth）、容器沙箱、服务化、鉴权、限流、高可用；
- 官方 BFCL / τ² 分数、真实客服流量、业务 KPI、长期用户画像；
- planner 的语义化/学习化——v0.2 只做规则级确定性 policy；
- 5–10 trial + bootstrap CI、CI 平台接入。

**为什么现在冻结**

- v0.1 已把“能跑、能评、能看成本、能定位回归”补到可讲的程度；
- v0.2 只补了 planning policy、outcome、新场景回归，把“行为不可靠”变成可测边界；
- 再往上（语义 planner、CI、multi-agent、多模态）是另一个能力层，不应混进当前叙事；
- 冻结边界能让面试口径稳定：**强项讲透，缺口明确，不用硬凑关键词。**
