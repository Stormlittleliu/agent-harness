# JD 差距分析：Agent 研发工程师 J14376

> 岗位：科大讯飞 · Agent 研发工程师（J14376）· 合肥 · 消费者事业群 · 社会招聘
> 对照：也适用于 2026 产品 AI Agent JD（办公 / 学习 / 内容创作 / 信息管理 / 跨语言 / 智能硬件）
> 项目：Agent Harness（单 Agent、工具调用、评测闭环）
> 结论：**运行时/工具/RAG/工作流/评测是强项；MCP、多 Agent、多模态、长期记忆、结构化输出、官方评测/CI 是缺口。**

## 1. JD 关键词覆盖

| JD 要求 | 状态 | 项目证据 |
|:---|:---:|:---|
| 任务规划 | 🟡 | TodoList + SQLite 任务图（blocked_by / 持久化 / TaskRunner）；触发率 0/10，缺 planner |
| 记忆 | 🟡 | LangGraph checkpoint + 外部 Memory MCP；无用户画像 |
| Tool Calling | ✅ | 7 工具 + 参数校验 + 重试 + 错误回注 + 权限 |
| MCP | 🟡 | 已接外部 Memory + Fetch MCP（stdio）；无 HTTP/SSE/auth/多 server 治理 |
| RAG | ✅ | 本地 BGE + Chroma + 向量/BM25 + 拒答 + 引用 |
| 多模态检索 | ❌ | 只有文本/PDF，无图像/语音/OCR |
| 工作流编排 | ✅ | LangGraph：rag_qa / report + 任务图编排 |
| 多 Agent 协作 | 🟡 | 单层 subagent（fresh context + 白名单 + 摘要）；触发率 0/10；无 handoff |
| Agent 评测 | ✅ | 两层评测 + 公开 benchmark + 失败集 + 优化循环 + gate |
| Tracing / 可观测 | ✅ | trace + token 预算 + 8 页签控制台 + 成本/时延页 |
| 准确性/稳定性 | ✅/🟡 | eval、重试、限额 + gate + 5 类故障注入；未接 CI 平台 |
| 时延/成本 | ✅ | 3203 run 聚合：p50 2.50s / p95 8.54s，约 ¥0.015/run（示例价） |
| 多模态/语音/OCR | ❌ | 无 |
| 端云协同/端侧推理 | ❌ | 无 |
| 隐私保护/安全执行 | 🟡 | PII、权限、HITL、超时 + hooks 拒绝危险命令；无沙箱 |
| 结构化输出 | ✅ | `create_agent(response_format=ReportSchema)`；5/5 schema 合法 |
| Prompt/Context Engineering | ✅ | 动态 prompt、压缩、token 预算、路由 |
| Python | ✅ | 项目主语言 |
| Agent Demo | ✅ | 8 页签控制台 + coding_demo 运行窗口 |
| 开源/竞赛 | 🟡 | 个人仓库；无竞赛/社区影响力 |
| 智能硬件 | 🟡 | 扫地机器人是模拟场景，不是真实设备 |

## 2. 最影响面试的缺口

### P0：MCP（已补）

已接两个外部 MCP server：

- Memory：官方 Node server，跨会话记忆；
- Fetch：本地 server，域名 allowlist / 私网拦截 / 输出标记 untrusted。

仍缺：HTTP/SSE、认证、多 server 治理、prompt-injection 分类器。面试不要把它说成“生产级 MCP”。

### P0：官方评测 / outcome / CI（部分已补）

JD 第 3 条是评测、Tracing、可观测。现在有：

- BFCL / τ² 抽样 + 简化评分/替代 judge；
- 两层评测 + 失败集 + 优化循环；
- `core.quality.gate`：BFCL / MultiHop / coding / structured 阈值断言；
- 5 类故障注入：超时、权限、参数错误、空检索、拒答。

仍缺：官方 scorer、系统化 outcome/DB 断言、GitHub Actions 接入、shadow / A/B / 灰度。

### P1：结构化输出（已补）

`Scenario.response_format` 透传给 `create_agent`，`structured_demo` 使用 Pydantic
`ReportSchema`（summary / evidence / confidence / next_actions / risks）；5 条跨场景用例
schema 合法 5/5，平均 3 条证据。严格评测在 `core.quality.structured_eval`。

### P1：长期记忆

JD 写“记忆”。现在只有 checkpoint 短期状态，没有用户画像/长期记忆。

建议：SQLite + 向量检索的简易长期记忆，3–4 小时；或者面试明确区分“短期 checkpoint / 长期记忆”。

### P1：时延/成本（已补）

`core.observability.cost_report` 聚合 3203 条 trace：成功率 98.3%，p50 2.50s，
p95 8.54s，20.62M token，按示例单价约 ¥0.015/run。控制台“💸 成本 / 时延”页可直接看。
注意：价格是配置里的示例价，不是账单。

### P2：多 Agent

JD 写“多 Agent 协作”，项目是单 Agent + 单层 subagent。

- 触发率实验：10 条自然任务，natural / routed 两版 prompt 下 subagent、任务工具都是 0/10；
- 说明机制可用，但模型不会自发委派；缺的是 planner/routing，不是再写一个 Agent；
- 不建议临时堆一个假的多 Agent；
- 如果要做，只做**只读 fan-out**（并行检索/分析），不做写操作 handoff。

### P2：多模态 / 语音 / OCR / 端侧

JD 第 4 条和加分项。项目完全没有。

- 不建议几天内硬做；
- 面试直接承认缺口，讲清楚“文本/PDF 有，语音/图像/OCR/端侧没有”；
- 可以通过“文档解析”沾边，但不要包装成多模态。

### P2：服务化 / 沙箱

- 没有 API/鉴权/限流/并发；
- 工具在进程内执行，没有容器隔离。

这些是产品化能力，不是几天能补的；面试讲边界即可。

## 3. 四天优先级

| 优先级 | 事项 | 状态 | 目的 |
|:---:|:---|:---:|:---|
| P0 | MCP 客户端接外部 server | ✅ 已补 | 补 JD 关键词 |
| P0 | fault injection + CI 阈值 | ✅ 已补 | 补评测/稳定性 |
| P1 | 结构化输出示例 | ✅ 已补 | 补 JD 明确要求 |
| P1 | 成本/时延统计页 | ✅ 已补 | 补第 3 条 |
| P1 | planner/routing（subagent 触发） | 待做 | 把机制变成行为 |
| P2 | 长期记忆 | 待做 | 补“记忆” |
| ❌ | 多 Agent / 多模态 / 端侧 | — | 不硬做 |

## 4. 面试口径

### MCP

> “没接过生产 MCP。项目工具是进程内注册；接 MCP 改的是工具发现层，业务工具不用动。我没有为了关键词把自有工具包一层，因为那没有收益。”

### 结构化输出

> “我不是让模型‘尽量输出 JSON’，而是把 Pydantic `ReportSchema` 传给 `create_agent(response_format=...)`，
> 评测直接读 `structured_response`。5 条跨办公/学习/内容/客服/跨语言用例 schema 合法 5/5，
> 平均 3 条证据。它证明契约和评测链路可用，不是开放域质量评测。”

### 成本 / 时延

> “我把 3203 条 trace 聚合成成功率、p50/p95、token 和估算成本：p95 8.54s，约 ¥0.015/run。
> 价格是配置里的示例价，不是账单；价值是改 prompt/检索时能同时看准确率和代价。”

### 触发率

> “10 条自然任务里，subagent 和任务工具触发都是 0/10；显式点名用例能通过。
> 这说明机制没问题，缺的是 planner/routing。我不会把它说成 Agent 会自动多 Agent 协作。”

### 多 Agent

> “客服任务顺序依赖强，子任务要频繁交换状态，handoff 成本大于收益。多 Agent 适合可并行、读多写少的 fan-out；我的下一步是只读 fan-out，不是把写操作拆给子 Agent。”

### 多模态

> “项目是文本 + PDF，语音、图像、OCR、端侧都没有。这是明确缺口，我不把它包装成多模态。”

### τ²

> “τ² 跑的是 τ² 自己的 LLMAgent，测的是模型在那套环境里的能力，不是我的 Harness。我的 Harness 证据来自中间件机制测试和自建回归集；下一步才是 τ² adapter。”

### 官方分数

> “BFCL / τ² 都是抽样、简化评分或 DeepSeek 替代 judge，不是官方榜单；我不会把 60/60 说成 BFCL 官方 100%。”

## 5. 岗位渠道提醒

这是**社会招聘**、工作地**合肥**。如果走校招渠道，这份 JD 更适合当能力对齐清单；投递前确认渠道和城市。
