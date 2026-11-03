# Benchmark 驱动的有效优化与机制补全

> 来源：`docs/benchmarks/optimization-loop-3x.md`、`bfcl-fixes.md`、`current-results.md`、`data/evals/failures/`、`core/experiments/`
> 口径：BFCL 60 条抽样 + MultiHop 45 条抽样，3 trial；简化评分/替代 judge，不是官方榜单。

---

## 1. 一句话结论

真正有数字支撑的有效优化是：

1. **BFCL Python 语法提示**：55/60 → 59/60，稳定修复 3 条 `wrong_args`；
2. **BFCL 组合配置（语法提示 + 重复调用抑制）**：60/60，两轮独立 3-trial 复跑；
3. **MultiHop hybrid 检索（向量 + BM25）**：40/45 → 44/45，修复 7 条、0 回归。

同时补全了评测机制：失败集、3-trial pass^k、fixed/regressed、门禁、故障注入。
但 **参数校验单独无效**、**全局 prompt routing 有负作用**、**英文 embedding 没有超过 hybrid**；τ²/RGB 是验证集，不是优化驱动。

---

## 2. BFCL：失败类型 → 改动 → 结果

### 2.1 基线失败

| 失败类型 | 数量 | 典型 case |
|---|---:|---|
| `extra_call` | 3 | 同一次工具调用重复发送 |
| `wrong_args` | 3 | `simple_python_13/15/16`：把 `2x**2` 写成 `2x^2` |
| `unnecessary_call` | 3 | 无关任务上连续换参数调用 |

### 2.2 有效改动

| 改动 | 针对 case | 结果 | 证据 |
|---|---|---|---|
| **Python 语法提示**：乘方写 `**`，不写 `^` | `simple_python_13/15/16` | BFCL 55/60 → **59/60**；mean 92.8% → 98.3%；修复 4、回归 0 | `bfcl-fixes.md` |
| **重复调用抑制**：同一 run 内同一工具只执行一次，重复调用回注错误 | `simple_python_377`、`irrelevance_236` | 组合配置 **60/60**，两轮独立 3-trial 复跑；RAG 44/45 不变 | `bfcl-fixes.md` |
| **irrelevance 先判断是否需要工具** | 无关任务过度调用 | 过度调用 3 → 1 | `optimization-loop-3x.md` |

### 2.3 无效改动（重要）

| 改动 | 结果 | 结论 |
|---|---|---|
| 只加参数校验 | 56/60；相对组合配置回归 4 条 | BFCL 的问题是 Python 语法，不是 schema 缺参；校验解决不了 |
| 全局 prompt routing | BFCL +3，但 RAG -2，comparison 回归 3 条 | prompt 不能全局统一，应按任务类型拆分 |
| 英文 embedding | BFCL -1、RAG -1，回归 2 条 | 瓶颈不完全是中文 BGE；BM25 词面匹配贡献更大 |

### 2.4 诚实边界

- `simple_python_377` / `irrelevance_236` 的修复更像 **模型方差**；重复抑制中间件的独立贡献**未被证明**，只能说组合配置稳定、无回归。
- 60 条抽样 + 简化评分 ≠ BFCL 官方 100%。
- 参数校验机制保留在 Harness 里（缺参/错类型/工具超时用故障注入验证），但**不归因于 BFCL 提升**。

---

## 3. MultiHop-RAG：失败类型 → 改动 → 结果

### 3.1 基线失败

- RAG 40/45（mean 89.6%），5 条 `retrieval_miss`，集中在 comparison。

### 3.2 有效改动：hybrid 检索

| 改动 | 结果 | 证据 |
|---|---|---|
| 向量 + BM25（加权 RRF，k=8） | RAG **44/45**（mean 97.8%）；修复 7、回归 0；修复 `comparison_query-0/3/7` | `optimization-loop-3x.md` |
| 英文 embedding | 43/45，-1，回归 2 | 未采用 |
| 只加参数校验 | 44/45，但与改动无关，是 3-trial 噪声 | 不归因 |

**结论**：hybrid 是当前最值得保留的检索优化；BM25 的词面匹配补上了向量检索的漏召回。

### 3.3 未解决

- `comparison_query-4`：hybrid 已召回相关文章，但没命中指定 evidence，需要 **rerank / 更好的英文检索**；没有实现。

---

## 4. τ² / RGB：验证，不是优化

### τ²-bench retail 20 条

- Pass^1 19/20，DB 20/20；1 条 `nl_assertion_missing`。
- τ² 使用它自己的官方 harness，测的是模型在 τ² 里的能力，**不是我们的 FrameworkAgent**。
- 做的改动只有评测适配：把官方 OpenAI NL judge 换成 DeepSeek（非官方口径）；**没有针对 τ² 改 Agent 机制**。

### RGB 20 条

- Hit@4 16/16，MRR 0.875；作为检索 sanity check，没有失败驱动的代码改动。

---

## 5. 补全了哪些“本应有的机制”

| 机制 | 位置 | 触发原因 | 价值 |
|---|---|---|---|
| 失败集归档 | `core/quality/failures.py`、`data/evals/failures/` | BFCL 31 条、RAG 5 条、Agent 2 条、τ² 1 条失败 | 从单 case 调 prompt 转为失败类型分析 |
| 3-trial pass^k + mean | `core/experiments/optimize.py:_aggregate`；`core/quality/agent_eval.py` | 单次 run 噪声大 | 区分真实改进与方差 |
| fixed / regressed 对比 | `optimize.py` | 改动可能修 A 坏 B | 防止“修一个坏三个” |
| 评测门禁 | `core/quality/gate.py` | 报告分散、口径漂移 | BFCL / MultiHop / coding / structured 阈值断言 |
| 5 类故障注入 | `tests/test_fault_injection.py` | 参数校验缺少独立证据 | 超时/权限/参数/空检索/拒答的确定性测试 |
| 重复调用抑制（实验适配器） | `core/experiments/bfcl_agent.py:suppress_repeat_tool_calls` | `simple_python_377`、`irrelevance_236` | 组合配置 60/60；独立贡献未证明，未生产化 |
| 必填参数校验（实验适配器） | `core/experiments/bfcl_agent.py:validate_required_args` | BFCL 缺参重试 | 机制存在，但没解决 BFCL 的语法问题 |
| Hybrid retriever（生产） | `core/tools/rag/retrievers.py`、`config/rag.yml` | comparison 漏召回 | 40/45 → 44/45，0 回归 |
| 失败类型统计 | `data/evals/failures/summary.json` | 失败分散 | 10 argument mismatch / 21 unnecessary call 等 |

---

## 6. 面试怎么讲（30 秒）

> “我不是靠堆 prompt。BFCL 失败我先归类：3 条是 `^` vs `**` 的语法问题，3 条是重复调用，3 条是无关任务过度调用。语法提示把 BFCL 从 55/60 提到 59/60；加重复调用抑制后组合配置 60/60，两轮 3-trial 复跑。MultiHop 的 5 条 comparison 漏召回，用 vector + BM25 hybrid 从 40/45 提到 44/45，0 回归。参数校验单独加反而 56/60，所以我不会把它算成有效优化。τ² 和 RGB 是验证集，不是优化驱动。”

如果追问“哪个最有效”：

> “最可信的是 hybrid：40/45 → 44/45，修复 7 条、0 回归，而且已经进生产 `get_hybrid_retriever`。BFCL 语法提示也稳定：55/60 → 59/60。60/60 是组合配置的小样本结果，重复抑制的独立贡献我没证明，不会说成官方 100%。”

如果追问“机制补了什么”：

> “失败集、3-trial pass^k、fixed/regressed、gate、5 类故障注入。这些不是模型能力，是让我能判断‘改完是变好还是变坏’的 Harness 机制。”

---

## 7. 一句话总结

> **有效优化：hybrid 检索（最可信）、Python 语法提示（稳定）、重复调用抑制（组合有效、独立贡献未证明）。  
> 机制补全：失败集、3-trial pass^k、fixed/regressed、gate、故障注入。  
> 无效/负向：参数校验单独、全局 prompt routing、英文 embedding。**
