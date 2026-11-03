# JD 对齐结果页（2026-11-04 面试）

> 生成：2026-11-02
> 模型：DeepSeek `deepseek-chat` + 本地 BGE `bge-small-zh-v1.5`
> 原则：所有公开 benchmark 都是抽样/简化评分，不是官方榜单；新场景是 3-trial 小样本，不做统计显著声明。
> 本页是面试唯一数字来源；旧文档里的 3203 / 11/13 / RAG 42 条只作历史快照。

---

## 1. 一页结论

```text
项目：多场景工具调用 Agent Harness（办公/学习/内容/跨语言 + 研究 + 编码 + 模拟智能硬件客服）
强项：Harness 中间件、确定性 planning policy、outcome 评测、trace/cost、8 场景工作流
新证据（2026-11-02）：
  - 行为 3-trial：workspace 5/5、research 2/3、router 3/4
  - Outcome 12 条：1-trial 12/12；3-trial pass^k = 12/12
  - Planning policy：router 12/12（baseline 11/12），模型调用 1.92 → 1.08
  - 触发率：natural 0/10、routed 0/10、policy eligible 3/10 → 3/3
边界：多模态/语音/OCR/端侧、多 Agent handoff、生产级 MCP 网关、官方榜单分数都没有。
```

---

## 2. JD 五条责任 → 证据 → 数字 → 边界

| JD 责任 | 项目证据 | 可讲数字 | 诚实边界 |
|---|---|---|---|
| 1. 办公 / 学习 / 内容 / 信息管理 / 跨语言 / 智能硬件 | `workspace_assistant` 9 工具 + 4 工作流；`router` 4 路由；`robot_vacuum` 模拟硬件客服 | workspace 5/5 pass^k；router 3/4 行为、4/4 outcome target | 智能硬件是模拟工具，不是真实设备；跨语言是文本翻译，不是语音 |
| 2. 任务规划、记忆、Tool Calling / MCP、RAG、多模态检索、工作流、多 Agent | 确定性 planning policy；Todo + SQLite 任务图；checkpoint + SQLite 偏好；20+ 工具；Memory/Fetch MCP（stdio）；BGE+Chroma hybrid；7 条 LangGraph 工作流；只读 fan-out | policy 12/12；eligible 3/10 → 3/3；research report 3/3 用 3 个 subagent | 多模态检索没有；多 Agent 只有只读 fan-out，无 handoff；MCP 无 HTTP/SSE/auth |
| 3. Agent 评测、tracing、准确率/稳定性/时延/成本/UX | 44 条行为用例 + 12 条 outcome 用例（13 个断言）+ 3-trial pass^k + gate + 5 类故障注入；JSONL trace + 成本/时延 + 7 视图 dashboard（总览 + 6 功能页） | outcome 1-trial 12/12；3-trial 12/12；3203 runs / 98.3% / p50 2.50s / p95 8.54s / ¥0.0149/run（示例价） | 小样本、单机、无生产流量；gate 是读报告断言，不是 CI |
| 4. 语音/文档/图像多模态、云端边、隐私安全 | 文档解析 txt/pdf/docx/md；PII、权限、HITL、超时、hooks 拒绝危险命令、Fetch 域名白名单 | 5 类故障注入全部通过；HITL reject 不执行 | 语音/图像/OCR/端侧/云边都没有；不是安全沙箱 |
| 5. 使用 AI 工具、跨团队交付 | 个人项目，AI 辅助开发；完整复现命令 + 评测闭环 | 76 项确定性测试通过 | 没有真实跨团队交付，不能编 |

---

## 3. Planning Policy（2026-11-02 新增）

**机制**：`core/agent/middleware/planning.py` 在第一次模型调用前做关键词/优先级分类。
命中唯一规则时注入一条带 `tool_calls` 的 `AIMessage` 并 `jump_to="tools"`；无命中、分数不足
或平局 abstain，交回模型。它不是自主 planner，而是可测、可审计的 Harness 策略。

**Router A/B（12 条带标签 prompt）**

| 变体 | 正确 | 准确率 | abstain | 平均模型调用 | 平均 token | 平均时延 |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| baseline | 11/12 | 91.7% | — | 1.92 | 2221 | 9.6s |
| policy | 12/12 | 100% | 1/12 | 1.08 | 1567 | 19.9s |

- baseline 唯一失败：“请记住：我喜欢简洁的回答…”——模型没有路由，直接回答。
- policy 唯一 abstain：英文 “Summarize the product brief…”——规则不唯一命中，交回模型后仍正确路由。
- 时延不能用来证明 policy 更快：policy 真的执行了目标场景任务，research 一条 90s+；可证明的是
  准确率 +1、router 自身平均模型调用 1.92 → 1.08。

**触发率（10 条 coding 任务）**

| 变体 | subagent 触发 | task 触发 | eligible | eligible 触发 |
|:---|:---:|:---:|:---:|:---:|
| natural | 0/10 | 0/10 | — | — |
| routed | 0/10 | 0/10 | — | — |
| policy | 3/10 | 0/10 | 3/10 | 3/3 |

口径：“不是 10/10 全委派，而是 3/10 该委派的委派、7/10 不该委派的不委派。”

---

## 4. Outcome 评测（2026-11-02 新增）

**原则**：断言只看运行后的环境状态，不看最终回答。每条用例用 `run_id` 生成唯一内容标记，
运行前快照目录，运行后检查新增文件 / SQLite 行 / 任务状态 / 路由 trace。

| 场景 | 条数 | 断言 |
|:---|:---:|:---|
| workspace_assistant | 3 | write_note 文件内容；MemoryStore SQLite 偏好；中文学习笔记含办公/学习/跨语言 |
| research_assistant | 3 | write_report 报告文件 + 至少 2 个 source id；多源对比报告；deep_research 工作流报告 |
| coding_demo | 2 | 脚本文件 + run 日志含 `9x9=81`；任务图 subject 走到 completed |
| router | 4 | `route_to_*` 返回的 target 正确 + `target_trace_id` 能在 trace 文件找到 |

**结果**

```text
1-trial：12/12
3-trial pass^k：workspace 3/3、research 3/3、coding 2/2、router 4/4，合计 12/12
```

失败会保留具体 check：文件不存在 / 内容不满足 / SQLite 行不存在 / 任务状态不对 /
router target 错或 trace 缺失。

---

## 5. 新场景 3-trial 行为回归（2026-11-02）

| 场景 | 用例 | trials | pass^k | mean | 失败说明 |
|:---|:---:|:---:|:---:|:---:|:---|
| workspace_assistant | 5 | 3 | 5/5 | 1.00 | 无 |
| research_assistant | 3 | 3 | 2/3 | 0.78 | `research-compare-001` 有时直接 read_source，未走 subagent/search_sources |
| router | 4 | 3 | 3/4 | 0.92 | `router-research-001` 路由目标正确，但最终回答未覆盖期望词 |
| coding_demo | 7 | 1 | 7/7 | 1.00 | 本轮 1 trial |

**最有价值的对照**：router 行为层 3/4（transcript 关键词），outcome 层 4/4（路由 target + trace）。
这正是“Transcript 可以撒谎，Outcome 不会”的实证。

---

## 6. 观测与成本（两个口径）

```text
历史文档快照（2026-10-31）：
  3203 条 run；成功率 98.3%（3104/3203）；p50 2.50s / p95 8.54s；
  20.62M tokens；约 ¥0.0149/run（示例单价：输入 ¥2/M、输出 ¥8/M）

最新本地聚合（2026-11-02，outputs/cost_report.json）：
  3495 条 run；成功率 96.7%；p95 9.10s；23.43M tokens；¥54.62
  注意：包含本次故意失败的负向用例、实验和重跑，不是产品成功率；
        因此简历用 3203/98.3% 的历史快照，面试同时说明最新口径。
```

Dashboard：`python -m streamlit run app_agent.py`，9 个视图（总览 + 架构 / 任务 / 测试 /
公开基准 / 优化循环 / Benchmark 目录 / 成本时延 / 评测记录）。

---

## 7. 公开 benchmark（历史快照，抽样/简化评分）

| 评测 | 规模 | 指标 | 结果 | 口径 |
|:---|:---:|:---|:---|:---|
| BFCL v4 | 200 | 函数选择 / 参数 exact / 无关不调用 | 100/100 · 90/100 · 79/100 | **模型层**（`bind_tools`）+ 简化评分；**Harness 层**另见 BFCL 60/60（`FrameworkAgent`） |
| τ²-bench retail | 20 | Pass^1 / DB | 0.95 · 20/20 | 1 trial；NL judge 用 DeepSeek 替代 |
| RGB | 20 | Hit@4 / MRR | 16/16 · 0.875 | 16 条可回答参与评分 |
| MultiHop-RAG | 2255 | Hits@4 | 57.07%（95% CI 55.02–59.10） | 中文 BGE 检索英文语料，弱配置 |
| 结构化输出 | 5 | schema / pass | 5/5 · 5/5 | 自建 5 条 |
| 旧 RAG 42 条 | 42 | judge / 拒答 | 37/42 · 10/10 | **服装域历史数据，不作为当前结果** |

---

## 8. 明确缺口

- 多模态检索 / 语音 / 图像 / OCR / 视觉 embedding / 端侧推理 / 云边协同：没有真实实现。
- 多 Agent handoff / supervisor / 共享状态 / A2A：只有只读 fan-out 和场景路由。
- 生产级 MCP 网关：只有 stdio client + Memory/Fetch 两个 server，没有 HTTP/SSE/auth/治理。
- 生产服务：单进程、无 API/鉴权/限流/并发/容器沙箱/监控告警。
- 评测：小样本、3 trial、无官方 scorer、无 bootstrap CI、未接 CI 平台。
- 记忆：checkpoint 短期 + 场景级 SQLite KV；没有用户画像、语义记忆、巩固、冲突消解。

---

## 9. 复现命令

```powershell
# 测试
C:\Users\28980\anaconda3\envs\langchain\python.exe -m pytest -q

# 新场景 3-trial 行为
python -m core.quality.runner agent --scenario workspace_assistant --trials 3
python -m core.quality.runner agent --scenario research_assistant --trials 3
python -m core.quality.runner agent --scenario router --trials 3

# Outcome 3-trial
python -m core.quality.runner outcome --all --trials 3

# Planning A/B + 触发率
python -m core.experiments.planner_eval --trials 1
python -m core.experiments.trigger_rate --variants natural,routed,policy

# 门禁 / 成本
python -m core.quality.gate
python -m core.observability.cost_report
```

---

## 10. 不能说的话

- ❌ “BFCL 官方 100%”“τ² 测的是我的 Harness”。
- ❌ “生产级 MCP 网关”“多 Agent 平台”“多模态 Agent”。
- ❌ “真实客服系统 / 线上用户 / 业务 KPI”。
- ❌ “42 条 RAG 是扫地机器人结果”。
- ❌ “44 条用例代表全部场景”。
- ✅ “自建小样本评测”“公开集抽样”“个人项目”“下一步计划”。
