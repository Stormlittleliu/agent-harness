# Benchmark 执行层：模型层 / Harness 层 / 能力层 / 外部层

> 用途：面试时避免把“模型层分数”说成“Harness 成绩”，也避免把“数据目录”说成“跑过 320 条”。
> 原则：同一 benchmark，不同执行路径，能证明的东西不同。

---

## 1. 一张表

| 执行层 | Benchmark | 代码路径 | 实际跑什么 | 能证明 | 不能证明 |
|---|---|---|---|---|---|
| **模型层** | BFCL 200（simple 100 + irrelevance 100） | `core/quality/bfcl_simplified.py` | `chat_model.bind_tools(tools).invoke(...)` | 模型函数选择、参数、irrelevance | 不是 Harness；没有中间件/循环 |
| **Harness 层** | BFCL 60（45 simple + 15 irrelevance，3 trial） | `core/experiments/bfcl_agent.py` + `optimize.py` | schema → Pydantic → `StructuredTool` → `Scenario` → `FrameworkAgent.invoke` | 工具调用链、中间件、prompt/loop 改动 | 工具是 stub；简化评分；60 条抽样 |
| **Harness 层** | MultiHop 45（3 类 × 15，3 trial） | `core/experiments/rag_agent.py` + `optimize.py` | 609 语料 → Chroma+BM25 → `rag_retrieve` 工具 → `FrameworkAgent.invoke` | 检索工具在 agent loop 里的效果 | 只评检索 Hit/MRR，不评最终回答 |
| **能力层** | RGB 20 / MultiHop 抽样 | `core/quality/public_sample.py` + `rag_harness.py` | `build_eval_agent(retriever)` → `invoke_tool("rag_summarize")` | 检索/生成工具质量 | 绕过模型决策和中间件 |
| **检索层** | MultiHop 全量 2555 | `core/quality/multihop_full.py` | Chroma retriever + 官方 `calculate_metrics` | 检索召回 | 不是 Agent |
| **外部层** | τ²-bench retail 20 | 外部 τ² harness + `run_tau2_deepseek_judge.py` | τ² 自己的 LLMAgent + 官方环境 | 模型在 τ² 环境的能力 | 不是我的 Harness |
| **数据层** | 320 catalog（8×40） | `core/benchmarks/catalog.py` + `runner.py` | 统一样例目录；`NativeRunner` 占位 | 数据可用性/抽样口径 | 大部分未端到端执行 |

---

## 2. 一句话口径

> “BFCL 200 是模型层：我用 `bind_tools` 直接测模型；BFCL 60 是 Harness 层：我把 schema 转成 LangChain 工具，跑 `FrameworkAgent`，所以语法提示、重复调用抑制、参数校验都能归因到我的链路。MultiHop 45 也是 Harness 层；RGB 是能力层；MultiHop 全量是检索层；τ² 是外部 harness；320 catalog 是数据目录。”

---

## 3. 为什么这个区分重要

- **模型层**改的是 prompt/模型调用方式，不能证明中间件、状态、权限、评测；
- **Harness 层**才能证明“改完是变好还是变坏”的工程闭环；
- **能力层**证明工具质量，不证明 Agent 决策；
- **外部层**是模型能力，不是你的 Harness；
- **数据层**是样本目录，不是执行结果。

---

## 4. 面试追问

### Q1. BFCL 200 条 100/100 函数选择，是你的 Harness 吗？
> “不是，那是模型层：`bfcl_simplified.py` 用 `chat_model.bind_tools` 直接测模型。Harness 层是 BFCL 60 条：`bfcl_agent.py` 把 schema 转成 LangChain 工具，跑 `FrameworkAgent`，60/60 是组合配置的小样本结果。”

### Q2. 那 BFCL 60/60 能说明什么？
> “说明在我的工具调用链里，Python 语法提示把 55/60 提到 59/60；加重复调用抑制后组合配置 60/60，两轮 3-trial 复跑。工具是 stub、评分简化，不是官方 AST。”

### Q3. MultiHop 44/45 是 Harness 吗？
> “优化循环里的 45 条是 Harness 层：609 语料做成 `rag_retrieve` 工具，跑 `FrameworkAgent`。全量 2555 条是检索层：直接 Chroma + 官方指标，不走 Agent。”

### Q4. τ² 呢？
> “外部层：τ² 跑它自己的 LLMAgent，不是我的 Harness；我只把 NL judge 换成 DeepSeek。不能说 τ² 测的是我的 Harness。”

### Q5. 320 条都跑过吗？
> “没有。320 是数据目录；`NativeRunner` 还是占位。真正跑过的是 BFCL 200/60、MultiHop 45/2555、RGB 20、τ² 20，且口径各不相同。”

---

## 5. 一句话总结

> **同一 benchmark，模型层、Harness 层、能力层、外部层、数据层要分开说；BFCL 200 是模型，BFCL 60 才是 Harness。**
