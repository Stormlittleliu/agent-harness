# 讲序：先展示 → 再对标 learn-claude-code → 再讲下一步

> 配套：`docs/interview/boundary-and-demo-2026-11-03.md`
> 对标对象：`E:\CODE\ag_learn\learn-claude-code`（20 章递进式 Claude Code 风格 Harness 课程）
> 原则：不做优劣评判；做能力覆盖图和取舍说明。

---

## 1. 一句话讲法

> “我先用 8 分钟展示现在能跑什么；再用 5 分钟把它和 learn-claude-code 的 20 个 harness 机制做对标；最后用 4 分钟讲我下一步会补什么、不补什么。”

这样开场的好处：面试官知道你不是在背功能，而是在建立“能力地图 + 取舍判断”。

---

## 2. 能力覆盖图（对标核心）

`learn-claude-code` 的 20 章：s01 loop、s02 tool use、s03 permission、s04 hooks、s05 todo、s06 subagent、s07 skill loading、s08 context compact、s09 memory、s10 system prompt、s11 error recovery、s12 task system、s13 background tasks、s14 cron scheduler、s15 agent teams、s16 team protocols、s17 autonomous agents、s18 worktree isolation、s19 MCP plugin、s20 comprehensive。

### 2.1 覆盖状态

| 章节 | 能力 | 本 Harness | 说明 |
|---|---|---|---|
| s01 | agent loop | ✅ 有 | `FrameworkAgent` + `create_agent` ReAct |
| s02 | tool use | ✅ 有 | 8 场景 / 20+ 工具 |
| s03 | permission | 🟡 部分 | `tool_policy` allow/deny + HITL + 路径保护；**无 permission modes / 沙箱** |
| s04 | hooks | ✅ 有 | UserPromptSubmit / PreToolUse / PostToolUse / Stop / Task* |
| s05 | todo write | ✅ 有 | `TodoListMiddleware` |
| s06 | subagent | 🟡 部分 | 单层只读 fan-out；**无通用 Task tool / handoff** |
| s07 | skill loading | ❌ 缺 | 没有 `SKILL.md` / progressive disclosure |
| s08 | context compact | 🟡 部分 | Summarization 30/12 + token 预算；**无四层压缩 / offloading / context editing** |
| s09 | memory | 🟡 部分 | checkpoint + SQLite KV；**无筛选/提取/整理/冲突消解** |
| s10 | system prompt | 🟡 部分 | Scenario 固定 prompt + 报告 prompt 切换；**无分段组装 / 按需拼接 / 版本化** |
| s11 | error recovery | ✅ 有 | ToolRetry / ToolError / ModelRetry / ToolTimeout / ToolCallLimit / TokenBudget |
| s12 | task system | ✅ 有 | SQLite 任务图 + blocked_by + TaskRunner |
| s13 | background tasks | ❌ 缺 | 工具同步执行，长任务阻塞 |
| s14 | cron scheduler | ❌ 缺 | 无定时触发 |
| s15 | agent teams | ❌ 缺 | 只有只读 fan-out，无持久化队友/邮箱 |
| s16 | team protocols | ❌ 缺 | 无请求-回复协议 |
| s17 | autonomous agents | ❌ 缺 | 无看板/自组织认领 |
| s18 | worktree isolation | ❌ 缺 | 无按任务隔离目录 |
| s19 | MCP plugin | 🟡 部分 | stdio Memory + Fetch；**无 HTTP/SSE/auth/治理** |
| s20 | comprehensive | — | 课程综合章，不直接对标 |

**汇总**：✅ 6 章、🟡 6 章、❌ 7 章、— 1 章。

### 2.2 本 Harness 多出来的能力

| 能力 | 位置 | 价值 |
|---|---|---|
| 多场景 Scenario 抽象 | `core/agent/contracts.py` + `core/scenarios/` | 一套运行时覆盖办公/研究/编码/客服 |
| 本地文本 RAG | `core/tools/rag/` | BGE + Chroma + BM25 |
| 7 条 LangGraph 工作流 | `core/scenarios/*/graph.py` | 固定流程走图，开放决策走 ReAct |
| 确定性 planning policy | `core/agent/middleware/planning.py` | 路由 12/12；带 abstain |
| Behavior + Outcome 评测 | `core/quality/` | 44 行为 + 12 outcome / 13 断言 |
| 公开 benchmark / gate / 故障注入 | `core/quality/` | BFCL / τ² / RGB / MultiHop + 5 类故障 |
| Trace / 成本 / 7 视图 dashboard | `core/observability/` + `core/interfaces/dashboard/` | 可回放、可下钻、可看成本 |
| 结构化输出 | `structured_demo` | Pydantic schema 5/5 |

---

## 3. 对比怎么说（不踩坑）

### 3.1 先给结论

> “learn-claude-code 是 20 章递进式的 Claude Code 风格 Harness 教学实现，重点在编码 Agent 的机制深度；我的项目是多场景 Harness，重点在场景抽象和评测闭环。相同的是 loop、tools、context、MCP、subagent；不同的是它更偏编码交互，我更多场景和评测。”

### 3.2 讲 4 个关键差异，不要逐章念

1. **Agent loop**
   - 它：从零写 loop，透明、可控。
   - 我：`create_agent` + LangGraph，借状态/中断/checkpoint，把精力放在中间件和评测。
   - 判断：不重写 loop；框架抽象泄漏时再考虑下沉。

2. **Context / skills**
   - 它：s07 skill loading、s08 四层压缩/offloading、s10 prompt 组装。
   - 我：Summarization + token 预算；缺 skills、offloading、context editing。
   - 判断：这是我下一步 P0，因为直接决定上下文成本和多场景复用。

3. **Permission / sandbox**
   - 它：s03 权限模式 + s18 worktree 隔离。
   - 我：allow/deny + HITL + 路径保护；`run_command` 是进程内 shell。
   - 判断：这是安全边界，P1；不冒充沙箱。

4. **Evaluation**
   - 它：教学 repo，评测较轻。
   - 我：44 行为 + 12 outcome / 13 断言 + 3-trial + trace/cost/dashboard。
   - 判断：这是我的差异化；但 44/44 是 1-trial 评分，不是“所有任务都能做”。

### 3.3 不要说的话

- ❌ “我比 learn-claude-code 更完整”——它是 20 章教学，我是应用 Harness，目标不同。
- ❌ “我缺 7 章，所以我不行”——那 7 章里有一部分是刻意不做（agent teams / autonomous agents）或下一阶段（skills / sandbox / background）。
- ❌ “44/44 说明所有问题都能答”——Transformer 这类语料外问题是任务失败，不是成功。

---

## 4. 下一步方向（按 ROI 排）

| 优先级 | 方向 | 对应章节 | 为什么现在做 | 指标 | 预估 |
|:---:|---|---|---|---|---|
| P0 | Skills + progressive disclosure | s07 | 把 SOP 从 prompt 里拿出来，按需加载；多场景复用 | system prompt tokens、重复流程成功率 | 2–3 天 |
| P0 | Context offloading / 四层压缩 | s08 | 工具结果写文件、保留路径；cache 友好前缀；直接降 token/cost | tokens/run、p95、成本、pass^k | 3–5 天 |
| P1 | Permission modes + sandbox | s03 / s18 | 当前 `run_command` 是进程内 shell，不能算安全执行 | unsafe block rate、false deny rate | 1–2 周 |
| P1 | Planner / plan mode | s05 / s10 | 当前 policy 是规则级；复杂任务需要 plan-then-act + 审批 | 复杂任务 pass^k、工具调用数 | 3–5 天 |
| P1 | Background tasks + cron | s13 / s14 | 长工具阻塞；主动任务需要调度 | p95、中断恢复率、定时任务成功率 | 1 周 |
| P1 | MCP governance | s19 | stdio 只适合 demo；生产要 HTTP/SSE/auth/健康检查 | MCP 工具成功率、重连率 | 1 周 |
| P2 | Semantic memory / consolidation | s09 | 当前只有 KV；没有筛选、提取、整理、冲突 | 召回准确率、过期记忆率 | 1–2 周 |
| P2 | Eval CI + 官方 scorer + 5–10 trial | 额外 | 当前 gate 是本地读报告，不是 CI | flaky rate、gate pass rate | 3–5 天 |

**明确不做（除非业务需要）**：
- Multi-agent teams / protocols / autonomous agents（s15–s17）：顺序依赖强，handoff 成本大于收益；只保留只读 fan-out。
- 多模态/语音/OCR/端侧：没有真实数据和指标，不为了关键词硬做。
- 微调/Agentic RL：不是当前岗位的核心，也缺数据规模。

---

## 5. 讲序（20 分钟版）

| 时间 | 讲什么 | 关键句 / 动作 |
|:---:|---|---|
| 0–1 min | 开场 + 边界 | “三段：先展示、再对标、再讲下一步；单机单 Agent、本地语料、无多模态。” |
| 1–3 min | 架构 | 指图：界面 → FrameworkAgent → Scenario → Tools/RAG/Workflow → Trace/Eval；“模型只负责决策，Harness 负责工具、上下文、状态、权限、预算、评测。” |
| 3–7 min | Demo | Router→Workspace（policy 路由、检索、引用）；Research（3 subagent、引用、报告）；Coding/HITL（任务图、拒绝副作用）。 |
| 7–9 min | 评测 | 44 行为 + 12 outcome / 13 断言 + 3-trial outcome 12/12；policy 12/12；workspace 5/5；“绿是评分，不是所有任务；Transformer 是语料外，任务失败。” |
| 9–10 min | 过渡 | “功能展示到这里；接下来把它放到工程谱系里看。” |
| 10–15 min | 对标 learn-claude-code | 先给结论；展示 20 章覆盖图（✅6 / 🟡6 / ❌7）；讲 4 个关键差异（loop、context/skills、permission/sandbox、eval）；“不是谁更好，是目标不同。” |
| 15–19 min | 下一步 | P0 skills + context；P1 permission/sandbox、planner、background/cron、MCP；P2 memory、eval CI；明确不做 teams/multimodal。 |
| 19–20 min | 收尾 | “如果入职，前 90 天：评测接 CI → skills/context → MCP 治理。” + 3 个反问。 |

---

## 6. 讲序（10 分钟压缩版）

| 时间 | 讲什么 |
|:---:|---|
| 0–0.5 min | 开场 + 边界 |
| 0.5–2 min | 架构 + 一个 demo（Router→Workspace） |
| 2–3 min | 一个评测数字：outcome 12/12 + policy 12/12；“绿 ≠ 任务成功” |
| 3–6 min | 20 章覆盖图，讲 4 个差异 |
| 6–9 min | 下一步 P0/P1（skills、context、sandbox、MCP） |
| 9–10 min | 90 天计划 + 反问 |

---

## 7. 明天排练重点

1. **先练 20 分钟版**，用计时器；超时就砍 Coding/HITL 和部分章节。
2. **覆盖图要能背**：✅6 / 🟡6 / ❌7；不要逐章念，只讲 4 个差异。
3. **每个缺口都要有一句“为什么现在不补”**：
   - teams/autonomous：顺序依赖强，handoff 成本 > 收益；
   - multimodal：没有数据/指标，不硬做；
   - sandbox：P1，当前明确说“不是沙箱”。
4. **每个 P0/P1 都要有一个指标**：tokens/run、p95、cost、pass^k、unsafe block rate。
5. **最后练 10 分钟版**，确保任何场合都能压缩。

---

## 8. 一句话总结

> **先证明“能跑、能测、知道边界”，再用 20 章覆盖图证明“知道自己在工程谱系里的位置”，最后用 P0/P1/P2 证明“知道下一步怎么补”。**
