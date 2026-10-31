# 优化循环 3 倍样本 / 3 trial 复盘

> 运行：2026-10-31 14:22–16:01，seed=42，DeepSeek `deepseek-chat`
> 样本：BFCL 60（45 simple + 15 irrelevance）、MultiHop 45（comparison / inference / temporal 各 15）
> 每个 case 3 trial；主指标 pass^k（3 次全过），括号内为 mean
> 代码：`core/experiments/optimize.py`；原始报告：`outputs/demo/report.md`

## 1. 结果

| # | 方向 | 改动 | BFCL pass^k (mean) | RAG pass^k (mean) | 修复 | 回归 |
|:---:|:---|:---|:---:|:---:|:---:|:---:|
| 1 | baseline | 中性 prompt；vector k=4 | 51/60 (87%) | 40/45 (90%) | 0 | 0 |
| 2 | A/D. Prompt routing | simple 强制调用；irrelevance 先判断；comparison/inference 多子查询 | 54/60 (91%) | 38/45 (88%) | 4 | 3 |
| 3 | C. Hybrid | 向量 + BM25，k=8 | **55/60 (93%)** | **44/45 (98%)** | **7** | **0** |
| 4 | C. English embedding | bge-small-en-v1.5 + vector k=8 | 54/60 (92%) | 43/45 (97%) | 0 | 2 |
| 5 | B/E. Arg validation | BFCL 必填参数校验，缺参回注 | 55/60 (93%) | 44/45 (98%) | 2 | 0 |

**最佳配置：Iteration 3 hybrid。** BFCL +4 条、RAG +4 条（相对 baseline），0 回归。

## 2. Badcase 与归因

### 2.1 Baseline 主要失败

- BFCL：`extra_call` 3、`wrong_args` 3、`unnecessary_call` 3；
- RAG：`retrieval_miss` 5，集中在 comparison。

### 2.2 Prompt routing：BFCL 有效，RAG 负向

- BFCL 51→54，irrelevance 的过度调用从 3 降到 1，说明“先判断是否需要工具”有效；
- RAG 40→38，comparison 回归 3 条，说明“多子查询”prompt 对检索有副作用；
- 结论：**prompt 不能全局统一**，应按任务类型拆分，并在 RAG 侧回退。

### 2.3 Hybrid：明确收益

- RAG 40→44，mean 89.6%→97.8%，修复 7 条、0 回归；
- 修复了之前反复失败的 `comparison_query-0/3/7`；
- BFCL 也顺带 +1，但主要收益来自检索；
- 结论：**hybrid（向量 + BM25）是当前最值得保留的优化**。

### 2.4 English embedding：没有超过 hybrid

- 54/60、43/45，相对 hybrid -1/-1，回归 2 条（`simple_python_142`、`temporal-1`）；
- 说明 MultiHop 的瓶颈不完全是“中文 BGE 检索英文”，BM25 的词面匹配贡献更大；
- 结论：**回退，不上英文 embedding**，除非后续做 rerank 或多向量。

### 2.5 Arg validation：没有独立证据

- Iteration 5 只改了 BFCL 参数校验，理论上 RAG 不应变化；
- 实际 RAG 43→44，说明这是 **3 trial 下的残余随机性**；
- BFCL `wrong_args` 仍是 3 条，校验中间件没有触发或没有改善；
- 结论：**不能把 +1 归因于校验**；需要 fault-injection case（缺参数、错类型）才能证明。

### 2.6 最终剩余失败：不是随机，是三类具体问题

Iteration 5 的 5 条 BFCL 失败：

| Case | 失败类型 | 真实原因 |
|:---|:---|:---|
| `simple_python_16` / `15` / `13` | wrong_args | 模型把 `2x**2` 写成 `2x^2`、`x**3` 写成 `x^3`，是 **Python 语法提示缺失**，不是 schema 校验能解决的 |
| `simple_python_377` | extra_call | 同一次工具调用重复发了两次（第二次补了 format），需要 **重复调用抑制** |
| `irrelevance_236` | unnecessary_call | 模型连续换 `flight_type` 调了 3 次，属于 **无关任务上的重试循环** |

RAG 只剩 `comparison_query-4`：hybrid 已经召回 Vikings/NFL 相关文章，但没命中指定 evidence，说明还需要 **rerank 或更好的英文检索**。

这三类问题对应下一轮方向：

1. **Tool description / prompt**：明确“函数参数使用 Python 表达式（`**` 而不是 `^`）”；
2. **Loop control**：相同/近相同 tool call 去重，限制同一工具连续重试；
3. **Retrieval**：rerank / 英文 embedding + BM25，而不是继续堆 query。

## 3. 方向结论

| 方向 | 结果 | 判断 |
|:---|:---|:---|
| A. Prompt routing | BFCL +3、RAG -2 | 分任务类型使用，不要全局强制 |
| C. Hybrid retrieval | +1 / +6，0 回归 | **保留，当前最佳** |
| C. English embedding | -1 / -1 | 回退 |
| B/E. Arg validation | +1 / +1，但 RAG 变化与改动无关 | 证据不足，需 fault injection |
| D. Query planning | 已包含在 routing 中，未单独增益 | 保留在 comparison 子集 |
| F. Memory / persistence | P2 demo 已验证两轮记忆 | 单轮指标不体现，需多轮场景 |
| G/H | 未验证 | 下一步 |

## 4. 下一步

1. **评测**：每个 case 5 trial，报 pass^k + bootstrap CI；把 iteration 5 的噪声写进口径。
2. **保留 hybrid**，在 hybrid 基础上单独加参数校验，不要和 embedding 变更混在一起。
3. **BFCL 的 3 条 wrong_args** 逐条看：是模型错、schema 歧义，还是可选参数口径；用官方 scorer 复核。
4. **Fault injection**：构造缺必填参数、错类型、工具超时的 case，验证校验/重试中间件。
5. **多轮 / 恢复**：接 τ² adapter，或至少用 SQLite checkpoint 跑两轮任务。
6. **不要继续堆 prompt**：当前证据表明瓶颈在检索和评分口径，不在 prompt 数量。

## 5. 边界

- BFCL 工具是 stub，评分是简化评分，不是官方 AST；
- MultiHop 只评检索召回，不评最终回答；
- 只改 prompt / 检索器 / embedding / 校验，没有改模型；
- 3 trial 仍不足以消除随机性，结论不做统计显著性声明；
- 没有真实业务数据、没有 τ² 官方 reward、没有多轮环境。
