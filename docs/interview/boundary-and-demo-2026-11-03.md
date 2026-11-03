# 边界与展示口径（2026-11-03 排练版）

> 面试：2026-11-04 上午
> 原则：不补新能力、不刷绿、不把“安全拒答”说成“任务成功”。
> 目标：30 分钟内让面试官相信三件事：真的做过、真的测过、知道边界在哪。

---

## 1. 一句话边界

> 这是一个**单机、单 Agent、工具调用型 Agent Harness**，用 8 个场景验证运行时、规划/路由、MCP、工作流和评测闭环；**不是联网研究 Agent、不是多 Agent 平台、不是多模态 Agent、不是生产服务**。

---

## 2. 数据边界（最重要）

| 场景 | 数据来源 | 是否联网 | 边界说法 |
|---|---|---|---|
| `research_assistant` | `data/research_assistant/sources/` 3 篇 Agent 评测资料 | ❌ | 本地小语料；检索为空必须拒答；Transformer 这类问题属于**任务失败/数据缺口**，不是成功 |
| `workspace_assistant` | `data/workspace_assistant/notes/` 本地笔记 | ❌ | 办公/学习/内容/跨语言，本地笔记 |
| `robot_vacuum` | `data/knowledge/` + 本地 Chroma | ❌ | 模拟智能硬件客服，知识库是本地文档 |
| `coding_demo` | `data/runtime/coding_workspace/` | ❌ | 本地文件/命令/任务图 |
| `mcp_demo` | Memory MCP + Fetch MCP（单 URL、域名白名单） | ⚠️ | Fetch 是“抓一个允许域名下的 URL”，**不是搜索** |
| `router` | 上述本地场景 | ❌ | 场景级分发，不是多 Agent 协商 |

**不要说**：
- “能联网搜索/能调研整个互联网”
- “research_assistant 是 web research agent”
- “MCP Fetch 是搜索引擎”

**被问 Transformer 时**：
> “这条问题不在本地语料里。正确行为是拒答，但任务本身失败了，我不会把拒答算成任务成功。要解决，要么加资料，要么接搜索 API + Fetch；这是新能力层，不是 prompt 能补的。”

---

## 3. 能力边界

| 有 | 没有 |
|---|---|
| 单 Agent ReAct + 14 层中间件 | 多 Agent handoff / supervisor / 共享状态 |
| Tool Calling、参数校验、错误回注、重试、超时、预算 | 生产级 MCP 网关（HTTP/SSE/auth/治理） |
| 确定性 planning/routing policy（带 abstain） | 语义/学习型 planner |
| 只读 subagent fan-out | 多 Agent 协作协议 / A2A |
| 本地文本 RAG（BGE + Chroma + BM25） | 多模态 / 语音 / 图像 / OCR / 视觉 embedding |
| 7 条 LangGraph 工作流 | 分布式工作流 / 队列 / 持久化执行 |
| JSONL trace + 成本/时延 + 7 视图 dashboard | OTel / LangSmith / 生产 SLA / 告警 |
| 44 条行为用例 + 12 条 outcome 用例 / 13 个断言 | 官方 BFCL/τ² scorer、CI 平台、5–10 trial + bootstrap CI |
| HITL、PII、权限、路径保护、Fetch 白名单 | 容器沙箱、注入分类器 |
| 本地 BGE（CPU） | 端侧 LLM / 端云协同 |

---

## 4. 评测口径（必须说清）

### 4.1 绿 ≠ 任务成功

- `should_refuse=true` 的用例：拒答是**预期行为**，绿是对的。目前只有 robot `agent-refuse-001`（退货政策）属于这种。
- `should_refuse=false` 的正常任务：工具没查到资料 → 拒答，**任务失败**。这种失败不能算通过。
- **没有**为 Transformer 问题新增拒答用例；`research_assistant` 仍然只有 3 条正常研究用例。

### 4.2 数字口径

| 口径 | 数字 | 怎么讲 |
|---|---|---|
| 2026-11-02 新鲜 1-trial | **44/44**（8 场景） | “新鲜 1-trial 全绿；其中 1 条是真拒答用例，不是普通任务。” |
| 3-trial 历史快照 | workspace 5/5、research 2/3、router 3/4、coding 7/7（1-trial） | “3-trial 是修复前的保守快照；修复后还没重跑 3-trial，不冒充稳定性。” |
| outcome | 12 条用例 / 13 个断言，3-trial **12/12** | “不看回答文本，检查文件/SQLite/任务图/路由 trace。” |
| planning policy | router 12/12（baseline 11/12）；模型调用 1.92 → 1.08 | “确定性策略，不是自主 planner。” |
| 触发率 | natural 0/10、routed 0/10、policy eligible 3/10 → 3/3 | “该委派的委派，不该委派的不委派。” |
| BFCL / τ² | BFCL 200 条**模型层** 100/100 选择、90/100 参数；Harness 层 BFCL 60/60；τ² 19/20、DB 20/20 | “模型层/Harness 层/外部层分开说；抽样/简化评分，不是官方榜单。” |
| 成本/时延 | 3,203 历史快照 98.3%、p50 2.50s / p95 8.54s；最新 3,495 / 96.7% 含失败用例 | “示例价，不是账单；最新聚合含故意失败用例，不是产品成功率。” |

**不要说**：
- “44/44 说明所有问题都能答”
- “research 3/3 是 3-trial 稳定结果”（这是 1-trial 新鲜结果；3-trial 历史是 2/3）
- “BFCL 官方 100%”

---

## 5. 展示主线

**标题**：
> 多场景 Agent Harness：让 Agent 可约束、可观测、可回归。

**三条证据链**：
1. **Harness 机制**：Scenario 契约 + 14 层中间件 + Tool Calling + HITL + checkpoint。
2. **Planning / Outcome**：确定性 policy（12/12）+ outcome 断言（12/12）+ transcript vs outcome 的对照。
3. **评测 / 可观测**：44 行为 + 12 outcome / 13 断言 + 3-trial + trace + 成本看板。

**不要以 RAG 或多 Agent 做标题**：RAG 是工具，多 Agent 只有只读 fan-out。

---

## 6. 8–10 分钟 Demo 脚本

### 第 1 幕：总览（1 分钟）
- 打开 `http://localhost:8502`。
- 指能力矩阵：强项（Tool Calling / Planning / Outcome / RAG / HITL / trace）；缺口（multi-agent handoff / multimodal）。
- 一句话：“先讲边界，再讲证据。”

### 第 2 幕：Router → Workspace（2 分钟）
- 输入：“根据笔记帮我整理一份 Agent 评测的学习计划。”
- 展示：policy 强制 `route_to_workspace` → `search_notes` / `read_note` → 带 `[笔记id]` 的回答 → 调用链。
- 讲：“确定性路由 + 检索 + 引用。”

### 第 3 幕：Research（2 分钟，只用语料内问题）
- 输入：“对比三份资料对 Agent 评测的主要观点，并给出来源。”
- 展示：`write_todos` → 3 个 `subagent` 并行 → 汇总引用 → 报告文件。
- **不要输入 Transformer 问题**；如果面试官问，切到边界回答。
- 讲：“只读 fan-out + 上下文隔离 + outcome 报告。”

### 第 4 幕：Coding / HITL（2 分钟）
- 跑 `coding-write-001` 或 `python core/tests/demos/hitl_demo.py --decision reject`。
- 展示：任务图、文件编辑、高风险审批拒绝后不执行。
- 讲：“任务图 + 权限 + 副作用控制。”

### 第 5 幕：评测 / 成本（1–2 分钟）
- 打开“评测”页：场景报告、outcome、成本/时延。
- 指一条失败/边界：“这里能看到失败原因，不是只给一个总分。”
- 讲：“评测闭环 + 可观测。”

**回退**：
- API 不稳定 → 切预生成报告 + 截图 + 录屏。
- Dashboard 起不来 → CLI 报告。
- 时间不够 → 砍第 4 幕，保留 Router/Workspace + Research + 评测。

---

## 7. 高频边界问答

### Q1. 能联网搜索吗？
> “不能。`research_assistant` 是本地三篇资料的小语料 demo；`mcp_demo` 的 Fetch 是单 URL、域名白名单，不是搜索。要联网，需要接搜索 API + Fetch + 安全/评测，这是新能力层。”

### Q2. Transformer 问题为什么拒答？
> “因为本地语料没有 Transformer 内容，`search_sources` 返回空。拒答是正确行为，但任务失败了，我不会把拒答算成任务成功。要回答，要么加资料，要么接搜索。”

### Q3. 44/44 全绿，是不是所有任务都能做？
> “不是。44/44 是当前 44 条用例的评分结果，其中 1 条是真拒答用例；Transformer 这类语料外问题不在其中，算任务失败。1-trial 也只是 smoke，不是稳定性结论。”

### Q4. 为什么 research 3-trial 只有 2/3？
> “修复前的保守快照；`research-compare-001` 有时直接读资料、不走 subagent。修复后新鲜 1-trial 是 3/3，但 3-trial 还没重跑，我不冒充稳定。”

### Q5. 多 Agent 在哪？
> “只有 research 的只读 fan-out：3 个 subagent 并行读不同资料，主 Agent 汇总；没有 handoff、supervisor、共享状态。写操作留在主 Agent + HITL。”

### Q6. MCP 到什么程度？
> “stdio 的 Memory + Fetch；没有 HTTP/SSE、auth、多 server 治理。Fetch 有域名白名单、私网拦截、200KB 截断、untrusted 标记。”

### Q7. 多模态 / 语音 / OCR？
> “没有真实实现。现有只到文本/PDF 文档解析；扫描 PDF 会明确提示需要 OCR。如果要做，先 OCR 解析 → 页码/版面 → 多索引 → 证据包 → 分题型评测。”

---

## 8. 明天（11/3）排练时间表

| 时间 | 内容 | 产出 |
|---|---|---|
| 09:00–10:00 | 30 秒 / 2 分钟各练 3 遍；只记 3 个数字：workspace 5/5、policy 12/12、outcome 12/12 | 两版稿定稿 |
| 10:00–11:30 | Demo dry-run 1：总览 → Router/Workspace → Research（语料内）→ Coding/HITL → 评测 | 单次 ≤10 分钟 |
| 11:30–12:00 | 截图 / 报告 / 录屏备份；确认 8502 可打开 | 离线备份 |
| 13:30–15:00 | 15 个追问 + 7 个边界问答；重点 Q1/Q2/Q3/Q5 | 卡壳点清单 |
| 15:00–16:30 | 模拟面试 30 分钟；按“结论 → 机制 → 数字 → 边界”回答 | 3 个卡壳点修复 |
| 16:30–17:30 | Demo dry-run 2；计时；准备反问 | 最终演示稿 |
| 17:30–18:00 | **冻结代码/评测**；只允许改文档和讲稿 | 冻结 |
| 晚上 | 轻复盘、设备检查、23:00 前睡 | 面试状态 |

**冻结后不再做**：
- 不加新场景 / 新工具 / 新评测；
- 不改 prompt / case / 评分；
- 不重跑大规模 benchmark；
- 只练讲稿、截图、演示路径。

---

## 9. 一句话总结

> **强项讲透：Harness 工程、planning policy、outcome 评测、trace/cost。缺口讲清：本地语料不是联网搜索，单 Agent 不是多 Agent 平台，拒答不是任务成功。**
