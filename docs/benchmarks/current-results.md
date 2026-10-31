# 当前评测结果总览

> 更新时间：2026-10-31
> 用途：把散落在 `outputs/` 的结果集中到一页，作为面试/复盘口径。
> 原则：所有公开 benchmark 都是抽样 + 简化/替代评分，不冒充官方榜单。

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
read_file / glob / run_command
create_task / list_tasks / get_task / claim_task / complete_task / fail_task
hooks: UserPromptSubmit / PreToolUse / PostToolUse / Stop / Task*
SQLite 任务图 + blocked_by 依赖 + TaskRunner
运行窗口：任务看板 + 命令日志 + 执行 ready 任务
```

用例：

```text
coding-read-001   读 README.md        pass
coding-run-001    echo hello          pass
coding-task-001   创建任务             pass
coding-task-002   列出任务             pass
4/4 pass
```

任务图单元测试也通过：依赖阻塞、完成后解锁、TaskRunner 认领/完成、危险命令拒绝、hooks 拦截。

## 5. 前端控制台

入口：

```bash
python -m streamlit run app_agent.py
```

页签：

```text
架构 / 任务执行 / 测试用例 / 公开基准 / 优化循环 / Benchmark 目录 / 评测记录
```

- 优化循环：5 轮趋势、pass^k/mean、A/B 对比、失败类型、trace 时间线、搜索/下载；
- Benchmark 目录：8 个来源、320 条样例、按来源/类别/bucket/任务类型/关键词筛选；
- 评测记录（新增）：浏览 `outputs/` 下的历史报告，查看 summary、逐条结果、下载。

## 6. P0 / P1 / P2 状态

- **P0**：3 倍样本、3 trial、pass^k + mean、BFCL 可选参数放宽、trace_id ✅
- **P1**：任务类型路由 prompt、hybrid BM25、英文 BGE ✅
- **P2**：SQLite checkpoint 两轮记忆、trace 时间线 ✅
- **MCP**：Memory + Fetch（stdio）✅
- **Runtime**：hooks / SQLite 任务图 / read_file / run_command / 运行窗口 ✅
- **待做**：后台任务 / 定时调度、rerank、τ² adapter、5 trial + CI、outcome 断言、MCP HTTP/SSE/auth

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
docs/benchmarks/current-results.md        # 本文件
```

## 8. 诚实边界

- 公开 benchmark 都是抽样、简化评分或替代 judge，不是官方榜单；
- BFCL 工具是 stub，MultiHop 只评检索召回；
- τ² 使用官方 harness，测的是模型在 τ² 里的能力，不是我们的 Harness；
- 没有生产流量、业务 KPI、真实客服数据；
- 3 trial 仍不足以消除随机性，不做统计显著性声明；
- RAG 42 条是服装域历史结果，和当前扫地机器人知识库不匹配。
