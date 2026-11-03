# 讲法分块：先骨架，再肌肉

> 用途：11/04 上午的讲述结构。先能完整讲清"一次 run 怎么跑"，再讲"我改了什么、凭什么说它变好了"。
> 时间配比：**框架 40%，优化 60%**。没有骨架，优化实例听起来像调参；没有优化实例，骨架听起来像抄文档。

---

# Part A · 基础框架（四块，必须能脱稿）

## A1 分层与依赖方向

```text
L4 接口   CLI / Streamlit / 评测 runner
L3 场景   router / workspace / research / coding / robot / mcp / structured / general
L2 能力   业务工具 + RAG(BGE + Chroma + BM25) + 文件/命令/任务图
L1 运行时 FrameworkAgent：create_agent + 中间件 + checkpoint + trace
L5 质量   capability / behavior / outcome / gate
```

**一句话**：依赖方向是 `scenarios → agent.contracts ← agent`，框架层不 import 任何业务工具。

**证据**：`tests/test_scenario_separation.py` 用 pytest 断言这条边界。
> 讲法："这条边界不是靠自觉，是用一条测试守住的。架构约束能写进测试，才不会腐化。"

## A2 Scenario 契约

一个 `dataclass Scenario`（27 个字段），把业务差异压成 5 组：

| 组 | 字段 | 作用 |
|---|---|---|
| 身份/模型 | name / description / model / system_prompt / tools | 这个场景是谁 |
| Harness 开关 | enable_todo / enable_summarization / tool_call_limit / token_budget / pii_types / checkpoint* | 用哪些能力 |
| 权限与容错 | high_risk_tools / tool_policy / tool_timeout* / fallback_model | 出事了怎么办 |
| 工作流/输出 | workflow_factory / response_format | 图还是结构化 |
| 扩展 | middleware / planning_policy / runtime / context / cases_path | 场景自定义 |

**一句话**：新增业务 = 新目录 + `build_scenario()` + 注册，运行时一行不改。

**证据**：8 个场景共用同一个 `FrameworkAgent`。

## A3 一次 run 的生命周期（这是"弄清楚框架"的验收标准）

按代码顺序背下来（`core/agent/framework.py`）：

1. `registry` 取场景 → `build_scenario()` 返回 `Scenario`；
2. `FrameworkAgent.__init__` **按固定顺序装配中间件**，再 `create_agent(model, tools, middleware, checkpointer, response_format)`；
3. `invoke(query, thread_id)`：无 thread_id 就生成一次性 ID；
4. `UserPromptSubmit` hook 可以改写 query；
5. `RunBudget`（token 预算）+ `TraceCallbackHandler`（trace_id）挂到 config；
6. `before_agent`：场景中间件（如 `intent_router`）写 `context`；
7. `before_model`：planning policy 可能注入 tool_call 并 `jump_to="tools"`；token 预算超限直接结束；消息超 30 条触发摘要；
8. 模型返回 tool_calls → 权限（deny 直接回 error ToolMessage）→ HITL（interrupt，等人）→ 超时 → ToolError/ToolRetry → 调用上限 → 真正执行；
9. 工具结果作为 observation 回到循环，直到没有 tool_calls，或撞到步数/调用数/预算上限；
10. `Stop` hook → trace 写 `run_end` → 评测读 trace，不读模型的话。

**HITL 恢复**：中断后用 `resume(thread_id, decisions)` 发 `Command(resume=...)`，checkpoint 恢复状态，审批时间不计入工具超时（超时中间件在 HITL 内层）。

> 自测：能不能不看代码，60 秒把 1→10 讲完，并在第 8 步说清"为什么权限在最外层"。

## A4 评测三层（框架的最后一块）

| 层 | 怎么跑 | 看什么 | 证明什么 |
|---|---|---|---|
| capability | `invoke_tool` 直接调工具 | Hit@4 / MRR / 要点覆盖 | 检索和工具本身行不行 |
| behavior | `invoke` 跑完整 Agent | 工具选择、传参、多步、关键词 | Agent 行为对不对 |
| outcome | 跑完看环境 | 文件内容 / SQLite 行 / 任务图状态 / 路由 trace | **任务真的完成了没有** |

配套：`pass^k`（3 trial 全过才算过）、5 类故障注入、`gate` 阈值门禁、JSONL trace（token/耗时/成本）。

## A5 扩展点地图（被问"怎么加一个需求"时用）

| 需求 | 改哪里 | 不用改 |
|---|---|---|
| 新业务场景 | `core/scenarios/<name>/` + registry | 运行时 |
| 新工具 | 场景 `tools.py` | 框架 |
| 新约束（如审计） | 写一个中间件，加进 `Scenario.middleware` | 业务工具 |
| 新评测维度 | `core/quality/` 新 grader | 场景 |

---

# Part B · 优化实例（统一五段式）

**每个实例都按这个模板讲**：现象 → 归因 → 改动 → 证据 → 代价/边界。

> 关键信号：**归因先于改动**。先说"我判断是哪一层坏了"，再说"所以我只改这一层"。

## B1 BFCL：三条 wrong_args 全是 `^`（首推，10 分钟版必讲）

- **现象**：`simple_python_13/15/16` 三条，3/3 trial 全错，报 `wrong_args`。
- **归因**：不是 schema 问题，是模型把 `x**3` 写成 `x^3`——工具签名没错，是**模型不知道参数要用 Python 表达式**。
- **改动**：工具描述/提示里写明"乘方用 `**`"，不动校验器。
- **证据**：BFCL 60 条 3-trial，55/60 → **59/60**；加重复调用抑制后 60/60，**两轮独立复跑都是 60/60**；RAG 44/45 完全不变（0 回归）。
- **代价/边界**：只修了参数语义，没修 schema；抽样 60 条、简化评分，不是官方榜单。
- **加分自证（一定要主动说）**：我做了隔离实验——只加参数校验是 **56/60，还回归 4 条**，说明校验器解决不了这个问题；而重复调用抑制的独立贡献我**没有证明**（377/236 两条更像模型方差），所以我不把它算成收益。

> 这一段同时展示了：会看 badcase、会隔离变量、敢说"这条我没证据"。

## B2 RAG：hybrid 检索（Q&A 弹药）

- **现象**：45 条 MultiHop 抽样里 `retrieval_miss` 5 条，集中在 comparison 类问题。
- **归因**：纯向量对专有名词/数字不敏感（Vikings、年份、队名），需要词面匹配兜底。
- **改动**：向量 + 手写 BM25（jieba 分词）+ 加权 RRF，k=8。
- **证据**：RAG 40/45 → **44/45**，修复 7 条、0 回归；BFCL 顺带 51→55。
- **代价/边界**：`comparison_query-4` 仍失败（召回了相关文章但没命中指定 evidence，需要 rerank）；**我还同时把 k 从 4 提到 8，所以严格说不是纯 hybrid 的功劳**——这句话主动讲，比被问出来强。
- **反向证据**：换成英文 embedding 反而 -1/-1 并回归 2 条，说明瓶颈不只在语言，BM25 的词面匹配贡献更大。

## B3 Planning policy（Q&A 弹药，最能体现"Harness 决策"）

- **现象**：12 条路由里，模型自主路由 baseline 11/12，漏掉"请记住：我喜欢简洁的回答"（直接答了，没路由）。
- **归因**：路由是确定性决策，交给模型就引入了不确定性。
- **改动**：`before_model` 按规则分类，唯一命中就注入 `route_to_*` 并 `jump_to="tools"`；不命中/平局 **abstain**。
- **证据**：12/12；平均模型调用 1.92 → 1.08；trigger 实验 eligible 3/10 → **3/3**，其余 7 条不该委派的不委派。
- **代价/边界**：规则级、12 条小样本；**时延反而变长（9.6s→19.9s），因为 policy 真的把目标场景跑完了**，不能拿时延说更快。

## B4 Outcome 评测（第二个必讲，收尾用）

- **现象**：router 行为层 3/4，outcome 层 4/4；行为层判失败的那条，路由 target 和 trace 都对。
- **归因**：关键词评分在测"回答像不像"，不是"任务成没成"。
- **改动**：运行前快照目录，运行后用 `run_id` 唯一标记检查文件内容 / SQLite 行 / 任务图状态 / 路由 trace。
- **证据**：12 条用例 / 13 个断言，3-trial 12/12。
- **代价/边界**：断言是我手写的，覆盖的是"可检查的副作用"，不是开放域质量。
- **金句**：**Transcript 可以撒谎，Outcome 不会。**

## B5 错误重注入（机制类，被问"Agent 和 API 有什么区别"时用）

- 参数非法不抛异常，回一条 `status="error"` 的 ToolMessage，让模型下一轮自己改。
- 证据不是分数，是 **5 类故障注入**（超时/权限/参数/空检索/拒答）全过。
- 边界：BFCL 上没证据（只加校验 56/60 且回归 4 条），所以我不用它刷分，只用它证明机制。

## 讲哪几个？

| 时长 | 框架 | 优化 |
|---|---|---|
| 5 min | A1 + A3（60 秒版） | B1 |
| 10 min | A1–A4 | **B1 + B4** |
| 15 min | A1–A5 | B1 + B4 + B2 |
| 30 min 深挖 | 全部 | B1–B5，每个都留一个"我没证明的部分" |

**原则**：优化实例永远讲两个就够——一个证明"我能把指标改好"（B1），一个证明"我会怀疑指标本身"（B4）。B2/B3/B5 是弹药，不是主线。

---

# Part C · 自测：8 个问题答不出就别上场

1. 框架层为什么不 import 业务工具？靠什么保证？
2. 新增一个场景要改哪几个文件？运行时为什么不用动？
3. 一次 `invoke` 从进到出，中间经过哪些阶段？（60 秒，10 步）
4. 中间件为什么是"权限最外、HITL 在超时外、ToolError 在 ToolRetry 外"？
5. capability / behavior / outcome 三层分别读什么？各证明什么？
6. 你做过的优化里，哪一个的收益你**不能**归因？为什么？
7. outcome 断言具体检查了哪四类东西？
8. 如果只让你保留一个中间件，留哪个？

---

# Part D · 一句话总纲

> **基础框架讲"一条 run 怎么被约束和记录"，优化实例讲"我怎么知道改动真的有用"。**
> 前者证明我会搭，后者证明我会判断。
