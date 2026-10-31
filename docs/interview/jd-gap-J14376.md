# JD 差距分析：Agent 研发工程师 J14376

> 岗位：科大讯飞 · Agent 研发工程师（J14376）· 合肥 · 消费者事业群 · 社会招聘
> 项目：Agent Harness（单 Agent、工具调用、评测闭环）
> 结论：**运行时/工具/RAG/工作流/评测是强项；MCP、多 Agent、多模态、长期记忆、结构化输出、官方评测/CI 是缺口。**

## 1. JD 关键词覆盖

| JD 要求 | 状态 | 项目证据 |
|:---|:---:|:---|
| 任务规划 | ✅ | TodoList + SQLite 任务图（blocked_by / 持久化 / TaskRunner） |
| 记忆 | 🟡 | LangGraph checkpoint + 外部 Memory MCP；无用户画像 |
| Tool Calling | ✅ | 7 工具 + 参数校验 + 重试 + 错误回注 + 权限 |
| MCP | 🟡 | 已接外部 Memory + Fetch MCP（stdio）；无 HTTP/SSE/auth/多 server 治理 |
| RAG | ✅ | 本地 BGE + Chroma + 向量/BM25 + 拒答 + 引用 |
| 多模态检索 | ❌ | 只有文本/PDF，无图像/语音/OCR |
| 工作流编排 | ✅ | LangGraph：rag_qa / report + 任务图编排 |
| 多 Agent 协作 | ❌ | 刻意单 Agent；无 handoff |
| Agent 评测 | ✅ | 两层评测 + 公开 benchmark + 失败集 + 优化循环 |
| Tracing / 可观测 | ✅ | trace + token 预算 + 7 页签控制台 |
| 准确性/稳定性 | ✅/🟡 | 有 eval、重试、限额；无 CI 门禁 |
| 时延/成本 | 🟡 | trace 有 latency/token；pricing 未配置，无系统优化 |
| 多模态/语音/OCR | ❌ | 无 |
| 端云协同/端侧推理 | ❌ | 无 |
| 隐私保护/安全执行 | 🟡 | PII、权限、HITL、超时 + hooks 拒绝危险命令；无沙箱 |
| 结构化输出 | 🟡 | 工具参数用 Pydantic schema；无 `with_structured_output` 示例 |
| Prompt/Context Engineering | ✅ | 动态 prompt、压缩、token 预算、路由 |
| Python | ✅ | 项目主语言 |
| Agent Demo | ✅ | 7 页签控制台 + coding_demo 运行窗口 |
| 开源/竞赛 | 🟡 | 个人仓库；无竞赛/社区影响力 |
| 智能硬件 | 🟡 | 扫地机器人是模拟场景，不是真实设备 |

## 2. 最影响面试的缺口

### P0：MCP（已补）

已接两个外部 MCP server：

- Memory：官方 Node server，跨会话记忆；
- Fetch：本地 server，域名 allowlist / 私网拦截 / 输出标记 untrusted。

仍缺：HTTP/SSE、认证、多 server 治理、prompt-injection 分类器。面试不要把它说成“生产级 MCP”。

### P0：官方评测 / outcome / CI

JD 第 3 条是评测、Tracing、可观测。我们有两层评测和 trace，但：

- BFCL / τ² 都是抽样 + 简化评分/替代 judge；
- 没有官方 scorer；
- Outcome 只覆盖 HITL/预算/持久化，没有系统化 DB/state 断言；
- 没有 CI 门禁。

建议：先做 fault injection + 本地 CI 阈值脚本，再考虑官方 scorer。

### P1：结构化输出

JD 明确写“结构化输出”。现在只有工具参数 schema，没有模型端 `with_structured_output`。

建议：加一个“报告生成 → JSON schema”的示例，1–2 小时。

### P1：长期记忆

JD 写“记忆”。现在只有 checkpoint 短期状态，没有用户画像/长期记忆。

建议：SQLite + 向量检索的简易长期记忆，3–4 小时；或者面试明确区分“短期 checkpoint / 长期记忆”。

### P1：时延/成本

JD 要求优化时延、成本。trace 有数据，但 `pricing` 为空，没有系统统计。

建议：填官方单价，生成一页 p50/p95 延迟 + token/成本统计，1–2 小时。

### P2：多 Agent

JD 写“多 Agent 协作”，项目是单 Agent。

- 不建议临时堆一个假的多 Agent；
- 面试讲清楚：客服任务顺序依赖强，handoff 成本大于收益；多 Agent 适合并行、读多写少的 fan-out；
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

| 优先级 | 事项 | 工时 | 目的 |
|:---:|:---|:---:|:---|
| P0 | MCP 客户端接外部 server | 3–4h | 补 JD 关键词 |
| P0 | fault injection + CI 阈值 | 3–4h | 补评测/稳定性 |
| P1 | 结构化输出示例 | 1–2h | 补 JD 明确要求 |
| P1 | 成本/时延统计页 | 1–2h | 补第 3 条 |
| P2 | 长期记忆 | 3–4h | 补“记忆” |
| ❌ | 多 Agent / 多模态 / 端侧 | — | 不硬做 |

## 4. 面试口径

### MCP

> “没接过生产 MCP。项目工具是进程内注册；接 MCP 改的是工具发现层，业务工具不用动。我没有为了关键词把自有工具包一层，因为那没有收益。”

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
