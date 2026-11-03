# 面试问答稿（2026-11-04）

> 配套：`docs/interview/interview-pack-2026-11-04.md`（简历 / 30s / 2min / demo）
> 数字来源：`docs/interview/jd-results-2026-11-04.md`
> 原则：有实现、有结果、有边界的才展开；没有的用三句话承认，不硬编。

## 0. 回答模板

**有实现的题**：结论 → 机制 → 数字 → 边界。

**没有实现的题**：
> “这块我没做过真实实现。我的理解是【一句话原理】。如果要做，我会从【最小闭环】开始。”

**被追问到不会的细节**：
> “这个点我没验证过，不敢下结论。我的判断依据是【已知事实】，回去会用【实验】确认。”

---

## A. 开场与定位

### A1. 用 2 分钟介绍这个项目

> 我做了一个面向办公、学习、内容创作和跨语言的 Agent Harness。它不是接一个大模型就完了：我用 LangChain 1.x + LangGraph 把 ReAct 循环、工具调用、MCP、工作流、只读子代理、权限审批和评测做成一个可切换场景的运行时，再用智能硬件客服场景验证高风险操作。
>
> 我重点解决三件事：第一，工具选错/传错/超时/越权时，系统有可预期的行为；第二，复杂任务什么时候该委派、什么时候不该委派，由 Harness 显式决策，而不是赌模型；第三，评测不只看回答文本，而是检查文件、SQLite、任务图和路由 trace。
>
> 结果是 8 个场景、44 条行为用例、12 条 outcome 用例 / 13 个断言；workspace 5/5、research 2/3、router 3/4；outcome 3-trial 12/12。多模态和多 Agent handoff 我没做，这是明确边界。

### A2. 这个项目你个人做了什么？哪些是框架自带的？

> LangChain 的 `create_agent` 和 LangGraph 的状态图是框架能力，我不假装自己重写了 Agent loop。我做的是：Scenario 契约、14 层中间件的组合与顺序、工具与场景实现、planning policy、outcome 评测、trace/cost 聚合、dashboard、测试和评测口径。换句话说，框架负责循环，我负责让它可约束、可观测、可评测。

### A3. 为什么叫 Harness，不叫 Agent 框架？

> 因为模型不是产品。同一个 DeepSeek，配上不同的工具、上下文、权限、状态和评测，效果完全不一样。Harness 是模型外面那一层：工具注册、上下文管理、状态、权限、预算、trace、eval。我的项目价值主要在这一层，不在模型。

### A4. 这个项目最大的价值是什么？

> 把“Agent 好不好”拆成可验证的几件事：工具选对没有、参数对不对、失败能不能恢复、高风险操作有没有审批、改完有没有回归。比如 router 行为层 3/4，但 outcome 层 4/4——说明回答措辞有问题，路由本身是对的。这种区分比一个总分有用。

### A5. 如果重做一次，你会怎么改？

> 先做评测和 outcome 断言，再做功能。现在这个项目是功能先长出来、评测后补；如果重来，我会先定 20 条任务和通过标准，再决定要不要加 MCP、多 Agent。第二，场景少一点、深一点；第三，planner 从第一天就做，而不是先靠 prompt。

---

## B. 架构与运行时

### B1. 为什么用 LangChain / LangGraph，不自己写循环？

> LangGraph 已经提供了状态、条件边、中断恢复、checkpoint 这些运行时能力，自己重写收益不大。Harness 的价值在中间件和评测，不在重写 while 循环。如果框架抽象泄漏，我也知道怎么用状态机重写；但当前阶段，用成熟运行时更快。

### B2. 14 层中间件的顺序为什么这样？举两个关键的。

> 两个关键顺序：
> 1. 权限在最外层：deny 的工具不会进入 HITL、超时、重试链路，避免“先审批再拒绝”的浪费。
> 2. HITL 在超时之前：人工审批时间不计入工具超时；ToolError 在外、ToolRetry 在内，先重试，重试耗尽再把异常转成可读的 ToolMessage。
>
> 其余是参数校验、hooks、Todo、Summarization、PII、ToolCallLimit、TokenBudget、ModelFallback、ModelRetry。

### B3. 工具调用失败怎么处理？

> 分四层：
> 1. 参数校验失败：返回带修正提示的 error ToolMessage，让模型自己改；
> 2. 工具异常：ToolRetry 重试一次，仍失败由 ToolError 转成中文可读错误；
> 3. 超时：ToolTimeout 中断等待，返回超时消息；
> 4. 死循环：ToolCallLimit + LimitSteps 兜底。
>
> 5 类故障注入测试覆盖了超时、权限、参数错误、空检索、拒答。

### B4. 上下文太长怎么办？

> Summarization 在 30 条消息触发、保留 12 条；TokenBudget 在每次模型调用前检查；工具结果截断/分页；subagent 用 fresh context 隔离；Todo 列表放在上下文后部，缓解“lost in the middle”。还没做 prompt cache 友好的前缀设计和分层预算。

### B5. 多轮记忆怎么实现？

> LangGraph checkpointer，按 `thread_id` 恢复；SQLite 持久化，所以重启后同一 thread 还能继续。workspace 场景另有 `MemoryStore`，SQLite KV，用于跨会话的偏好 `remember/recall`。Memory MCP 是外部演示。语义记忆/巩固/冲突消解没做。

### B6. 模型换掉/不稳定怎么办？

> `core/llm/factory.py` 做了 provider 抽象；`ModelFallbackMiddleware` 代码里有，但当前场景都传 `None`，没有真正启用。实际观察到 DeepSeek 和 Qwen 的工具调用风格不同：Qwen 更愿意调工具，DeepSeek 更保守。所以评测不能绑死一个模型，Harness 要允许换。

### B7. 为什么不用自动的 LLM planner？

> 小场景集合（4 个路由）用规则 policy 更便宜、更确定；LLM planner 会增加一次模型调用和方差。我的 policy 还保留 abstain：规则不唯一命中就交回模型。开放域场景可以换成 embedding/LLM 分类器，但要用准确率、abstain 率、延迟来选，不能凭感觉。这个我没做，是下一步。

---

## C. Planning / 路由

### C1. 你的 planner 怎么工作？

> `PlanningPolicyMiddleware` 在第一次模型调用前做关键词 + 优先级分类。命中唯一规则时，注入一条带 `tool_calls` 的 `AIMessage` 并 `jump_to="tools"`；不命中、分数不足或平局就 abstain，交回模型。它不是自主 planner，是确定性的 Harness 策略。
>
> 数字：router baseline 11/12 → policy 12/12；平均模型调用 1.92 → 1.08；1 条 abstain 后模型兜底仍正确。

### C2. 为什么用注入，不让模型自己规划？

> 提示词不可验证。模型可以说“我会先规划”，但实际不调用工具。注入是 Harness 层的确定性动作，可测、可审计，而且省一次模型调用。保留 abstain 是为了避免误路由：规则没把握时，交回模型比硬路由安全。

### C3. 触发率 0/10 怎么解释？

> 那 10 条是简单文件检查，不需要委派，0/10 是不过度委派，不是机制坏了。换成 policy 后，eligible 3/10 全部触发，另外 7/10 保持不委派。research 的报告任务 3/3 都用了 3 个 subagent。所以不是“模型不会委派”，是“简单任务不该委派”。

### C4. research 只有 2/3，为什么？

> `research-compare-001` 有一次/两次直接 `read_source`，没有走 subagent 或 search_sources，但内容覆盖是对的；用例要求 `expected_tools_any=["subagent","search_sources"]`，所以判失败。这是真实的工具选择缺口，不是评分 bug。下一步是把复杂度判断也做成 policy，而不是继续调 prompt。

### C5. 为什么不用 LLM 做 router？

> 可以，但成本和方差更高。4 个场景的 closed set 用规则足够；开放域才需要语义 router。即使用 LLM，我也会保留 abstain 和兜底，不会让它 100% 强制路由。

---

## D. 评测与 outcome

### D1. 你的评测分几层？

> 三层：
> 1. capability：直接调工具，测 RAG 检索/生成，不让模型改写 query；
> 2. behavior：完整 Agent 跑 44 条 cases，测工具选择、传参、多步执行、拒答；
> 3. outcome：12 条用例 / 13 个断言，检查文件、SQLite、任务图、路由 trace。
>
> 另外有公开 benchmark 抽样、gate、5 类故障注入。

### D2. 什么是 transcript vs outcome？举个例子。

> Router 行为层 3/4：最后回答没覆盖期望词，transcript 判失败。但 outcome 层 4/4：`route_to_research` 的 target 正确，`target_trace_id` 也能在 trace 文件找到。回答措辞可能骗人，路由动作不会。
>
> 再比如 workspace 说“笔记已保存”，outcome 检查 user 笔记目录真的多了文件；说“记住了”，检查 SQLite 真有这行。

### D3. Outcome 断言怎么保证不 flaky？

> 四个做法：
> 1. 每条用例生成唯一 `run_id`，写进内容标记，避免重复运行互相污染；
> 2. 运行前快照目录，运行后只检查新增文件，不依赖固定文件名；
> 3. 断言只读文件/DB/trace，不调用模型；
> 4. 3-trial；失败保留具体 check 原因。
>
> 限制：模型如果完全不调用写工具，还是会失败；这是真实失败，不降低断言。

### D4. 3-trial 够吗？pass^k 和 mean 有什么区别？

> 3-trial 是小样本，不做统计显著声明。pass^k = 所有 trial 都通过；mean = 通过 trial 的比例。客服/办公场景每个用户都要成功，所以 pass^k 更合适。5–10 trial + bootstrap CI 是下一步。

### D5. 公开 benchmark 数字怎么来的？可信吗？

> BFCL 200 条抽样、简化评分；τ² retail 20 条、官方 harness 但 NL judge 用 DeepSeek 替代；RGB 20 条、16 条可回答参与评分；MultiHop 全量 2255 条、Hits@4 57.07%，中文 BGE 检索英文语料，是弱配置。它们证明泛化方向，不是官方榜单，也不是业务效果。

### D6. 你怎么做 badcase 分析和优化循环？

> 5 轮优化循环：baseline → routed prompts → hybrid → english embedding → arg validation。BFCL 51/60 → 55/60，RAG 40/45 → 44/45；记录 fixed/regressed，失败归档。最后加 Python 语法提示，BFCL 60/60 两轮复跑；RAG 保持 44/45，0 回归。注意 60 条抽样不等于官方 100%。

### D7. 评测有没有过拟合/泄漏？

> 自建 cases 和公开样本分开；公开样本固定 seed；优化循环用同一批样本做 A/B，存在过拟合风险，所以我会保留失败集和独立场景。LLM judge 和回答模型同属 DeepSeek，有 self-preference 风险；没有人工校准。这是评测的已知局限。

---

## E. Tool Calling 与 MCP

### E1. MCP 怎么接的？stdio 够吗？

> `MultiServerMCPClient` 接两个 server：官方 Memory（跨会话记忆）和本地 Fetch（FastMCP）。工具名前缀 `memory_*`/`fetch_*`，async 工具包装成同步 LangChain 工具。Fetch 有域名白名单、私网拦截、200KB 截断、输出标记 untrusted。
>
> stdio 适合本地 demo；生产要补 HTTP/SSE、auth、多 server 治理、健康检查、prompt-injection 分类器。我没做过生产 MCP 网关，不把它说成生产级。

### E2. 你怎么做工具权限/安全？

> `tool_policy` 按风险级别 allow/deny；高风险工具接 HITL；工具超时；workspace 路径保护、受保护目录拒绝、危险命令拒绝；PII 输入脱敏；Fetch 域名白名单/私网拦截。没有容器沙箱。

### E3. MCP 工具有没有 prompt injection 风险？

> 有。工具输出是数据，不是指令。我做的是 allowlist、截断、untrusted 标记、高风险 HITL；没有注入分类器。原则是“模型可以建议，系统负责授权”，不能只靠 prompt 防注入。

### E4. 为什么没把自有工具包成 MCP server？

> 自有用具已经在进程内注册，包一层 MCP 不会让业务工具变好；MCP 的价值在工具发现层。真要做，可以用 FastMCP 把 workspace/research 工具暴露出去，加 schema 和权限，但这是集成工作，不是当前重点。

---

## F. RAG

### F1. RAG 怎么做的？为什么 hybrid？

> 文档解析 → 按类型切分 → 本地 BGE → Chroma → 向量 + BM25 加权 RRF。hybrid 在 45 条 MultiHop 抽样上把 RAG 从 40/45 提到 44/45，0 回归；小语料上 Hit@4 已经饱和，MRR 更有区分度。

### F2. RAG 怎么评？42 条为什么不能用？

> 检索看 Hit@4/MRR；生成看要点覆盖、引用、拒答。42 条是服装尺码域的历史数据，和当前扫地机器人知识库不匹配，不能当当前结果。当前用 RGB/MultiHop 抽样和场景行为用例。

### F3. MultiHop 57% 怎么解释？

> 2255 条评分，Hits@4 57.07%（95% CI 55.02–59.10）。中文 BGE 检索英文语料，是弱配置；只评检索召回，不评生成。它说明检索方向可用，但不是业务结论。

### F4. 为什么不做 rerank / query rewrite / GraphRAG？

> 没做。rerank 和 query rewrite 是下一步，会先用检索消融证明增益；GraphRAG 需要多跳图结构，当前语料小，收益不明显。没有指标前不堆组件。

---

## G. Memory

### G1. 长期记忆怎么做的？

> checkpoint 是短期会话状态；workspace 的 `MemoryStore` 是 SQLite KV，跨会话 `remember/recall/list`；Memory MCP 是外部演示。没有语义记忆、用户画像、巩固、衰减、冲突消解。

### G2. 为什么不上向量记忆/用户画像？

> 场景里偏好是 KV 就够：key/value 明确、量小、要精确召回。向量记忆要解决“什么时候存、怎么检索、什么时候忘、冲突怎么合并”，没有指标前上向量库是过度设计。下一步可以先做 SQLite + 向量召回，再用命中率/冲突率评估。

---

## H. 工作流与多 Agent

### H1. 为什么不做多 Agent？

> 客服/办公任务顺序依赖强，子任务要频繁交换状态，handoff 成本大于收益。我只做只读 fan-out：research 把三份资料分给三个 subagent，各自 fresh context，只回摘要，主 Agent 汇总和写报告。写操作留在主 Agent + HITL。

### H2. 你的 subagent 怎么隔离？

> 子 Agent 有 fresh context、独立 thread、checkpoint 关闭；工具白名单排除 `subagent` 自身，禁止递归；有最大模型调用数、token 预算、超时；只返回最终摘要。

### H3. router 和 multi-agent 的区别？

> router 是场景级分发：调一个目标场景的 FrameworkAgent，返回答案和 target trace；没有协商、共享状态、handoff、supervisor。它不是多 Agent 协作。

### H4. 工作流和 Agent 怎么选？

> 固定步骤走 LangGraph 工作流，开放决策走 ReAct。比如文档问答、学习笔记、跨语言摘要、报告生成是固定链路；什么时候检索、检索几次、是否拒答，交给 Agent。7 条工作流都是这个原则。

---

## I. 可观测与成本

### I1. Trace 记了什么？

> model/tool 的 start/end/error、token、latency、cost、trace_id、run_end 汇总；dashboard 能做 trace 时间线，测试详情能下钻到 case→tool→middleware→eval function→trace。

### I2. 成本/时延怎么统计？怎么优化？

> 聚合 JSONL trace：成功率、p50/p95、token、按模型/工具/场景的成本。优化手段：本地 BGE 去掉 Embedding API 成本；token 预算和工具调用上限防跑飞；DeepSeek 比 Qwen 便宜。没有生产 SLA、并发、缓存命中率。

### I3. 为什么没有 OTel / LangSmith？

> 个人项目先做本地 JSONL，数据模型和聚合是自己写的；接 OTel/LangSmith 是 exporter 集成，不是核心难点。没有采样、告警、trace PII 脱敏。

### I4. p50/p95 数据怎么来的？为什么用示例价？

> 3,203 条历史 run 的 trace 聚合：p50 2.50s / p95 8.54s；成本按 `config/observability.yml` 的示例单价（输入 ¥2/M、输出 ¥8/M）估算，不是 DeepSeek 账单。最新聚合 3,495 runs / 96.7%，包含故意失败的负向用例，不是产品成功率。

---

## J. 安全与生产化

### J1. HITL 怎么实现？模型自己拒绝怎么办？

> `HumanInTheLoopMiddleware` 拦截 `reset_device` 高风险工具，approve 才执行，reject 把原因回注给模型。DeepSeek 有时自己先拒绝调用，这是双层保护，不是 Bug。

### J2. PII 怎么处理？

> workspace 场景对 email / credit_card / ip 做输入侧 redact；没有做输出和工具结果脱敏，也没有完整 DLP。原则是 secrets 只在工具执行层，trace 里不记敏感信息——这一条我还没完全做到。

### J3. 生产化要补什么？

> API/鉴权/限流/并发/队列/高可用/监控告警/容器沙箱/CI；当前是单进程 + SQLite + Streamlit。项目定位是 Harness，不是生产服务。

### J4. 沙箱/权限边界？

> 工具 allow/deny、路径保护、危险命令拒绝、Fetch 域名白名单/私网拦截、HITL；`run_command` 是进程内 shell，不是容器沙箱，没有注入分类器。这是明确边界。

---

## K. 多模态与缺口

### K1. 多模态/语音/OCR 为什么没做？

> 【没有，不要展开】没做过真实实现。现有 RAG 只到文本/PDF/docx，扫描 PDF 会明确提示需要 OCR。如果团队需要，我会先做 OCR 文档解析 → 保留页码/版面 → 文本/表格/图片多索引 → 证据包 → 分题型评测，不会一上来做端到端多模态 Agent。

### K2. 端侧/端云协同？

> 【没有】本地 BGE 只是本地 Embedding，不是端侧 LLM；没有端侧推理、云边协同、模型量化/蒸馏。这块我不冒充做过。

### K3. 如果给你两周补多模态，怎么做？

> 第一周做最小闭环：OCR/版面解析、页码和 bbox 保留、文本/表格/图片 caption 多索引、证据包；第二周做评测：文本题/表格题/图题分开算，加引用准确率和拒答。先证明检索和证据链，不先做多模态生成。

---

## L. 行为面

### L1. 这个项目最难的地方？

> 不是写工具，是让失败可定位。比如 research 的 2/3，表面是“回答不对”，实际是工具选择；router 的 3/4，表面是“回答不对”，实际是最终措辞。我要把行为层和 outcome 层分开，才能定位到是模型、工具、检索还是评分的问题。

### L2. 你最大的失败/踩坑？

> 一开始只做 transcript 评测，回答里说“已保存”就判通过；后来发现文件根本没写。于是补了 outcome 断言，用文件/DB/任务图/trace 验证。这个坑让我理解了“评测口径比功能数量重要”。

### L3. 为什么选择这个方向/岗位？

> 我对“让 Agent 可约束、可观测、可回归”这件事感兴趣，而不是只调 API。这个岗位的办公/学习/跨语言/智能硬件场景，正好是我项目里验证过的方向；我也知道自己缺多模态和生产化，愿意补。

### L4. 你没有实习/大厂经验，怎么证明能落地？

> 我用可复现的工程证据证明：76 项测试、8 个场景、44 条行为用例、12 条 outcome 用例、门禁和故障注入；代码、评测报告、复现命令都在。没有真实线上流量，这是事实，我不包装。

### L5. 你和团队怎么协作？

> 这是个人项目，没有真实跨团队交付。我能证明的是：把接口契约、评测口径、复现命令写清楚，让别人能接手；用 AI 工具做代码审查和文档；如果进团队，我会先把评测和 trace 接进现有流程，而不是另起一套。

### L6. 你的优点/缺点？

> 优点是把模糊问题拆成可验证的指标，比如把“Agent 好不好”拆成工具命中、outcome、p95、成本。缺点是有时会先做机制再补评测，顺序反了；这个项目后半段我在纠正，先定通过标准再改代码。

---

## M. 你问面试官的问题

1. 团队现在 Agent 的评测流程是什么？behavior / outcome / 人工各占多少？
2. 模型选型是统一走一家，还是按场景路由？有没有 fallback 和成本预算？
3. 这个岗位前 3 个月最希望我交付什么：场景落地、评测体系，还是 Harness 基础设施？

---

## N. 不要展开的清单（被问就三句话）

- 多模态 / 语音 / 图像 / OCR / 视觉 embedding
- 端侧推理 / 端云协同
- 多 Agent handoff / supervisor / 共享状态 / A2A
- 生产级 MCP 网关（HTTP/SSE/auth/治理）
- 生产服务（API/鉴权/限流/并发/高可用/容器沙箱）
- 真实用户流量 / 业务 KPI / 真实客服数据
- 官方 BFCL / τ² 分数
- CI/CD 平台接入
- 长期记忆系统 / 用户画像 / 语义记忆
- Agentic RAG / rerank / query rewriting / GraphRAG
- 微调 / post-training / Agentic RL

**统一答法**：
> “这块我没做过真实实现。我的理解是【一句话】。如果要做，我会从【最小闭环】开始，先定指标再动手。”
