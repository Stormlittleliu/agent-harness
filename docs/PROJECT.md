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
- 运行时扩展：hooks、SQLite 任务图（blocked_by 依赖）、文件读取 / glob / 命令执行、运行窗口、单层 subagent；
- 结构化输出：`Scenario.response_format` → `create_agent` → Pydantic `ReportSchema`，评测直接读 `structured_response`；
- 成本 / 时延报告：聚合 trace 的成功率、p50/p95、token、估算成本；
- 评测门禁 + 故障注入：BFCL / MultiHop / coding / structured 阈值断言，超时 / 权限 / 参数 / 空检索 / 拒答；
- 触发率实验：natural / routed 两版 prompt 下 subagent 与任务工具的使用率；
- 8 页签的 Streamlit 控制台：架构、任务、测试、公开基准、优化循环、Benchmark 目录、成本时延、评测记录；`coding_demo` 另有运行窗口。

验证场景是**模拟的扫地机器人客服**，不是真实业务系统。

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
| 不是长期记忆系统 | 只有 checkpoint 短期状态；Memory MCP 是外部 demo，不是用户画像系统 |

## 3. 边界：四层

### 3.1 能力边界

```text
有：单 Agent、工具调用、RAG、状态、权限、预算、工作流、评测、trace
有：MCP client（stdio，Memory + Fetch）
有：hooks、SQLite 任务图、read_file / glob / run_command、运行窗口、单层 subagent
有：结构化输出（Pydantic response_format）、成本 / 时延报告、评测门禁
无：多 Agent、多模态、沙箱、分布式任务队列、长期记忆（除外部 Memory MCP 外）、在线学习
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
| Task / Trial / Grader / Transcript / Outcome | 有 Task/Trial/Grader/Trace；Outcome 只有部分（HITL、预算、持久化），未系统化 DB 校验 |
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
- 补了 hooks、SQLite 任务图、文件读取 / 命令执行、运行窗口和单层 subagent；运行时按场景配置；
- 用 `create_agent(response_format=...)` + Pydantic 做结构化报告，5 条跨场景用例 schema 合法 5/5；
- 把 3203 条 trace 聚合成成本 / 时延报告：成功率 98.3%，p50 2.50s，p95 8.54s，约 ¥0.015/run（示例价）；
- 评测门禁覆盖 BFCL / MultiHop / coding / structured，另有 5 类故障注入；
- 触发率实验显示：10 条自然任务中 subagent / 任务工具触发 0/10，说明机制可用但行为不可靠。

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
core/scenarios/        # coding_demo / general / mcp_demo / robot_vacuum / structured_demo
core/interfaces/       # CLI / Streamlit / 8 页签控制台
core/quality/          # 两层评测 / 公开基准 / 失败集 / 门禁 / 结构化评测
core/observability/    # trace + token budget + 成本时延报告
core/mcp/              # MCP client + Fetch server
core/benchmarks/       # 8 个公开 benchmark 适配器
core/experiments/      # 最小优化循环 + 触发率实验
tests/                 # pytest：runtime / workspace / metrics / dashboard / 故障注入
data/benchmarks/       # 320 条统一样例
docs/benchmarks/       # 结果总览 / 复盘
```

## 7. 最终结论

> 这是一个**可运行、可评测、可定位失败的单机 Agent Harness**，不是模型、不是生产服务、不是官方榜单。
> 它的价值在于：把“Agent 好不好”拆成工具、状态、权限、预算、检索、评测六件事，并且能用同一批 case 证明改动是否有效。

## 8. 后续方向（不纳入当前冻结）

- planner / routing：决定何时用 subagent、何时建任务图，而不是只靠 prompt；
- 官方 BFCL scorer / τ² adapter；
- MCP HTTP/SSE、认证、多 server 治理、prompt-injection 分类器；
- outcome 断言 + CI 平台接入（当前 gate 是本地 CLI）；
- 5 trial + bootstrap CI；
- 后台任务 / 定时调度 / 多 worker；
- rerank / 查询改写；
- 服务化、并发、鉴权、沙箱、长期记忆。

## 9. 当前边界（2026-10-31 冻结）

本仓库当前冻结为 **v0.1（单机、单 Agent、可评测的 Harness）**。到此为止不再新增能力；
后续只做 bugfix、文档修正和评测口径校准；新方向另开分支或仓库。

**纳入本边界**

- 单进程、单 Agent 的 ReAct Harness 与中间件；
- 7 个 mock 业务工具 + 本地 RAG（BGE / Chroma / BM25）；
- 5 个场景：robot_vacuum / mcp_demo / coding_demo / general / structured_demo；
- 两层评测、公开 benchmark 抽样、失败集、优化循环、阈值门禁、5 类故障注入；
- trace / token 预算 / 成本时延报告；
- MCP stdio（Memory + Fetch）、hooks、SQLite 任务图、workspace 工具、运行窗口、单层 subagent；
- 8 页签控制台（coding_demo 9 页签）。

**不纳入本边界**

- 多 Agent handoff / 多 Agent 治理 / 只读 fan-out；
- 多模态、语音、OCR、端云协同、端侧推理；
- 生产级 MCP 网关（HTTP/SSE/auth）、容器沙箱、服务化、鉴权、限流、高可用；
- 官方 BFCL / τ² 分数、真实客服流量、业务 KPI、长期用户画像；
- planner / routing 的完整实现——只保留触发率实验和“下一步”说明。

**为什么现在冻结**

- P0 已把“能跑、能评、能看成本、能定位回归”补到可讲的程度；
- 再往上（planner、outcome、CI、multi-agent）是另一个能力层，不应混进当前叙事；
- 冻结边界能让面试口径稳定：**强项讲透，缺口明确，不用硬凑关键词。**
