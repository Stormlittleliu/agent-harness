# Agent 优化方向全景（v1.0）

> **文档定位**：面向 LLM 应用 / Agent 开发工程师，持续收集 Agent 的优化方向，用于学习路线、项目迭代和面试准备。
> **更新时间**：2026-10-27
> **状态**：方向清单 + 优先级，本轮不改代码。
> **来源**：AgentGuide 仓库、公开论文/工程博客、Agent 开发与 AI 应用工程师岗位 JD。
> **证据等级**：A = 官方文档/工程博客；B = 论文/基准；C = JD/社区/实践经验。

---

## 0. 结论先行

1. **Agent 的优化不是"让模型更聪明"，而是让系统更可靠、更可控、更便宜。**
   核心指标是任务成功率、pass^k、成本/成功任务、p95 延迟、违规率，而不是单轮回答好不好看。

2. **优化分三层：模型层、Harness 层、产品层。**
   模型层做选型、路由、后训练；Harness 层做上下文、工具、循环、记忆、评测；产品层做权限、HITL、交互和审计。

3. **2026 年的主线：从"堆上下文、堆 Agent"转向"选择性上下文 + 可验证轨迹 + 最小 Harness"。**
   公开资料反复出现同一结论：不是信息越多越好，而是"与下一步决策最相关的信息"越多越好。

4. **可靠性是数学问题，不是 Prompt 问题。**
   单步 95% 可靠性，20 步只剩 36%；所以长流程必须拆小、可验证、可回滚、可人工介入。

5. **岗位 JD 已经从"会调 API"转向"对业务效果和上线质量负责"。**
   RAG、LangGraph、MCP、上下文工程、Memory、评测、成本/延迟、Guardrails 是高频要求。

---

## 1. 优化方向总览

| ID | 方向 | 解决的问题 | 代表手段 | 关键指标 | JD 频率 | 本项目优先级 |
|:--:|:---|:---|:---|:---|:--:|:--:|
| A | Context Engineering | 上下文腐蚀、长上下文、token 成本 | 分层、Offload、Retrieve、Compress、Isolate、缓存友好 | tokens/任务、缓存命中、成功率、成本/成功 | 高 | P0 |
| B | Tool Engineering | 工具误选、参数错误、部分失败、结果过长 | Schema、描述、错误回注、分页/截断、幂等、权限 | 工具选择准确率、参数合法率、重试率 | 高 | P0 |
| C | Agent Loop / Planning | 早停、死循环、长任务漂移 | ReAct、Plan-and-Execute、Todo、Reflection、停止条件 | 步数、成功率、循环率、恢复率 | 高 | P0 |
| D | Memory | 跨会话遗忘、偏好不一致、记忆污染 | 工作/情景/语义/程序记忆、巩固、冲突更新、分层存储 | 召回准确率、过期率、跨会话一致性 | 高 | P1 |
| E | RAG | 检索漏召回、噪声、多跳、引用不可信 | Hybrid、Rerank、Query 改写、GraphRAG、Agentic RAG、引用溯源 | Hit@K、MRR、Faithfulness、拒答率 | 极高 | P0 |
| F | Eval / Observability | 只看最终答案、无法定位、回归困难 | 组件/轨迹/端到端、Code/LLM/Human Grader、Trace、CI | pass@k、pass^k、工具 P/R、p95、成本 | 极高 | P0 |
| G | Reliability | 错误累积、工具故障、状态丢失、重复副作用 | 限步、超时、熔断、重试、幂等、Checkpoint、补偿 | 故障注入成功率、重复率、恢复时间 | 高 | P0 |
| H | Safety / Permission | 越权、破坏性操作、Prompt Injection、PII | 权限分级、HITL、Sandbox、最小权限、审计 | 违规率、审批延迟、注入成功率 | 高 | P1 |
| I | Cost / Latency | token 二次增长、长轨迹、模型价格差 | Prompt Cache、缓存感知路由、压缩、批处理、流式 | 成本/成功、缓存命中、TTFT、p95 | 高 | P1 |
| J | Multi-Agent / Subagent | 上下文污染、并行任务、长任务隔离 | Supervisor、Handoff、只读 Fan-out、Worktree 隔离 | 并行加速、token 倍数、协调失败率 | 中高 | P2 |
| K | Skills / Procedural Memory | 重复纠正、流程不复用、System Prompt 膨胀 | SKILL.md、渐进式披露、条件激活、按需加载 | Skill 召回、token 开销、复用率 | 中高 | P1 |
| L | Harness Engineering | 模型之外的可靠性、工具/状态/权限/观测 | 七层模型、可靠性六件套、最小 Harness | 成功率、成本、失败归因 | 高 | P0 |
| M | Post-training / Agentic RL | 工具策略、长程信用分配、奖励作弊 | SFT/LoRA、DPO/GRPO、轨迹数据、Verifier、稠密奖励 | 任务成功率、pass@k、作弊率 | 中（算法岗） | P2 |
| N | RSI / Self-evolution | 经验内化、持续自我改进 | 参数/上下文/记忆/技能/Harness 代码进化 | 改进速率、保留率、迁移性 | 低（前沿） | P2 |
| O | Protocols（MCP/A2A/ACP） | 工具集成 N×M、跨 Agent 互操作 | MCP、A2A、ACP、统一 Schema、鉴权 | 集成时间、互操作成功率、安全事件 | 高 | P1 |
| P | Model Selection / Routing / Deployment | 质量-成本权衡、供应商锁定、上线 | Provider 抽象、模型路由、Fallback、FastAPI/Docker/K8s | 质量、成本、可用性、p95 | 高 | P1 |

> 优先级是"对当前项目 + 求职目标"的建议，不是行业统一标准。P0 先做，P1 选做，P2 了解即可。

---

## 2. 方向详解

### A. Context Engineering（上下文工程）

**问题**
- 上下文越长，模型对关键信息的注意力越容易被稀释（Context Rot / Lost in the Middle）。
- 工具结果、历史消息、检索文档、记忆全部堆进窗口，导致成本上升、行为不可预测。
- 动态改工具/改 Prompt 会破坏 Prompt Cache，成本和延迟反而更高。

**优化手段**
1. **分层上下文**：System、Task、Working Memory、Retrieved Evidence、Recent Trace、Archive 分开管理，每层设 token 预算。
2. **Offload**：大结果写到文件/数据库/状态对象，只把"指针 + 摘要"返回给模型。
3. **Retrieve**：RAG、Hybrid、GraphRAG、Agentic Search；需要时再取，不预先全量注入。
4. **Compress**：结构化摘要、工具结果截断、Rerank、语义压缩；先做可逆裁剪，再做 LLM 摘要。
5. **Isolate**：只读子任务交给 Subagent；代码执行放 Sandbox。
6. **缓存友好**：稳定前缀、只追加、JSON 键顺序确定、不要把时间戳放在前缀；工具定义尽量不变。
7. **目标复述**：长任务把 Todo/目标重写到上下文末尾，对抗 Lost in the Middle。
8. **上下文预算**：按层分配 token，低价值内容先淘汰；记录每次请求的 context 组成。

**指标**：tokens/请求、缓存命中率、任务成功率、成本/成功任务、上下文利用率、Lost-in-Middle 回归。
**JD/面试问法**：上下文太长怎么办？Context Engineering 和 Prompt Engineering 的区别？如何设计 context builder？
**本项目现状**：已有 `SummarizationMiddleware`、Todo、PII、Trace；缺分层预算、工具结果截断、缓存友好的前缀设计、ContextEditing。
**证据**：AgentGuide `docs/02-tech-stack/11-context-engineering-practices.md`、`27-agent-harness-engineering.md`；O'Reilly "Stop Overengineering Your Agent Harness"；Manus 实践；Less Context, Better Agents（arXiv 2606.10209）。

---

### B. Tool Engineering（工具工程）

**问题**
- 工具名/描述含糊，模型选错工具或传错参数。
- 工具返回 10,000 行原始数据，塞爆上下文。
- 部分成功、超时、限流、重复副作用没有结构化反馈。
- 工具数量增长后，模型选择准确率下降，动态增删工具又会破坏缓存。

**优化手段**
1. **命名语义互斥**：避免 `search_docs` / `find_docs` 同时存在。
2. **描述面向模型**：写清"什么时候用、什么时候不用、参数含义、失败语义"。
3. **严格 Schema**：JSON Schema、enum、required、默认值；参数校验中间件把错误回注给模型。
4. **结果可控**：分页、截断、摘要、附来源；只返回模型决策需要的信息。
5. **错误可恢复**：结构化错误码 + 可读原因 + 建议动作；区分可重试/不可重试。
6. **幂等**：写操作带幂等 key，避免重试导致重复扣款/重复发邮件。
7. **权限分级**：读自动、写 dry-run + 人审、不可逆显式确认。
8. **工具选择优化**：工具动态检索、LLM Tool Selector、工具分组；尽量不动态增删定义。
9. **协议化**：MCP 统一工具/资源接入，降低 N×M 集成成本。

**指标**：工具选择准确率、参数合法率、无效调用率、重试率、工具 p95、工具结果 token、重复副作用率。
**JD/面试问法**：Function Calling 原理？怎么保证参数正确？工具调用失败怎么办？MCP 是什么？
**本项目现状**：7 个工具、参数校验、ToolRetry/ToolError、ToolCallLimit；缺幂等、结果预算、工具选择评测、MCP。
**证据**：AgentGuide `27-agent-harness-engineering.md`、`03-practice/06-agent-production-challenges.md`；Volt（Zenodo 20419471）；MemTool（ECIR 2026）。

---

### C. Agent Loop / Planning（循环与规划）

**问题**
- 多步任务错误率指数复合；长流程容易早停、死循环、目标漂移。
- 没有明确的停止条件、最大步数、恢复点。
- 计划与执行混在一起，失败后无法局部重试。

**优化手段**
1. **从 ReAct 到 Plan-and-Execute**：先产出可检查的计划，再逐步执行；计划可 replan。
2. **Todo/任务图**：把复杂目标拆成可验证的小步骤，持续更新状态。
3. **Reflection**：执行后自评、发现错误后修正；注意成本和延迟。
4. **停止条件**：最大步数、最大工具调用、明确成功标准、无进展检测。
5. **错误恢复**：工具失败回注、重试、降级、换工具、请求澄清。
6. **中断与恢复**：Checkpoint、Human-in-the-loop、暂停/继续、用户 Steering。
7. **小步可验证**：把 20 步流程拆成 3–5 个可独立验证的操作，关键节点加人审。
8. **路由**：简单任务走单轮/Workflow，复杂任务才上 Agent；不要所有场景都用 Agent。

**指标**：平均步数、成功率、循环率、早停率、恢复率、延迟、成本/成功。
**JD/面试问法**：ReAct 和 Plan-and-Execute 区别？怎么防止死循环？LangGraph 状态机怎么设计？
**本项目现状**：`create_agent`、TodoList、最大模型调用 8 步、ToolCallLimit；缺显式 Plan 节点、replan、用户 Steering、任务图。
**证据**：AgentGuide `27-agent-harness-engineering.md`、`agent-harness-playbook.md`；`03-practice/06-agent-production-challenges.md`；O'Reilly Harness 文章。

---

### D. Memory（记忆）

**问题**
- 跨会话遗忘用户偏好和历史；每次都要重新问。
- 记忆越存越多，噪声淹没重要信息；旧记忆过期或冲突。
- 记忆污染当前上下文，导致错误决策。

**优化手段**
1. **分类**：Working（当前任务）、Episodic（发生过什么）、Semantic（事实/偏好）、Procedural（怎么做）。
2. **MemGPT 式分页**：上下文窗口当 RAM，外部存储当磁盘，按需 page-in/page-out。
3. **巩固管线**：短→长记忆写入前做去重、模式识别、评分和门槛（如 OpenClaw Dreaming 的 Light/REM/Deep 三阶段）。
4. **冲突与更新**：保留时间戳、来源、可信度；偏好是时态状态，不是静态属性；过期记忆退出检索但不删除。
5. **分层存储**：向量库（语义）、全文搜索（精确）、图数据库（关系）、KV（热数据）、对象存储（归档/审计）。
6. **写入门槛**：不是所有对话都值得记；至少满足"多次出现 + 多查询语境 + 高置信度"。
7. **召回防污染**：记忆召回结果要标注来源、时间和置信度，避免直接当成事实。

**指标**：记忆召回准确率、过期率、冲突检测率、跨会话一致性、记忆 token 开销、写入精确率。
**JD/面试问法**：短期/长期记忆怎么设计？Mem0/Zep/MemGPT 区别？记忆冲突怎么处理？
**本项目现状**：只有 `InMemorySaver` 会话记忆；缺长期存储、巩固、冲突/过期、用户画像。
**证据**：AgentGuide `agent-memory-playbook.md`、`27-agent-harness-engineering.md`；MemGPT；Mem0/Zep/HippoRAG。

---

### E. RAG（检索增强生成）

**问题**
- 文档解析/切分不当导致召回失败；纯向量对型号、数字、专有名词不敏感。
- 噪声、过期文档、多跳问题、跨文档冲突。
- 回答没有引用或引用不可信；不知道该拒答。

**优化手段**
1. **解析与切分**：按文档类型差异化切片；表格/代码按结构切；保留来源和页码。
2. **Hybrid Retrieval**：BM25 + 向量 + 加权 RRF；元数据过滤。
3. **Rerank**：Cross-encoder / Cohere Rerank；Top-K 后精排。
4. **Query 改写**：HyDE、Multi-Query、子问题分解、意图识别。
5. **多跳与图谱**：GraphRAG、父子块、Agentic RAG（边检索边推理）。
6. **引用与拒答**：回答带来源；无证据时明确拒答；引用后校验。
7. **评估**：Hit@K、MRR、Recall、Faithfulness、Answer Relevancy、Context Precision/Recall；RAGAS / LLM Judge。
8. **公开基准**：RGB（噪声/拒答/整合/反事实）、MultiHop-RAG（多跳）、HotpotQA 等，用于泛化验证。

**指标**：Hit@K、MRR、Recall、Faithfulness、引用有效率、拒答准确率、延迟、成本。
**JD/面试问法**：RAG 全流程？切块怎么选？Hybrid 和 Rerank 区别？RAG 和微调怎么选？怎么评估 RAG？
**本项目现状**：Hybrid + 本地 BGE + 42 条业务集 + RGB/MultiHop 抽样 + Judge；缺 Rerank、Query 改写、chunk-level 评测、GraphRAG、时效性处理。
**证据**：AgentGuide `02-tech-stack/20-rag-full-pipeline.md`、`04-interview/02-rag-questions.md`；RGB；MultiHop-RAG；RAGAS。

---

### F. Eval / Observability（评测与可观测性）

**问题**
- 只看最终答案会漏掉"答对了但过程错了"：工具没调、权限没验、日志没写。
- Agent 非确定性，一次通过不代表稳定；LLM Judge 有位置、长度、自我偏好等偏差。
- 没有 Trace 就无法复盘，没有回归集就无法防止改坏。

**优化手段**
1. **三层评测**：组件级（Prompt/Tool/Retriever）、轨迹级（步数、工具选择、绕路）、端到端（任务成功）。
2. **三种 Grader**：Code-based（确定性守门）、LLM Judge（主观维度）、Human（校准/关键决策）。
3. **Judge 规范**：结构化 rubric、证据引用、不确定逃生门、一次只评一个维度、人工抽检校准。
4. **指标**：pass@k（至少一次成功）与 pass^k（连续 k 次成功）；后者更适合客服等面向用户的场景。
5. **Benchmark 构建**：从生产日志/投诉聚类采样；150 条 = 50 capability + 50 regression + 30 adversarial + 20 multi-turn hard。
6. **Trace/Replay**：记录 prompt、tool call、结果、token、延迟、成本、权限决策；支持回放。
7. **CI 与上线门**：每次改 Prompt/模型/工具跑回归；Offline Diff → Shadow → A/B → 灰度。
8. **失败归因**：工具选错、检索失败、上下文污染、模型误判、权限不足、业务规则缺失。

**指标**：成功率、pass^k、工具 Precision/Recall、平均步数、p95 延迟、成本/成功、违规率、失败分类分布。
**JD/面试问法**：Agent 怎么评估？LLM-as-Judge 怎么防偏？如何做回归测试？Trace 怎么设计？
**本项目现状**：`data/evals/` 检索/生成/Judge/公开基准，`core/tests/` 13 条行为用例；缺轨迹级评测、CI 回归、OTel、线上反馈闭环。
**证据**：AgentGuide `agent-evaluation-playbook.md`、`26-agent-evaluation-harness-guide.md`；Label Studio；LangChain Evaluation Framework；Arize Agent-as-a-Judge；AWS Eval Harness。

---

### G. Reliability / Error Recovery（可靠性与错误恢复）

**问题**
- 工具超时、限流、空结果、部分成功；重试造成重复副作用。
- 长任务状态丢失，失败后只能从头再来。
- 错误在 trajectory 中传播，越往后越难恢复。

**优化手段**
1. **限制步数/工具调用**：最大模型调用、最大工具调用、无进展检测。
2. **超时 + 熔断**：每个工具设 timeout；连续失败熔断，避免拖垮整个 trajectory。
3. **重试**：指数退避 + jitter；区分可重试错误。
4. **幂等**：写操作带幂等 key；重试不重复扣款/发邮件/写库。
5. **Checkpoint/Resume**：保存状态，支持中断恢复。
6. **补偿/回滚**：写操作失败时执行补偿；关键动作 dry-run。
7. **降级**：备用工具、备用模型、兜底回答、转人工。
8. **故障注入**：在评测中模拟超时、限流、空结果、非法参数，验证恢复能力。

**指标**：故障注入成功率、重试成功率、重复副作用率、恢复时间、p95、人工介入率。
**JD/面试问法**：工具调用失败怎么办？怎么保证高可用？重试会不会重复执行？
**本项目现状**：ToolRetry/ModelRetry、Checkpoint、ToolError、最大步数；缺幂等、熔断、补偿、故障注入评测。
**证据**：AgentGuide `27-agent-harness-engineering.md` 可靠性六件套；`03-practice/06-agent-production-challenges.md`；agent-harness-lab。

---

### H. Safety / Permission / Guardrails（安全与权限）

**问题**
- Agent 执行删除、付款、发布、改配置等不可逆动作。
- Prompt Injection 通过网页/文档/工具结果注入指令。
- PII 泄露、越权访问、审计缺失。
- "私有数据 + 不可信内容 + 外部通信"同时出现（lethal trifecta）风险最高。

**优化手段**
1. **权限分级**：读自动、写 dry-run + 人审、不可逆显式确认。
2. **HITL**：高风险工具审批；拒绝后不执行，并把拒绝原因回注给模型。
3. **Sandbox**：代码/浏览器/文件操作隔离；最小权限；scoped credentials。
4. **Prompt Injection 防护**：外部内容只当数据，不当指令；结构化分隔；工具白名单。
5. **PII**：输入/输出/工具结果脱敏；审计日志。
6. **审计**：记录谁在何时让 Agent 做了什么、批准了什麼。
7. **结构化隔离优于人工审核**：高频场景靠 sandbox/权限边界，而不是每次都靠人看。

**指标**：违规率、审批延迟、误报率、注入成功率、PII 泄露率、审计覆盖率。
**JD/面试问法**：如何防止 Agent 越权？HITL 怎么设计？Prompt Injection 怎么防？
**本项目现状**：`HumanInTheLoopMiddleware` + `reset_device`、PII 脱敏；缺 Sandbox、注入测试、审计日志、scoped credentials。
**证据**：AgentGuide `27-agent-harness-engineering.md`、`03-practice/03-agent-security.md`；O'Reilly Harness 文章；harness-lab。

---

### I. Cost / Latency（成本与延迟）

**问题**
- 对话式 Agent 的 token 成本随轮次近似二次增长；长 trajectory 输入输出比可达 100:1。
- 每步都调大模型，延迟和成本都高。
- 朴素地按请求切模型会破坏 Prompt Cache，反而更贵。

**优化手段**
1. **Prompt Cache**：稳定前缀、只追加、确定性 JSON、缓存断点；缓存命中可显著降成本。
2. **缓存感知路由**：在会话开始时选模型，子 Agent 启动时选模型；避免中途切模型导致 cache 重建。
3. **模型级联/小模型 Gate**：简单任务走小模型，复杂任务升级；路由 + 压缩组合效果最好。
4. **上下文压缩**：工具结果截断、摘要、Rerank；只保留决策相关信息。
5. **批处理/异步/流式**：非实时任务用 batch；前端用流式降低感知延迟。
6. **成本预算**：每个 trajectory 设 token/金额上限；记录成本/成功任务。
7. **本地化**：Embedding、重排、小模型本地跑；只把难例送云端。
8. **Plan Cache**：相似任务复用计划/工具序列，减少重复推理。

**指标**：tokens/任务、成本/成功任务、缓存命中率、TTFT、p50/p95 延迟、路由准确率、降级率。
**JD/面试问法**：怎么降低 Agent 成本？怎么优化延迟？模型路由怎么做？
**本项目现状**：DeepSeek + 本地 BGE，已去掉 Embedding API 成本；缺成本统计、预算、模型路由、Prompt Cache 设计。
**证据**：AgentGuide `03-practice/06-agent-production-challenges.md`；CA3（Zenodo 18916800）；Local-Splitter（arXiv 2604.12301）；Control the Harness（arXiv 2609.28919）；LiteLLM Auto Router。

---

### J. Multi-Agent / Subagent（多 Agent 与子 Agent）

**问题**
- 单 Agent 上下文污染、长任务状态膨胀。
- 多 Agent 协调成本、handoff 信息损失、错误传播、token 成倍增加。
- 很多团队用多 Agent 解决"本可以用单 Agent + 工具"的问题。

**优化手段**
1. **只在合适场景用**：任务可独立拆分、可并行、读多写少、上下文很长。
2. **只读 Fan-out**：让子 Agent 读资料/检索/分析，结果汇总给主 Agent；写操作留在主 Agent + 审批。
3. **上下文隔离**：子 Agent 只拿 brief，不继承父对话；只返回最终报告。
4. **限制轮数**：每个子 Agent 有最大步数、超时、预算。
5. **明确交接**：输入/输出 schema；交接时写清目标、约束、证据。
6. **调度拓扑**：Supervisor、Handoff、Pipeline、Hierarchical；不要为了"角色扮演"而多 Agent。
7. **Worktree/环境隔离**：并行写操作使用独立工作区，避免互相覆盖。

**指标**：并行加速、token 倍数、handoff 信息损失、协调失败率、与单 Agent 的成功率对比。
**JD/面试问法**：什么时候用多 Agent？Supervisor 怎么设计？子 Agent 失败怎么办？
**本项目现状**：暂无多 Agent；建议先做"只读子 Agent fan-out"实验，再考虑写操作。
**证据**：AgentGuide `27-agent-harness-engineering.md`；Rethinking Multi-Agent（arXiv 2609.19759）；Attention Tax（arXiv 2610.06069）；Aalto 实证；Anthropic/Bright Data 实践。

---

### K. Skills / Procedural Memory（技能与程序性记忆）

**问题**
- 同类任务反复纠正，经验没有沉淀。
- 把所有流程写进 System Prompt，token 成本高、缓存易失效。
- Skill 和 Tool/Prompt/Memory 边界不清。

**优化手段**
1. **概念区分**：Prompt（这次怎么做）、Tool（能调用什么）、Memory（知道什么）、Skill（这类事怎么做）。
2. **SKILL.md**：YAML frontmatter（name/description/条件）+ Markdown 步骤 + references/templates/scripts。
3. **渐进式披露**：索引常驻（name + description，约 20 tokens/skill），正文按需读取；100 个 Skill 的索引开销约 2000 tokens。
4. **条件激活**：requires_toolsets / fallback_for_toolsets / platforms。
5. **缓存友好**：Skill 正文以 User Message 注入，不改 System Prompt，避免破坏 Prompt Cache。
6. **Skill 评测**：SkillsBench / SWE-Skills-Bench；对比有/无 Skill 的任务成功率、token、步骤。
7. **Skill 进化**：从成功轨迹蒸馏 SKILL.md（Trace2Skill 等）；注意安全和回归。

**指标**：Skill 召回准确率、token 开销、任务成功率提升、复用率、回归失败率。
**JD/面试问法**：Skill 和 Tool 的区别？为什么不全写进 System Prompt？怎么做渐进式披露？
**本项目现状**：暂无 Skill 机制；可优先做"只读流程 Skill"，如报告生成、故障排查。
**证据**：AgentGuide `agent-skills-procedural-memory-playbook.md`；Claude Code Skills 文档；Harness2（arXiv 2610.14224）。

---

### L. Harness Engineering（Harness 工程）

**问题**
- 模型能力不等于系统能力；工具、状态、上下文、权限、观测决定上限。
- 过度设计 Harness 会拖慢迭代、增加成本；模型升级后很多"补丁"会过时。

**优化手段**
1. **七层模型**：模型层、循环层、工具层、记忆层、人格层、通道层、自驱层；按需逐层加。
2. **可靠性六件套**：幂等、超时/熔断、限流重试、成本上限、权限分级、可观测。
3. **Provider 抽象**：模型调用统一入口，便于路由、降级、统计。
4. **最小 Harness**：只在真实失败出现时加组件；先跑通 L1+L2+L3。
5. **分层分离**：Agent core / 业务场景 / 通道适配器分离；场景通过 Scenario 注入工具和 Prompt。
6. **Trace 驱动迭代**：用失败轨迹决定下一个 Harness 组件，而不是拍脑袋。

**指标**：任务成功率、失败归因、成本/成功、迭代速度、组件引入后的净收益。
**JD/面试问法**：什么是 Harness？Agent = Model + Harness 怎么理解？怎么设计一个 Agent 系统？
**本项目现状**：已做 `core/agent/framework.py` + `core/scenarios/` 分离、LangGraph 工作流、内置中间件；下一步用 Trace/Eval 驱动组件取舍。
**证据**：AgentGuide `27-agent-harness-engineering.md`、`agent-harness-playbook.md`；O'Reilly "Stop Overengineering Your Agent Harness"；harness-lab。

---

### M. Post-training / Agentic RL（后训练与 Agentic RL）

**问题**
- 通用模型在工具选择、长程任务、领域策略上不够稳定。
- 长程信用分配困难；奖励稀疏；Reward Hacking；环境构建成本高。
- 应用工程师通常不训练模型，但需要理解数据飞轮和评测。

**优化手段**
1. **SFT/LoRA/QLoRA**：用高质量轨迹/工具调用数据做行为克隆。
2. **偏好优化**：DPO/GRPO/PPO；规则奖励、Verifier、LLM Judge 组合。
3. **Agentic RL**：长程环境、稠密进度奖励、可验证奖励、自博弈。
4. **环境构建**：latent-spec-first、沙盒池、可重置环境、可执行检查。
5. **Reward 防作弊**：Verifier 完整性审计、隐藏探针、内部状态验证。
6. **数据飞轮**：线上 Trace → 失败分类 → 标注/合成 → 训练/评测 → 回归。

**指标**：任务成功率、pass@k、样本效率、泛化、Reward Hacking 率、环境覆盖率。
**JD/面试问法**：SFT 和 RL 怎么选？GRPO 是什么？怎么做 Agent 轨迹数据？
**本项目现状**：不做训练；可积累 eval/轨迹数据，为后续算法岗或数据飞轮做准备。
**证据**：AgentGuide `02-tech-stack/21-agent-reinforcement-learning.md`、`25-post-training-complete-guide.md`；Tev（arXiv 2610.18868）；VERA；Explorer-Zero（arXiv 2610.19868）。

---

### N. RSI / Self-evolution（递归自我改进）

**问题**
- 人工迭代速度跟不上模型/环境变化；经验无法自动沉淀。
- 自我改进容易失控、遗忘、奖励作弊。

**优化手段**
1. **五个改进层级**：参数进化、上下文进化、记忆进化、技能进化、Harness 代码进化。
2. **三种拓扑**：链式、树式、图式；树/图保留回退和融合能力。
3. **更新主体**：自更新、教师更新、联合更新。
4. **更新模式**：离线、在线、混合。
5. **MetaRSI**：Data-RSI、Harness-RSI、Model-RSI。
6. **成熟度路线**：L1 执行自治 → L2 策略自治 → L3 经验获取自治 → L4 环境适配自治 → L5 元递归自治。
7. **安全边界**：改进必须可回滚、可评测、可审计；先做 Harness/Skill 级，不碰权重。

**指标**：改进速率、能力保留率、跨任务迁移、回归失败率、安全违规率。
**JD/面试问法**：什么是 RSI？Self-evolving Agent 怎么做？如何防止自我改进失控？
**本项目现状**：暂无；对应用工程师最现实的是"Skill/Harness 级进化"，不是参数级。
**证据**：AgentGuide `docs/06-research-frontiers/02-recursive-self-improvement-landscape.md`。

---

### O. Protocols：MCP / A2A / ACP

**问题**
- 每个工具/数据源都要定制集成，N×M 成本高。
- Agent 之间、Agent 与宿主应用之间缺少统一接口。
- 工具权限、鉴权、审计不统一。

**优化手段**
1. **MCP**：统一 Tools / Resources / Prompts；客户端-服务器模型；工具发现与调用标准化。
2. **A2A**：Agent 发现、通信、协作；跨框架/跨厂商。
3. **ACP**：宿主应用与 Agent 的统一接口。
4. **统一 Schema/错误码/鉴权**：工具描述、参数、返回、权限一致。
5. **安全**：MCP Server 最小权限、Sandbox、审计、信任边界。

**指标**：集成时间、工具可用性、互操作成功率、权限违规率、延迟。
**JD/面试问法**：MCP 是什么？MCP 和 Function Calling 区别？A2A 解决什么问题？
**本项目现状**：暂无 MCP；可先做只读工具 MCP Server，验证接入成本。
**证据**：AgentGuide `27-agent-harness-engineering.md`、`00-getting-started/01-agent-map.md`；MCP 文档；A2A 规范。

---

### P. Model Selection / Routing / Deployment

**问题**
- 不同任务对质量/成本/延迟要求不同；单一模型不经济。
- 供应商锁定；模型升级/故障需要快速切换。
- 上线需要 API 服务、容器、监控、灰度。

**优化手段**
1. **Provider 抽象**：统一模型调用、工具调用、流式输出、错误处理。
2. **缓存感知路由**：会话级选模型，避免中途切换破坏缓存。
3. **模型级联**：小模型 gate → 大模型升级；按任务复杂度/风险路由。
4. **Fallback**：主模型失败切备用模型/供应商。
5. **部署**：FastAPI + Docker + K8s；健康检查、限流、超时、日志。
6. **可观测**：token、延迟、错误率、成本、模型版本。
7. **本地/云混合**：Embedding/重排/小模型本地，难例上云。

**指标**：质量、成本/成功、p95、可用性、路由准确率、降级率。
**JD/面试问法**：怎么选模型？模型路由怎么做？怎么部署 Agent 服务？
**本项目现状**：工厂支持 DeepSeek/DashScope + 本地 BGE；缺路由、成本统计、部署编排。
**证据**：AgentGuide `27-agent-harness-engineering.md`；CA3；Local-Splitter；Control the Harness；LiteLLM Auto Router。

---

## 3. 岗位 JD 映射

| JD 高频要求 | 对应方向 | 可证明的作品/指标 |
|:---|:--:|:---|
| RAG 全链路：解析、切分、Embedding、混合检索、Rerank、评估 | E | 42 条业务集 + RGB/MultiHop 抽样；Hit@4/MRR、Faithfulness、拒答率 |
| LangChain / LangGraph / 工作流编排 | C/L | `create_agent`、YAML 工作流、状态图、HITL、Checkpoint |
| Function Calling / Tool Use / MCP | B/O | 7 个工具、参数校验、错误回注、ToolRetry；MCP Server（待做） |
| Context Engineering | A | 分层上下文、Summarization、Token 预算、缓存友好前缀 |
| Memory：短期/长期、用户画像 | D | Checkpoint 会话记忆；长期记忆/巩固（待做） |
| 评测体系、LangSmith/Langfuse/Phoenix、Badcase | F | `data/evals/`、Judge、回归集、Trace；CI/OTel（待做） |
| 成本/延迟优化、模型部署 | I/P | DeepSeek + 本地 BGE；成本/成功、p95（待做） |
| 安全、Guardrails、HITL、PII | H | HITL 审批、PII 脱敏；Sandbox/注入测试（待做） |
| Multi-Agent / Supervisor / A2A | J/O | 只读 Subagent fan-out（待做） |
| 微调 / Post-training / Agentic RL（加分） | M | 理解 SFT/LoRA/GRPO、轨迹数据、Verifier（了解即可） |

**JD 观察**：2026 年岗位普遍要求"能对业务效果负责"——不只是会调 API，而是能设计评测、控制成本、定位 badcase、保证上线质量。这正好对应 F/G/I/H 四个方向。

---

## 4. 2026 年趋势判断（公开资料）

1. **选择性上下文 > 全量注入。**
   Volt、Less Context Better Agents、Needlepath 等工作一致表明：按决策相关性选择上下文，比把所有资料塞进窗口更有效；压缩/检索/记忆要联合设计。

2. **上下文优化必须和规划/执行一起做。**
   REALM 2026 的 WebArena 失败分析发现：只修上下文只能救回不到 10% 的失败；连续的状态/规划改进才能带来 19–38% 提升。

3. **缓存感知路由，而不是按请求切模型。**
   每个用户 turn 在 Agent 中会变成多次模型调用，中途切模型会破坏 Prompt Cache；正确做法是会话级选模型、子 Agent 启动时选模型、缓存友好的路由。

4. **评测从"看答案"转向"看轨迹"。**
   Label Studio、LangChain、Arize 等都在强调 trajectory evaluation、step-aware judge、Agent-as-a-Judge；只看最终答案会漏掉工具错误、权限跳过、轨迹作弊。

5. **多 Agent 是结构/成本优化，不是能力解锁。**
   多 Agent 在可并行、独立、读多写少的任务上有优势；顺序依赖强的任务反而更差。只读 fan-out 最安全，写操作留在主 Agent + 审批。

6. **Skills + 渐进式披露 + 最小 Harness。**
   不要把流程全写进 System Prompt；用 SKILL.md 索引 + 按需加载；不要过度设计 Harness，按真实失败逐步加组件。

7. **Agentic RL 走向稠密奖励、可验证环境、Verifier 完整性。**
   Tev、VERA、Explorer-Zero 等工作聚焦长程环境、进度奖励、防奖励作弊；应用工程师可以先积累轨迹和评测数据。

8. **RSI 最现实的入口是 Harness/Skill 级进化。**
   参数级 RSI 风险高、门槛高；对应用团队，先做 Skill 蒸馏、Harness 自动调优、评测驱动迭代。

---

## 5. 本项目的优先级 Backlog（暂不改代码）

> 原则：每个方向先有"问题 + 指标 + 基线 + 一周实验"，再动代码。不要因为"别人都在做"就加组件。

| 优先级 | 方向 | 当前状态 | 下一步验证 | 预期产物 |
|:--:|:---|:---|:---|:---|
| P0 | 上下文预算 + 缓存友好 | 有 Summarization/Todo | 记录 context 组成；对比压缩前后 tokens/成功率 | context 预算表 + A/B |
| P0 | 工具结果截断 + 幂等 | 有校验/重试 | 模拟超时/重复写入；对比 token 和重复副作用 | 工具契约 + 故障注入 |
| P0 | 轨迹级评测 + CI | 有答案级 eval | 记录工具序列/步数/成本；加回归门 | trajectory eval + CI 报告 |
| P0 | RAG Rerank + Query 改写 | Hybrid + BGE | 对比有无 Rerank/改写的 Hit@K/MRR | 检索消融表 |
| P0 | 冲突/拒答处理 | 有 42 条业务集 | 冲突题并列来源；拒答规则 | 冲突/拒答专项报告 |
| P1 | 长期记忆 + 巩固 | 只有 Checkpoint | 设计写入/召回/过期；小规模实验 | Memory v1 |
| P1 | Skills 渐进式披露 | 无 | 先做 2 个只读 Skill | Skill 索引 + 按需加载 |
| P1 | 成本/延迟统计 | 本地 BGE 已降本 | 记录 tokens/成本/p95 | 成本看板 |
| P1 | MCP 只读 Server | 无 | 接入 1 个外部工具 | MCP demo |
| P1 | Sandbox + 注入测试 | 有 HITL/PII | 红队 case；沙盒隔离 | 安全测试集 |
| P2 | 只读 Subagent fan-out | 无 | 对比单 Agent 的成功率/token | 多 Agent 实验报告 |
| P2 | Agentic RL / RSI | 无 | 只做资料和轨迹积累 | 方向笔记 |

---

## 6. 持续搜集机制

### 6.1 信息源分层

| 层级 | 来源 | 用途 |
|:---|:---|:---|
| A（官方） | Anthropic Engineering、OpenAI Guides、LangChain Docs、Claude Code Docs、MCP/A2A 规范 | 机制和最佳实践 |
| B（论文/基准） | arXiv、ACL/NeurIPS/ICML、RGB/MultiHop/SWE-bench/GAIA、RAGAS | 新方法、指标、可复现实验 |
| C（岗位/社区） | 招聘 JD、牛客/小红书面经、工程博客、开源 harness | 岗位要求、真实痛点 |

### 6.2 每周 30 分钟例程

1. 扫 AgentGuide 新增/更新文档（`docs/`、`docs/06-research-frontiers/`）。
2. 扫 1–2 篇官方工程博客（Anthropic/OpenAI/LangChain）。
3. 扫 3 条 JD（初级/中级/高级各 1 条），提取高频词。
4. 扫 1–2 篇论文/基准，记录"问题-方法-指标-局限"。
5. 更新本文件：总览矩阵、方向详解、JD 映射、趋势。
6. 在更新日志记一行；没有证据的方向不升级优先级。

### 6.3 证据规则

- **A**：官方文档/工程博客，可直接引用。
- **B**：论文/基准，记录样本量、指标、局限，不把单一结果当定论。
- **C**：JD/社区，只作为需求信号，不作为技术结论。
- 每个方向至少要有：问题、手段、指标、失败模式；缺一项就标"待补"。

### 6.4 不做什么

- 不在没有指标的情况下加组件（Memory、Multi-Agent、Skill）。
- 不把公开 benchmark 分数当业务效果；公开基准只证明泛化，不证明场景价值。
- 不为了"看起来高级"引入多 Agent/复杂 Harness。
- 不在没有 Trace/Eval 的情况下做"感觉变好"的优化。

---

## 7. 更新日志

| 日期 | 版本 | 更新 |
|:---|:---|:---|
| 2026-10-27 | v1.0 | 首版：16 个方向、JD 映射、2026 趋势、优先级 backlog、持续搜集机制 |

---

## 8. 参考来源

### AgentGuide（本地仓库）

- `docs/02-tech-stack/11-context-engineering-practices.md`
- `docs/02-tech-stack/27-agent-harness-engineering.md`
- `docs/03-practice/06-agent-production-challenges.md`
- `docs/02-tech-stack/26-agent-evaluation-harness-guide.md`
- `docs/04-interview/18-agent-interview-playbooks/agent-evaluation-playbook.md`
- `docs/04-interview/18-agent-interview-playbooks/agent-harness-playbook.md`
- `docs/04-interview/18-agent-interview-playbooks/agent-memory-playbook.md`
- `docs/04-interview/18-agent-interview-playbooks/agent-skills-procedural-memory-playbook.md`
- `docs/06-research-frontiers/02-recursive-self-improvement-landscape.md`
- `docs/00-getting-started/01-agent-map.md`
- `docs/04-interview/02-rag-questions.md`
- `docs/04-interview/03-agent-questions.md`

### 公开资料

- Anthropic, Building effective agents: https://www.anthropic.com/engineering/building-effective-agents
- OpenAI, A practical guide to building agents: https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/
- O'Reilly, Stop Overengineering Your Agent Harness: https://www.oreilly.com/radar/stop-overengineering-your-agent-harness/
- agent-harness-lab: https://github.com/mothieras/agent-harness-lab
- Less Context, Better Agents (arXiv 2606.10209): https://browse-export.arxiv.org/abs/2606.10209
- Volt: https://zenodo.org/records/20419471
- CA3 cost-aware agent architecture: https://zenodo.org/records/18916800
- Local-Splitter: https://ar5iv.labs.arxiv.org/html/2604.12301
- Control the Harness: https://export.arxiv.org/pdf/2609.28919
- LiteLLM Auto Router: https://docs.litellm.ai/docs/auto_router/index.md
- Rethinking Multi-Agent Collaboration: https://export.arxiv.org/html/2609.19759v2
- Attention Tax, Handoff Tax (arXiv 2610.06069)
- Label Studio, How to evaluate AI agents in production: https://labelstud.io/blog/how-to-evaluate-ai-agents-in-production/
- LangChain, LLM Evaluation Framework: https://www.langchain.com/resources/llm-evaluation-framework
- Arize, Agent-as-a-Judge: https://arize.com/blog/agent-as-a-judge-agentic-evaluation/
- AWS, Building Evaluation Harnesses for AI Agents: https://builder.aws.com/content/3GnUwSe4nZox997OebVae0Z4buH/does-your-agent-actually-work-building-evaluation-harnesses-for-ai-agents-on-aws
- trajectory-judge: https://pypi.org/project/trajectory-judge/0.2.0/
- Tev (arXiv 2610.18868): https://huggingface.co/papers/2610.18868
- Explorer-Zero: https://export.arxiv.org/abs/2610.19868
- VERA paper note: https://github.com/AkihikoWatanabe/paper_notes/issues/6808
- MCP: https://modelcontextprotocol.io/
- A2A: https://google-a2a.github.io/A2A/specification/
- Claude Code Skills: https://code.claude.com/docs/en/skills
- LangChain Docs: https://docs.langchain.com/
- RAGAS: https://github.com/explodinggradients/ragas

### 岗位 JD（示例）

- 美团，服务零售-大模型/AI 应用开发工程师：https://zhaopin.meituan.com/web/position/detail?jobUnionId=4148767793
- 厦门人才网，大模型应用开发工程师：https://www.xmrc.com.cn/Recruit/RecruitInfo/?id=2bd2962e95864631859e280961cc3e59
- 太原理工大学就业网，AI 应用开发相关岗位：https://career.tyut.edu.cn/Zhaopin/zhiweiDetail.html?jobtype=1&id=61371b9e-4711-b81f-f661-cbd7505ebbca
- Randstad，AI Agent 工程师：https://cn-lb-prod.prd.bluexcn.randstad.cn/jobs/apply/90M0153618_20121_CN/
- O*NET, Agentic AI Software Engineer: https://www.onetonline.org/link/jobinfo?id=B796B888656945AF8CA4C701290CAF83206

> 注：公开资料和 JD 日期集中在 2026 年；访问时间 2026-10-27。论文结论以原文为准，本文只做方向归纳。
