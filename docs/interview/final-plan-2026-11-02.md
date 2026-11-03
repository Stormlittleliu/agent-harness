# 最终面试计划（11/2 晚 – 11/4 上午）

> 目标：不再加功能；把已经做出来的东西讲清楚。
> 只背 3 个数字：workspace 5/5、policy 12/12、outcome 12/12。
> 只记 3 条边界：本地语料、单 Agent、拒答 ≠ 任务成功。
> **11/3 18:00 冻结**：之后只改讲稿，不改代码/评测。

---

## 0. 今晚（11/2，约 2 小时）

- [ ] **20:00–20:20** 读 [边界与 demo 稿](./boundary-and-demo-2026-11-03.md)  
  产出：能说出 3 条边界 + 7 个边界问答。
- [ ] **20:20–20:40** 读 [讲序与对标稿](./talk-track-compare-2026-11-03.md)  
  产出：能背 20 分钟讲序 + 20 章覆盖图（✅6 / 🟡6 / ❌7）。
- [ ] **20:40–21:20** 读 [功能树 × LangChain/LangGraph](./feature-tree-langchain-langgraph.md)  
  产出：能说出 15 个“功能 → 函数 → 框架特性”映射。
- [ ] **21:20–21:50** 读 [面试包](./interview-pack-2026-11-04.md)  
  产出：选定 30 秒 / 2 分钟版本。
- [ ] **21:50–22:00** 读 [JD 结果页](./jd-results-2026-11-04.md)  
  产出：背数字口径表 + 不能说的话。
- [ ] **22:00** 打开 http://localhost:8502 ，确认控制台可打开、评测页有数据。

**今晚不做**：不改代码、不跑大规模评测、不读新章节。

---

## 1. 明早（11/3，09:00–12:00）

- [ ] **09:00–09:20** 30 秒 / 2 分钟各出声练 3 遍  
  只记：workspace 5/5、policy 12/12、outcome 12/12。
- [ ] **09:20–09:50** 读 [core/agent/framework.py](../../core/agent/framework.py:60)  
  重点：中间件顺序、`create_agent(...)`、`invoke` / `resume`。
- [ ] **09:50–10:00** 读 [core/agent/contracts.py](../../core/agent/contracts.py:13)  
  重点：`Scenario` 的 tools / middleware / checkpoint / planning_policy / response_format。
- [ ] **10:00–10:15** 读 [core/agent/middleware/planning.py](../../core/agent/middleware/planning.py:103)  
  重点：`classify_intent`、`before_model`、`jump_to="tools"`、`__can_jump_to__`。
- [ ] **10:15–10:45** 读 [core/quality/agent_eval.py](../../core/quality/agent_eval.py:76) + [core/quality/outcome_eval.py](../../core/quality/outcome_eval.py:1)  
  重点：行为评分、`aggregate_trials`、文件/SQLite/任务图/路由断言。
- [ ] **10:45–11:05** 读 [core/agent/subagent.py](../../core/agent/subagent.py:48) + [research graph](../../core/scenarios/research_assistant/graph.py:139)  
  重点：子 Agent 白名单/超时/摘要；`StateGraph` 的 plan→fan_out→synthesize→cite→report。
- [ ] **11:05–11:25** 读 [core/observability/tracer.py](../../core/observability/tracer.py:39) + [core/mcp/client.py](../../core/mcp/client.py:79)  
  重点：`BaseCallbackHandler` 事件；`MultiServerMCPClient` + `StructuredTool.from_function`。
- [ ] **11:25–12:00** 读 [learn-claude-code README-zh](file:///E:/CODE/ag_learn/learn-claude-code/README-zh.md) 的 20 章清单，再 skim 4 章：  
  [s03_permission](file:///E:/CODE/ag_learn/learn-claude-code/s03_permission) · [s07_skill_loading](file:///E:/CODE/ag_learn/learn-claude-code/s07_skill_loading) · [s08_context_compact](file:///E:/CODE/ag_learn/learn-claude-code/s08_context_compact) · [s18_worktree_isolation](file:///E:/CODE/ag_learn/learn-claude-code/s18_worktree_isolation)  
  产出：能讲 4 个差异（loop、context/skills、permission/sandbox、eval）。

---

## 2. 明天下午（11/3，13:30–18:00）

- [ ] **13:30–13:50** 跑测试：  
  `C:\Users\28980\anaconda3\envs\langchain\python.exe -m pytest -q`  
  预期：84 passed。
- [ ] **13:50–14:10** 跑 router：  
  `C:\Users\28980\anaconda3\envs\langchain\python.exe -m core.quality.runner agent --scenario router --trials 1`  
  预期：4/4。
- [ ] **14:10–14:30** 跑 outcome：  
  `C:\Users\28980\anaconda3\envs\langchain\python.exe -m core.quality.runner outcome --all --trials 1`  
  预期：12/12。
- [ ] **14:30–14:40** 跑门禁：  
  `C:\Users\28980\anaconda3\envs\langchain\python.exe -m core.quality.gate`  
  预期：GATE: PASS。
- [ ] **14:40–15:30** Demo dry-run 1：总览 → Router/Workspace → Research（语料内）→ Coding/HITL → 评测页  
  目标：单次 ≤10 分钟；超时就砍 Coding/HITL。
- [ ] **15:30–16:00** 15 个追问自测：读 [面试包 Q&A](./interview-pack-2026-11-04.md) 和 [50 题问答稿](./interview-qa-2026-11-04.md)  
  重点：Q1 能联网吗、Q2 Transformer 为什么拒答、Q3 44/44 是不是都能做、Q5 多 Agent。
- [ ] **16:00–16:30** 模拟面试 30 分钟（找人或 AI），按“结论 → 机制 → 数字 → 边界”回答。
- [ ] **16:30–17:00** 修 3 个卡壳点，只改讲稿，不改代码。
- [ ] **17:00–17:30** Demo dry-run 2；计时；准备 3 个反问。
- [ ] **17:30–18:00** 冻结：截图/报告/录屏备份；确认 8502；`git status` 记录当前状态。
- [ ] **18:00 后** 只复习 30 秒稿 + 3 个数字 + 3 个反问；23:00 前睡。

---

## 3. 面试当天（11/4 上午）

- [ ] 提前 30 分钟起床/收拾。
- [ ] 面试前 10 分钟读一遍 30 秒稿，不学新东西。
- [ ] 打开 http://localhost:8502 ，确认 dashboard 可用；准备截图/录屏备份。
- [ ] 带 3 个反问：
  1. 团队现在 Agent 评测流程是什么？behavior / outcome / 人工各占多少？
  2. 模型选型统一走一家，还是按场景路由？有没有 fallback 和成本预算？
  3. 前 3 个月最希望我交付什么：场景落地、评测体系，还是 Harness 基础设施？
- [ ] 遇到不会的：说“这块我没做过真实实现。我的理解是…，如果要做我会从…开始。”

---

## 4. 文档索引（全部链接）

### 面试材料

- [边界与 demo 稿](./boundary-and-demo-2026-11-03.md)
- [讲序与对标稿](./talk-track-compare-2026-11-03.md)
- [功能树 × LangChain/LangGraph](./feature-tree-langchain-langgraph.md)
- [面试包（30s/2min/15min/Q&A/demo）](./interview-pack-2026-11-04.md)
- [50 题问答稿](./interview-qa-2026-11-04.md)
- [JD 结果页（数字口径）](./jd-results-2026-11-04.md)
- [项目架构树](../ARCHITECTURE.md)
- [项目边界](../PROJECT.md)

### 代码

- [core/agent/framework.py](../../core/agent/framework.py:60)
- [core/agent/contracts.py](../../core/agent/contracts.py:13)
- [core/agent/middleware/planning.py](../../core/agent/middleware/planning.py:103)
- [core/quality/agent_eval.py](../../core/quality/agent_eval.py:76)
- [core/quality/outcome_eval.py](../../core/quality/outcome_eval.py:1)
- [core/agent/subagent.py](../../core/agent/subagent.py:48)
- [core/scenarios/research_assistant/graph.py](../../core/scenarios/research_assistant/graph.py:139)
- [core/observability/tracer.py](../../core/observability/tracer.py:39)
- [core/mcp/client.py](../../core/mcp/client.py:79)

### 对标

- [learn-claude-code README-zh](file:///E:/CODE/ag_learn/learn-claude-code/README-zh.md)
- [s03_permission](file:///E:/CODE/ag_learn/learn-claude-code/s03_permission)
- [s07_skill_loading](file:///E:/CODE/ag_learn/learn-claude-code/s07_skill_loading)
- [s08_context_compact](file:///E:/CODE/ag_learn/learn-claude-code/s08_context_compact)
- [s18_worktree_isolation](file:///E:/CODE/ag_learn/learn-claude-code/s18_worktree_isolation)

### AgentGuide（只读 3 篇）

- [project-deep-dive](file:///E:/CODE/ag_learn/AgentGuide/docs/04-interview/23-frontier-interview-guides/project-deep-dive.md)
- [agent-harness-playbook](file:///E:/CODE/ag_learn/AgentGuide/docs/04-interview/18-agent-interview-playbooks/agent-harness-playbook.md)
- [agent-evaluation-playbook](file:///E:/CODE/ag_learn/AgentGuide/docs/04-interview/18-agent-interview-playbooks/agent-evaluation-playbook.md)

---

## 5. 一句话

> **今晚读“怎么说”，明早读“怎么实现”，下午只练“怎么讲”；18:00 冻结，不再加功能。**
