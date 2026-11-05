# 当前评测结果总览

> 更新时间：2026-11-02（新增 3-trial 行为 / outcome / planning policy；旧公开基准仍为 2026-10-31 快照）
> 用途：把散落在 `outputs/` 的结果集中到一页，作为面试/复盘口径。
> 原则：所有公开 benchmark 都是抽样 + 简化/替代评分，不冒充官方榜单。
> **本页不是唯一口径**：面试主结果页见 `docs/interview/jd-results-2026-11-04.md`；本页旧数字（3203、11/13、RAG 42）保留为历史快照。
> **2026-11-05 复核**：workspace / planner / outcome 三组结果到 trace 的链路见 [eval-traceability.md](eval-traceability.md)。

## 1. 统一 Benchmark 样例集

```text
8 个来源 × 40 条 = 320 条
```

| 来源 | 本地数据 | 抽样 | 许可 | 执行方式 |
|:---|:---:|:---:|:---|:---|
| τ²-bench retail | 114 | 40 | MIT | 官方 harness |
| BFCL v4 | 640 | 40 | Apache-2.0 | 官方 harness（待装） |
| RGB | 300 | 40 | CC BY-NC-SA 4.0 | 本项目适配 / 检索 |
| MultiHop-RAG | 2556 | 40 | ODC-BY 1.0 | 本项目适配 / 检索 |
| GAIA | 165 | 40 | HF dataset card | 本项目适配 |
| SWE-bench Verified | 500 | 40 | MIT | 官方 Docker 环境 |
| WebArena | 812 | 40 | Apache-2.0 | 官方自托管网站 |
| OSWorld | 418 | 40 | Apache-2.0 | 官方 VM |

Bucket：

```text
capability   250
adversarial   30
multi_turn    40
regression     0   ← 公开集不提供，回归集自建
```

## 2. 最小优化循环（3 倍样本 / 3 trial）

样本：BFCL 60（45 simple + 15 irrelevance）、MultiHop 45（3 类 × 15）；每个 case 3 trial。

| # | 方向 | BFCL pass^k (mean) | RAG pass^k (mean) | 修复 | 回归 |
|:---:|:---|:---:|:---:|:---:|:---:|
| 1 | baseline | 51/60 (86.7%) | 40/45 (89.6%) | 0 | 0 |
| 2 | routed_prompts | 54/60 (91.1%) | 38/45 (88.1%) | 4 | 3 |
| 3 | **hybrid** | **55/60 (92.8%)** | **44/45 (97.8%)** | **7** | **0** |
| 4 | english_embedding | 54/60 (92.2%) | 43/45 (97.0%) | 0 | 2 |
| 5 | arg_validation | 55/60 (92.8%) | 44/45 (97.8%) | 2 | 0 |

**结论**：

- 最佳配置是 hybrid（向量 + BM25）：相对 baseline BFCL +4、RAG +4，0 回归；
- prompt routing 是 trade-off：BFCL +3，RAG -2；
- 英文 embedding 没有超过 hybrid：-1/-1；
- arg validation 没有独立证据：第 5 轮只改 BFCL 校验，RAG 却 +1，属于噪声。

**剩余失败**：

| Case | 原因 |
|:---|:---|
| BFCL `simple_python_16/15/13` | 模型把 `2x**2` 写成 `2x^2`，缺 Python 语法提示 |
| BFCL `simple_python_377` | 同一次工具调用重复发送两次 |
| BFCL `irrelevance_236` | 无关任务上连续换参数调用 3 次 |
| RAG `comparison_query-4` | hybrid 已召回相关文章，但未命中指定 evidence，需要 rerank |

### BFCL 针对性修复（后续实验）

| 配置 | BFCL pass^k | mean | 结论 |
|:---|:---:|:---:|:---|
| hybrid | 55/60 | 92.8% | 基线 |
| python_syntax | 59/60 | 98.3% | 语法提示稳定修复 13/15/16 |
| **bfcl_fixes** | **60/60** | **100%** | 语法 + 重复调用抑制；两轮 3-trial 复跑均 60/60 |
| hybrid_validation | 56/60 | 93.3% | 单独参数校验无效 |

注意：60 条抽样 + 简化评分，不等于 BFCL 官方 100%；`377/236` 的修复仍可能含方差，抑制中间件的独立贡献未单独证明。

RAG 确认（45 条 × 3 trial）：hybrid 与 bfcl_fixes 都是 **44/45**，唯一失败仍是 `comparison_query-4`，0 回归。

**最终组合**：

```text
bfcl_fixes:
  BFCL 60/60（两轮独立 3-trial 复跑）
  RAG  44/45（与 hybrid 完全一致）
```

## 3. 公开 Benchmark（历史结果）

> 这些数字与上面的 demo 不是同一套链路，注意口径。

### BFCL v4 抽样

```text
simple 100 + irrelevance 100
函数选择 100/100
参数 exact 90/100
无关工具不调用 79/100
错误 0
```

简化评分，不是官方 AST/可执行评分。

### τ²-bench retail 抽样

```text
20 条，1 trial
Pass^1 19/20
DB 20/20
Read 102/110
Write 23/23
Generic 2/3
NL 5/6
```

DeepSeek 替代官方 NL judge，非官方分数；τ² 使用其官方 harness，不是我们的 `FrameworkAgent`。

### RGB 抽样

```text
20 条，16 条可回答样本参与检索评分
Hit@4 16/16，MRR 0.875
```

拒答类不计入检索分；只评检索，不评生成。

### MultiHop-RAG 全量

```text
2556 条问题，2255 条参与评分，301 条 null 跳过
Hits@4 0.5707（95% CI 0.5502–0.5910）
Hits@10 0.6980
MAP@10 0.2243
MRR@10 0.4539
```

语料 609 篇全量；使用中文 BGE 检索英文语料，是弱配置下的结果。
旧的 12 条抽样 5/9（CI 26.7%–81.1%）已被全量结果取代。

### RAG 42 条业务集（历史，需注意）

```text
42 = 20 原始 + 22 hard
judge 37/42
拒答 10/10
grounded 30/32
检索 Hit@K/MRR 1.0（语料小，已饱和）
```

**重要**：这组数据是服装尺码域（`KnowledgeBase-RAG-LLM-System`），当前 `data/knowledge` 是扫地机器人；两者不匹配，`outputs/rag` 是合并前的历史报告，不能当成“扫地机器人 RAG 42 条”。

### Agent 13 条行为用例

```text
11/13（历史 benchmark run）
工具命中 13/13
```

回归集，不是 benchmark；当时 1 trial、无 outcome 断言，后续已用 60 条 demo 集补 trial。

## 4. MCP 演示（Memory + Fetch）

- **Memory**：官方 Node server（`@modelcontextprotocol/server-memory`），跨会话保存/检索用户偏好，JSONL 落盘；
- **Fetch**：本地 `core.mcp.fetch_server`，域名 allowlist、默认禁止私网、200KB/8000 字符截断、输出标记 `untrusted`；
- MCP async 工具通过常驻事件循环包装成同步 LangChain 工具。

自建用例 3 条：

```text
mcp-memory-001  写入偏好   pass
mcp-memory-002  召回偏好   pass
mcp-fetch-001   读取 example.com  pass
```

```text
python -m core.quality.runner agent --scenario mcp_demo
3/3 pass
```

边界：stdio only，无 HTTP/SSE/认证/多 server 治理；Fetch 不做 JS 渲染，也没有完整的 prompt-injection 分类器。

### 4.1 Coding Runtime Demo

`coding_demo` 场景补了 Harness 缺失的运行时能力：

```text
read_file / write_file / edit_file / glob / grep / run_command
create_task / list_tasks / get_task / claim_task / complete_task / fail_task
hooks: UserPromptSubmit / PreToolUse / PostToolUse / Stop / Task*
SQLite 任务图 + blocked_by 依赖 + TaskRunner
运行窗口：任务看板 + 命令日志 + 执行 ready 任务
```

用例：

```text
coding-read-001      读 README.md            pass
coding-run-001       echo hello              pass
coding-task-001      创建任务                 pass
coding-task-002      列出任务                 pass
coding-subagent-001  子 Agent 检查文件         pass
coding-grep-001      搜索 hello               pass
coding-write-001     写并验证 99 乘法表        pass
7/7 pass
```

Subagent：父 Agent 通过 `subagent` 工具派生单层子 Agent，子 Agent 使用 fresh context 和
`read_file / glob / grep / run_command` 白名单，只返回摘要。

任务图单元测试也通过：依赖阻塞、完成后解锁、TaskRunner 认领/完成、危险命令拒绝、hooks 拦截。

### 4.2 P0 追加能力（成本 / 结构化 / 门禁 / 触发率）

详见 [p0-results.md](./p0-results.md)。

```text
成本 / 时延（历史快照）：3203 条 run，成功率 98.3%，p50 2.50s，p95 8.54s，
            20.62M token，按示例单价估算 ¥47.64（约 ¥0.015/run）
结构化输出：5/5，schema 合法 5/5，平均 3.0 条证据
评测门禁：BFCL 90/79、MultiHop 55.56%、coding 100%、structured 100% → PASS
故障注入：超时 / 权限 / 参数错误 / 空检索 / 拒答，5 条确定性测试
触发率：自然任务 0/10 使用 subagent 或任务工具；显式路由后仍 0/10
```

**结论**：结构化输出、成本时延、门禁已经补上；多 Agent / 任务规划仍是
“机制可用、行为不可靠”，下一步应做 planner/routing，而不是继续堆工具。

### 4.3 新场景 3-trial 行为评测（2026-11-02）

| 场景 | 用例 | trials | pass^k | mean | 失败说明 |
|:---|:---:|:---:|:---:|:---:|:---|
| workspace_assistant | 5 | 3 | 5/5 | 1.00 | 无 |
| research_assistant | 3 | 3 | 2/3 | 0.78 | `research-compare-001`：模型有时直接 `read_source`，未走 subagent / search_sources |
| router | 4 | 3 | 3/4 | 0.92 | `router-research-001`：路由目标正确，但最终回答未覆盖期望词 |
| coding_demo | 7 | 1 | 7/7 | 1.00 | 无（本轮 1 trial） |

说明：

- 这是 3-trial 行为回归，不是 5–10 trial 统计结论；失败保留，不掩盖。
- `research-report-001` 三次都使用 3 个 subagent 并行并写报告；`research-compare-001`
  三次中有一次走 subagent/search_sources，两次直接读资料，说明“是否会委派”仍是行为层缺口。
- `router` 行为层 3/4 是最终回答措辞问题；outcome 层路由目标 4/4（见 4.4），这是
  transcript vs outcome 的典型对照。
- `coding_demo` 现在有 `read_file / write_file / edit_file / glob / grep / run_command`
  + Todo + 任务图 + subagent，共 7 条行为用例。
- `workspace_assistant` 有 4 条 LangGraph 工作流，`research_assistant` 有 1 条
  `deep_research` 工作流，`router` 是对话式场景级路由，不合并目标场景工具。

### 4.4 Outcome 评测（12 条用例 / 13 个断言，2026-11-02）

断言直接检查运行后的环境状态：文件、SQLite、任务图、路由 trace。

| 场景 | 用例 | 断言类型 | 1-trial | 3-trial pass^k |
|:---|:---:|:---|:---:|:---:|
| workspace_assistant | 3 | 文件写入 / SQLite 偏好 / 学习笔记 | 3/3 | 3/3 |
| research_assistant | 3 | 报告文件 / 多源引用 / deep_research 工作流 | 3/3 | 3/3 |
| coding_demo | 2 | 脚本 + 运行日志 / 任务图 completed | 2/2 | 2/2 |
| router | 4 | `target` + `target_trace_id` 存在 | 4/4 | 4/4 |
| **合计** | **12** |  | **12/12** | **12/12** |

复现：

```bash
python -m core.quality.runner outcome --all --trials 3
```

口径：1-trial 只证明断言链路可运行；3-trial pass^k 才是可引用数字。失败会保留具体
check 原因（文件不存在 / 内容不满足 / SQLite 行不存在 / 任务状态不对 / router target 错）。

### 4.5 Planning Policy A/B（2026-11-02）

12 条带标签的路由 prompt，baseline = 模型自主路由，policy = 确定性注入 `route_to_*`，
不命中/平局 abstain。

| 变体 | 正确 | 准确率 | abstain | 平均模型调用 | 平均 token | 平均时延 |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| baseline | 11/12 | 91.7% | — | 1.92 | 2221 | 9.6s |
| policy | 12/12 | 100% | 1/12 | 1.08 | 1567 | 19.9s |

说明：

- baseline 失败的是“请记住：我喜欢简洁的回答…”：模型没有路由，直接回答。
- policy 唯一 abstain 的是英文 “Summarize the product brief…”：规则不唯一命中，交回模型后
  仍正确路由到 workspace。这是 abstain 的设计意图，不是失败。
- 平均时延受目标场景任务长度影响（research 一条 90s+），不能用它证明 policy 更快；
  可证明的是准确率 +1 且 router 自身平均模型调用 1.92 → 1.08。
- 12 条小样本行为实验，不是统计显著结论。

触发率实验：

| 变体 | subagent 触发 | task 触发 | eligible | eligible 触发 |
|:---|:---:|:---:|:---:|:---:|
| natural | 0/10 | 0/10 | — | — |
| routed | 0/10 | 0/10 | — | — |
| policy | 3/10 | 0/10 | 3/10 | 3/3 |

口径：不是 10/10 全委派，而是 3/10 该委派的委派、7/10 不该委派的不委派。

## 5. 前端控制台

入口：

```bash
python -m streamlit run app_agent.py
```

视图（侧边栏单视图渲染；总览为工作台入口）：

```text
架构 / 任务执行 / 测试用例 / 公开基准 / 优化循环 / Benchmark 目录 / 成本时延 / 评测记录
```

测试用例详情提供“对象链路”：案例 → 场景 / 工具 / 中间件 / 评测函数 / trace，均带 `module:line`；工具卡可跳转架构页，架构页可反查相关用例。

- 成本时延：成功率、p50/p95、token、估算成本、按模型/工具/最近 run 展示；
- 优化循环：5 轮趋势、pass^k/mean、A/B 对比、失败类型、trace 时间线、搜索/下载；
- Benchmark 目录：8 个来源、320 条样例、按来源/类别/bucket/任务类型/关键词筛选；
- 评测记录（新增）：浏览 `outputs/` 下的历史报告，查看 summary、逐条结果、下载。

## 6. P0 / P1 / P2 状态

- **P0**：3 倍样本、3 trial、pass^k + mean、BFCL 可选参数放宽、trace_id ✅
- **P1**：任务类型路由 prompt、hybrid BM25、英文 BGE ✅
- **P2**：SQLite checkpoint 两轮记忆、trace 时间线 ✅
- **MCP**：Memory + Fetch（stdio）✅
- **Runtime**：hooks / SQLite 任务图 / read_file / run_command / 运行窗口 ✅
- **P0 追加**：成本/时延报告 ✅、结构化输出 5/5 ✅、评测门禁 + 故障注入 ✅、触发率实验 ✅
- **2026-11-02 新增**：新场景 3-trial 行为回归 ✅、12 条 outcome 用例 / 13 个断言 ✅、确定性 planning policy（12/12）✅
- **待做**：后台任务 / 定时调度、rerank、τ² adapter、5–10 trial + CI、MCP HTTP/SSE/auth

## 7. 文件位置

```text
data/benchmarks/                          # 320 条统一样例 + manifest
core/benchmarks/                          # 8 个适配器
core/experiments/                         # 优化循环
core/mcp/                                 # MCP client + Fetch server
core/scenarios/mcp_demo/                  # Memory + Fetch 演示场景
core/interfaces/dashboard/                # 前端视图
outputs/demo/report.md                    # 5 轮报告
docs/benchmarks/optimization-loop-3x.md   # 3x/3-trial 复盘
docs/benchmarks/p0-results.md             # 成本 / 结构化 / 门禁 / 触发率
docs/benchmarks/current-results.md        # 本文件
```

## 8. 诚实边界

- 公开 benchmark 都是抽样、简化评分或替代 judge，不是官方榜单；
- BFCL 工具是 stub，MultiHop 只评检索召回；
- τ² 使用官方 harness，测的是模型在 τ² 里的能力，不是我们的 Harness；
- 没有生产流量、业务 KPI、真实客服数据；
- 3 trial 仍不足以消除随机性，不做统计显著性声明；
- RAG 42 条是服装域历史结果，和当前扫地机器人知识库不匹配；
- 成本是按 `config/observability.yml` 示例单价估算，不是 DeepSeek 账单；
- 触发率是 10 条小样本行为实验，不是统计显著结论。
