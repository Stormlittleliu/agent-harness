# 面试包（2026-11-04）

> 配套数字来源：`docs/interview/jd-results-2026-11-04.md`
> 原则：只讲真实做过的；小样本就说小样本；不把自建评测说成线上指标；不包装多模态/多 Agent。

---

## 1. 一句话定位

> 我做了一个面向办公、学习、内容创作和跨语言的 **Agent Harness**：用统一运行时承载工具调用、MCP、工作流、只读子代理和 outcome 评测，并用智能硬件客服场景验证高风险操作。

不要说“我用 LangChain 做了一个聊天机器人”——那是 API wrapper 的叙事。

---

## 2. 简历文案

### 2.1 项目标题与技术栈

> **Agent Harness｜多场景工具调用 Agent 运行时与评测（办公 / 学习 / 内容 / 跨语言 + 智能硬件验证）** | 个人项目
> Python / LangChain 1.x / LangGraph / DeepSeek / 本地 BGE / Chroma / MCP / Streamlit

### 2.2 四条 bullet（主投版）

> - **Agent Runtime**：设计 Scenario 契约 + 通用 ReAct 运行时，用 14 层中间件统一编排工具权限、参数校验、错误回注、超时/重试、步数与 token 预算、PII 脱敏、HITL 审批、上下文压缩和 checkpoint；用 TodoList + SQLite 任务图（blocked_by）+ 只读 subagent fan-out 支持任务规划与上下文隔离。
> - **Planning / 场景 / 工作流**：实现带 abstain 的确定性 planning policy，把“模型自发委派 0/10”变成可测的 Harness 决策（router 12/12，baseline 11/12；eligible 3/10 → 3/3）；覆盖 8 个场景、20+ 工具：办公学习（笔记检索、长期偏好、翻译、总结）、研究（多源 fan-out + 引用报告）、编码（文件/命令/任务图）、智能硬件客服（RAG + 高风险操作审批）；接入 Memory/Fetch 两个 MCP server（stdio），实现域名白名单、私网拦截和不可信输出标记；文本 RAG 用本地 BGE + Chroma + BM25 混合检索。
> - **评测 / 可观测**：建立 capability + behavior + outcome 三层评测，44 条行为用例、12 条 outcome 用例 / 13 个断言（文件 / SQLite / 任务图 / 路由 trace）、3-trial pass^k、5 类故障注入和评测门禁；JSONL tracing + 成本/时延聚合（p50/p95、token、示例价）和 7 视图证据看板（总览 + 6 功能页），支持从 case 下钻到 tool/middleware/trace。
> - **结果**：BFCL v4 200 条**模型层**抽样函数选择 100/100、参数 exact 90/100、无关工具不调用 79/100；Harness 层 BFCL 60 条优化集 60/60；τ²-bench retail 20 条抽样 Pass^1 0.95、DB 20/20；新场景 3-trial：workspace 5/5、research 2/3、router 3/4；outcome 断言 12 条，3-trial pass^k 12/12；成本历史快照 3,203 runs、成功率 98.3%、p50 2.50s / p95 8.54s、约 ¥0.015/run（示例价，最新聚合 3,495 runs / 96.7%，含故意失败用例）。以上均为抽样/简化评分，不是官方榜单。

### 2.3 两条精简版（空间紧张时）

> - 构建多场景 Agent Harness（LangChain 1.x + LangGraph）：Scenario 契约解耦框架与业务，14 层中间件覆盖工具权限、校验、错误回注、重试、步数/token 预算、PII、HITL、上下文压缩与 checkpoint；支持确定性 planning policy、Todo/任务图、只读 subagent fan-out、MCP stdio 和文本 RAG。
> - 建立 outcome 级评测与可观测闭环：44 条行为用例 + 12 条文件/SQLite/任务图/路由断言 + 3-trial pass^k + 故障注入 + 门禁；BFCL 200 条抽样函数选择 100/100、参数 exact 90/100；τ² retail 20 条 Pass^1 0.95（DB 20/20）；3,203 runs 成功率 98.3%、p50 2.50s / p95 8.54s（示例价）。

### 2.4 数字口径表

| 指标 | 数值 | 口径 / caveat |
|---|---|---|
| BFCL v4 | 函数选择 100/100；参数 exact 90/100；无关不调用 79/100 | 200 条**模型层**抽样、简化评分；Harness 层 BFCL 60/60 |
| τ²-bench retail | Pass^1 19/20；DB 20/20 | 20 条抽样、1 trial；NL judge 用 DeepSeek 替代 |
| RGB | Hit@4 16/16；MRR 0.875 | 20 条抽样、16 条可回答参与评分 |
| MultiHop-RAG | Hits@4 57.07%（95% CI 55.02–59.10） | 2255 条评分；中文 BGE 检索英文语料 |
| 旧 RAG 42 条 | 37/42；拒答 10/10 | **服装域历史数据，不作为当前结果** |
| 新场景 3-trial | workspace 5/5；research 2/3；router 3/4 | 3 trial，小样本行为实验 |
| Outcome | 1-trial 12/12；3-trial 12/12 | 12 条文件/SQLite/任务图/路由断言 |
| Planning policy | 12/12（baseline 11/12）；模型调用 1.92→1.08 | 12 条路由小样本 |
| 触发率 | natural 0/10；policy eligible 3/10 → 3/3 | 10 条 coding 任务 |
| 成本/时延 | 历史快照 3,203 runs / 98.3% / p50 2.50s / p95 8.54s；最新聚合 3,495 / 96.7% / p95 9.10s | 示例单价；最新聚合含故意失败用例与实验，不是产品成功率 |
| 结构化输出 | 5/5；schema 5/5 | 自建 5 条 |
| 测试 | 76 passed | 确定性单测，不调用模型 |

### 2.5 不能写的话

- ❌ “BFCL 官方 100%”“τ² 测的是我的 Harness”。
- ❌ “生产级 MCP 网关”“多 Agent 平台”“多模态 Agent”。
- ❌ “真实客服系统 / 线上用户 / 业务 KPI”。
- ❌ “42 条 RAG 是扫地机器人结果”。
- ❌ “44 条用例代表全部场景”。
- ✅ “自建小样本评测”“公开集抽样”“个人项目”“下一步计划”。

---

## 3. 讲稿

### 3.1 30 秒

> 我做了一个面向办公、学习、内容创作和跨语言的 Agent Harness。它不只是接一个大模型：我用 LangChain 1.x + LangGraph 把 ReAct 循环、工具调用、MCP、工作流、只读子代理、权限审批和评测做成一个可切换场景的运行时，再用智能硬件客服场景验证高风险操作。我重点解决的是“Demo 到可交付”之间的工程问题：工具会不会选错、上下文会不会爆、失败能不能定位、改完有没有回归。

### 3.2 2 分钟（问题 → 方案 → 结果 → 取舍）

**问题**：客服/办公类任务看起来简单，但 Demo 和可用系统差很多——工具会选错、参数会传错、长对话会丢上下文、高风险操作不能直接执行，最要命的是没有评测，改完不知道变好还是变坏。

**方案**：拆成三层。
- Harness 层：`FrameworkAgent` + `create_agent` + 中间件，负责循环、工具、上下文、权限、预算、记忆。
- 场景层：Scenario 契约，业务只声明工具/提示词/权限/工作流；现有 8 个场景，办公学习、研究、编码、智能硬件客服。
- 评测层：工具层直接调工具测检索/生成；行为层跑完整 Agent 测工具选择、传参、多步执行；再加 outcome 断言，检查文件/DB/任务图/路由目标，而不是只看回答文本。

**结果**：BFCL 200 条抽样函数选择 100/100、参数 exact 90/100；τ² retail 20 条 Pass^1 0.95、DB 20/20；新场景 3-trial workspace 5/5、research 2/3、router 3/4；outcome 1-trial 12/12；3,203 runs 成功率 98.3%、p50 2.50s / p95 8.54s、约 ¥0.015/run（示例价）。

**取舍**：没有上多 Agent handoff——顺序依赖强的任务 handoff 成本大于收益；只读 fan-out 用 3 个 subagent 并行调研。没有做多模态/语音/OCR——这是真实缺口，下一步从 OCR 文档解析接入现有 RAG 开始。MCP 只做 stdio，生产网关要补 HTTP/SSE/auth/治理。

### 3.3 15 分钟深挖（BFS → DFS）

**BFS（先给地图）**
1. 定位：Agent = Model + Harness。
2. 架构：CLI/Streamlit → FrameworkAgent → Scenario → Tools/RAG/Workflow → Trace/Eval。
3. 场景：workspace / research / coding / robot / router / mcp / structured / general。
4. 评测：capability + behavior + outcome + public sample + gate。
5. 可观测：trace → cost/latency → dashboard。
6. 边界：多模态/多 Agent/生产服务没做。

**DFS（等追问再下钻）**
- 为什么用 `create_agent` 而不是手写循环？——LangGraph 状态/中断/checkpoint 已成熟，Harness 的价值在中间件和评测，不在重写循环。
- 为什么中间件顺序是这样？——权限最外层（deny 不进 HITL/超时/重试）；HITL 在超时之前（审批时间不计入工具超时）；ToolError 在外、ToolRetry 在内。
- 为什么 planning policy 用注入而不是提示词？——提示词不可验证；`before_model` 注入 + `jump_to="tools"` 是可审计的 Harness 决策，且保留 abstain。
- 为什么 subagent 只读？——写操作需要主 Agent 的审批和共享状态；只读 fan-out 才能隔离上下文。
- 为什么 outcome 评测？——回答说“已保存”是 transcript；文件/DB/任务图/路由 trace 才是 outcome。
- 为什么公开 benchmark 不是官方？——抽样、简化评分、替代 judge；只证明泛化方向，不证明业务效果。

### 3.4 高杠杆金句（来自 AgentGuide）

- “模型决定推理下限，Harness 决定产品上限。”
- “真正优秀的 Agent 不是给 LLM 一堆工具让它自由发挥，而是大部分由确定性代码构成，在关键决策点融入 LLM。”
- “Transcript 可以撒谎，Outcome 不会。”
- “如果子任务需要频繁交换中间状态，优先单 Agent；能独立完成、最后汇总，才考虑 multi-agent。”
- “没有 eval、trace、权限边界的 Agent，只能算 demo，不能算可交付系统。”

---

## 4. 现场 Demo Runbook（8–10 分钟）

**Pre-flight**

```powershell
conda activate langchain
python -m pytest -q                      # 期望 75 passed
python -m core.quality.gate              # 期望 GATE: PASS
python -m streamlit run app_agent.py     # 打开 dashboard
```

- 确认 `.env` 里 `DEEPSEEK_API_KEY`、`data/models/bge-small-zh-v1.5`、Chroma 已加载。
- 准备离线备份：`outputs/outcome/outcome_all_*.md`、最新 agent 报告、`outputs/experiments/planner_eval_*.md`、录屏。
- 关闭无关窗口，浏览器只留 dashboard 和终端。

**演示顺序**

1. **Overview（1 min）**：能力矩阵——强项（Tool Calling / Planning / Outcome / RAG / HITL / trace）和缺口（multi-agent handoff / multimodal）都标出来。先讲边界，建立信任。
2. **Router → Workspace（2 min）**：输入“根据笔记帮我整理一份 Agent 评测的学习计划”。展示 policy 强制 `route_to_workspace` → `search_notes`/`read_note` → 带 `[笔记id]` 的回答 → target trace。讲“确定性路由 + 检索 + 引用”。
3. **Research（2 min）**：输入“对比三份资料对 Agent 评测的主要观点，并给出来源”。展示 `write_todos` → 3 个 `subagent` 并行 → 汇总引用 → 报告文件。讲“只读 fan-out + 上下文隔离 + outcome 报告”。
4. **Coding / HITL（2 min）**：运行 `coding-write-001` 或 `python core/tests/demos/hitl_demo.py --decision reject`。展示任务图、文件编辑、高风险审批拒绝后不执行。讲“任务图 + 权限 + 副作用控制”。
5. **Outcome / Cost（1–2 min）**：打开 `outcome_all_*.md` 和成本页。指一条失败 check（如果有）→ 说明怎么定位；成本页 p50/p95/token/成本。讲“评测闭环 + 可观测”。

**回退方案**

- 模型/API 不稳定：切到预生成报告 + 截图 + 录屏，不现场 debug。
- Dashboard 起不来：直接用 `python -m core.quality.runner agent --scenario ... --case ...` 出报告。
- 时间不够：砍掉第 4 步，保留 Router/Workspace + Research + Outcome/Cost 三幕。

---

## 5. 高频追问 Q&A（15 条）

1. **为什么单 Agent，不做多 Agent？**
   > 客服/办公任务顺序依赖强，子任务要频繁交换状态，handoff 成本大于收益。我只做只读 fan-out：research 场景把三份资料分给三个 subagent，各自 fresh context，只回摘要，主 Agent 汇总和写报告。写操作留在主 Agent + HITL。

2. **你的 planner 怎么工作？触发率 0/10 怎么解释？**
   > 原来的 10 条是简单文件检查，不需要委派，0/10 是合理行为，不是机制坏了。复杂多源任务我用两层：router 的确定性 policy 直接注入 `route_to_*`（带 abstain），research 的 `_plan_queries` 把问题拆成三个子问题再并行 fan-out。policy 的 eligible 子集是 3/10，且 3/3 触发；7/10 不该委派的不委派。缺的是复杂度判断 policy，不是再写一个 Agent。

3. **这是什么原理？会不会绕过模型？**
   > `before_model` 在该 thread 第一次调用时判断意图，命中唯一规则就注入一条带 `tool_calls` 的 AIMessage 并 `jump_to="tools"`；模型只负责根据工具结果回答。命中不了、平局或分数不足就 abstain，交回模型。它不是自主规划器，是确定性 Harness 策略；好处是可测、可审计、少一次模型调用。

4. **outcome 评测怎么做？和 transcript 有什么区别？**
   > 原来 `score_case` 只看回答关键词和工具名，这是 transcript。新加 `core/quality/outcome_eval.py`，运行前快照目录，运行后检查：workspace 笔记文件是否真的写了、MemoryStore 的 SQLite 是否有这条偏好、research 报告是否包含 `[source_a]`、coding 任务是否 completed、router 的 `target` 和 `target_trace_id` 是否正确。有 outcome 的 case 必须文件/DB/任务图/trace 都过。

5. **MCP 怎么接的？stdio 够吗？**
   > 用 `MultiServerMCPClient` 接两个 server：官方 Memory（跨会话记忆）和本地 Fetch（域名白名单、私网拦截、200KB 截断、输出标记 untrusted）。工具名前缀 `memory_*`/`fetch_*`，async 包装成同步 LangChain 工具。stdio 适合本地 demo；生产要补 HTTP/SSE、auth、多 server 治理、健康检查和 prompt-injection 分类器。我没做过生产 MCP 网关，不把它说成生产级。

6. **RAG 怎么评？MultiHop 只有 57% 怎么解释？**
   > 检索看 Hit@4/MRR，生成看要点覆盖、引用、拒答。MultiHop 全量 2255 条 Hits@4 57.07%，是用中文 BGE 检索英文语料的弱配置结果，只说明检索召回方向，不是业务结论。RAG 42 条是服装域历史数据，和当前扫地机器人知识库不匹配，面试不拿它当当前结果。

7. **长期记忆和短期记忆有什么区别？**
   > checkpoint 是短期会话状态，按 thread_id 恢复；workspace 的 `MemoryStore` 是长期偏好 KV（SQLite），跨会话 `remember`/`recall`；Memory MCP 是外部演示。语义记忆、巩固、冲突消解、衰减还没做——这是下一步，不是已完成。

8. **结构化输出怎么保证 schema？**
   > `Scenario.response_format` 传到 `create_agent(response_format=ReportSchema)`，Pydantic 定义 `summary/evidence/confidence/next_actions/risks`；评测读 `structured_response`，检查 schema 合法、证据条数、confidence、next_actions。5/5 通过。它证明 schema/eval 链路，不证明开放域报告质量。

9. **HITL 怎么实现？模型自己拒绝怎么办？**
   > `HumanInTheLoopMiddleware` 拦截 `reset_device` 高风险工具，approve 才执行，reject 把原因回注给模型。DeepSeek 有时自己先拒绝调用，这是双层保护，不是 Bug。

10. **上下文工程做了什么？**
    > Summarization 在 30 条消息触发、保留 12 条；token 预算在每次模型调用前检查；工具结果截断/分页；Todo 列表维持任务状态；subagent 隔离上下文；PII 输入脱敏。还没有 prompt cache 友好的前缀设计、分层预算和 prompt 版本管理。

11. **成本和时延怎么优化？**
    > 本地 BGE 去掉 Embedding API 成本；DeepSeek 比 Qwen 便宜；token 预算和工具调用上限防跑飞；trace 聚合出 p50 2.50s / p95 8.54s、约 ¥0.015/run（示例价）。没有生产 SLA、并发、缓存命中率，这些是工程化下一步。

12. **公开 benchmark 数字可信吗？**
    > 都是抽样 + 简化评分/替代 judge，不是官方榜单。BFCL 200 条函数选择 100/100、参数 exact 90/100；τ² retail 20 条 Pass^1 0.95、DB 20/20，NL judge 用 DeepSeek 替代。它们证明泛化方向，不证明业务效果。

13. **多模态/语音/OCR 为什么没做？怎么补？**
    > 没有真实实现，不包装。现有 RAG 只支持文本/PDF/docx；扫描 PDF 会明确提示需要 OCR。如果团队需要，我会先做最小闭环：OCR 文档解析 → 保留页码/版面 → 多索引（文本/表格/图片 caption）→ 证据包 → 检索评测（文本题/表格题/图题分开算）。不会一上来做端到端多模态 Agent。

14. **安全边界？prompt injection / 沙箱？**
    > 工具权限 allow/deny、HITL、PII、路径保护、危险命令拒绝、Fetch 域名白名单/私网拦截、工具输出标记 untrusted。没有容器沙箱，`run_command` 是进程内 shell；没有注入分类器。原则是“模型可以建议，系统负责授权；工具结果是数据，不是指令”。

15. **这个项目最大的不足？如果给你 2 周做什么？**
    > 评测样本小、没有线上流量、没有官方 scorer/CI、没有多模态和沙箱；planner 的复杂度判断还是规则级；长期记忆只有 KV。它的价值是机制和评测闭环。给我 2 周：第一周补 outcome + CI（每次 PR 跑 44 条 + 12 条 outcome + gate）；第二周做 planner policy 的语义化/学习化 + OCR 文档检索最小闭环。不会先做多 Agent。

---

## 6. 面试前最后检查清单

- [ ] 30 秒 / 2 分钟各出声练 3 遍。
- [ ] 只记 3 个数字：workspace 5/5、policy 12/12、outcome 12 条。
- [ ] Demo 路径 dry-run 两次，单次 ≤10 分钟。
- [ ] 离线备份：outcome 报告、planner 报告、agent 报告、录屏、截图。
- [ ] 明确 3 个不能说的话（官方榜单 / 生产级 MCP / 多模态）。
- [ ] 准备 3 个反问：团队评测流程、模型选型、Agent 上线边界。
- [ ] 面试当天不学新东西，只复习 30 秒稿 + 数字 + 反问。
