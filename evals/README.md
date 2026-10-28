# RAG / Agent / LLM 评测

评测代码在 `tools/eval/`，本目录只保存数据与报告：

```text
evals/
├── datasets/
│   ├── business/               # 服装客服业务集（42 条）+ 4 份文档
│   │   ├── docs/
│   │   ├── eval_set.jsonl      # 20 条原始
│   │   ├── eval_set_hard.jsonl # 22 条困难/多跳/冲突
│   │   └── eval_set_all.jsonl  # 42 条合并
│   └── public/                 # 公开 benchmark 抽样
│       ├── rag_rgb_sample.jsonl
│       ├── rag_multihop_sample.jsonl
│       └── multihop_corpus.json
├── failures/                   # 失败集（RAG / Agent / BFCL / τ²）
└── reports/                    # 运行产物（gitignore）
```

## 两层评测

| 层 | 调用链 | 测什么 |
|:---|:---|:---|
| 能力层 | `FrameworkAgent.invoke_tool` → `Scenario.get_tool` → `rag_retrieve` / `rag_summarize` | 检索 Hit@K/MRR、RAG 生成、拒答、grounded |
| 行为层 | `ReactAgent` → `FrameworkAgent.invoke` → model + middleware + tools | 工具选择、参数、拒答、多步 |

能力层把 query 原样传给工具，k 由评测控制；RAG 指标不会被模型改写 query / 多次调用污染。

## 运行

```bash
# 行为层：13 条 Agent 用例
python -m tools.eval.runner agent
python -m tools.eval.runner agent --limit 2
python -m tools.eval.runner agent --case agent-rag-001 --judge

# 能力层：RAG 检索 / 生成
python -m tools.eval.runner rag retrieval --limit 5
python -m tools.eval.runner rag generation --mode hybrid --limit 5

# 公开 benchmark
python -m tools.eval.runner public --rgb-limit 2 --skip-multihop
python -m tools.eval.runner bfcl --simple 2 --irrelevance 2

# LLM judge / 失败集
python -m tools.eval.runner judge --input evals/reports/eval_generation.json
python -m tools.eval.runner failures
```

兼容旧入口：

```bash
python test_entry.py rag retrieval
python test_entry.py rag generation
python test_entry.py rag judge
python test_entry.py benchmark public
python test_entry.py bfcl --simple 2 --irrelevance 2
```

## 指标

| 模块 | 指标 |
|:---|:---|
| `rag_eval.py` retrieval | Hit@K、MRR（按 `expected_sources` 匹配） |
| `rag_eval.py` generation | 要点覆盖率、拒答正确、冲突标记 |
| `rag_judge.py` | 语义覆盖、grounded、引用来源校验 |
| `public.py` | RGB / MultiHop 的 Hit@4、MRR |
| `agent_eval.py` | 工具选择、覆盖率、拒答、通过率 |
| `bfcl.py` | 函数选择准确率、参数 exact、无关工具不调用率 |

## 数据来源与许可

- 业务集：按 `KnowledgeBase-RAG-LLM-System` 的服装客服文档构造，自有数据。
- RGB：<https://github.com/chen700564/RGB>，**CC BY-NC-SA 4.0**（仅限非商业使用）。
- MultiHop-RAG：<https://github.com/yixuantt/MultiHop-RAG>，**ODC-BY 1.0**。
- BFCL：<https://github.com/ShishirPatil/gorilla>，**Apache-2.0**；使用 simple_python + irrelevance 抽样，简化评分。

公开 benchmark 为抽样评测，不是官方完整榜单成绩。

## Failure Set

`failures/` 归档最新一轮的失败/部分通过案例：

- `rag_failures.jsonl`：RAG 42 条中 fail/partial；
- `agent_failures.jsonl`：Agent 13 条中未通过；
- `bfcl_failures.jsonl`：BFCL 200 条中参数错误/无关工具误调用；
- `tau2_failures.jsonl`：τ²-bench 外部结果；
- `README.md`：字段、分类、使用方式。

重新生成：`python -m tools.eval.runner failures`。

> BFCL / τ² 保留外部官方 harness 口径；能力层 RAG 指标是工具级指标，不是 Agent 端到端指标。
