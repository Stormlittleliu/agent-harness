# RAG / Agent / LLM 评测

本目录把原本在 `KnowledgeBase-RAG-LLM-System` 里的评测能力收进了 Agent 仓库，
评测全部复用本项目的 `embed_model`、`chat_model`、RAG Prompt 和检索器，
只使用**内存 Chroma**，不会读写业务知识库 `chroma_db/`。

> **Agent 岗口径**：BFCL 工具调用是主指标；RAG 检索/生成是工具级指标；自建 13/42 条是回归集。
> 公开 Agent 基准方案见 [../docs/benchmarks/public-benchmark-plan.md](../docs/benchmarks/public-benchmark-plan.md)。

## 目录

```text
evals/
├── run_eval.py                 # 统一入口
├── common.py                   # 内存向量库、检索器、RAG 链
├── datasets/
│   ├── business/               # 服装客服业务集（42 条）
│   │   ├── docs/               # 4 份业务文档
│   │   ├── eval_set.jsonl      # 20 条原始
│   │   ├── eval_set_hard.jsonl # 22 条困难/多跳/冲突
│   │   └── eval_set_all.jsonl  # 42 条合并
│   └── public/                 # 公开 benchmark 抽样
│       ├── rag_rgb_sample.jsonl
│       ├── rag_multihop_sample.jsonl
│       └── multihop_corpus.json
├── scripts/
│   ├── eval_retrieval.py       # 检索 Hit@K / MRR
│   ├── eval_generation.py      # 生成、拒答、冲突标记
│   ├── eval_judge.py           # LLM-as-judge
│   ├── eval_public_benchmarks.py
│   └── eval_bfcl.py            # BFCL v4 工具调用（simple + irrelevance）
├── failures/                   # 失败集（RAG / Agent / BFCL）
└── reports/                    # 运行产物
```

## 运行

```bash
# 检索层：纯向量 vs 混合检索
python evals/run_eval.py retrieval

# 生成层
python evals/run_eval.py generation

# LLM 复核
python evals/run_eval.py judge

# 公开 benchmark
python evals/run_eval.py public

# BFCL 工具调用（默认 100 simple + 100 irrelevance）
python evals/run_eval.py bfcl
python evals/run_eval.py bfcl --simple 50 --irrelevance 50

# 从最新报告归档失败集
python evals/scripts/build_failure_set.py

# 快速冒烟
python evals/run_eval.py retrieval --limit 5
python evals/run_eval.py generation --limit 5
python evals/run_eval.py public --rgb-limit 2 --skip-multihop
python evals/run_eval.py bfcl --simple 2 --irrelevance 2
```

也可以从统一入口调用：

```bash
python test_entry.py rag retrieval
python test_entry.py rag generation
python test_entry.py rag judge
python test_entry.py benchmark public
python test_entry.py bfcl --simple 100 --irrelevance 100
```

## 指标

| 脚本 | 指标 |
|:---|:---|
| `eval_retrieval.py` | Hit@K、MRR（按 `expected_sources` 匹配） |
| `eval_generation.py` | 要点覆盖率、拒答正确、冲突标记 |
| `eval_judge.py` | 语义覆盖、grounded、引用来源校验 |
| `eval_public_benchmarks.py` | RGB / MultiHop 的 Hit@4、MRR，并产出 judge 输入 |
| `eval_bfcl.py` | 函数选择准确率、参数 exact、无关工具不调用率 |

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
- `README.md`：字段、分类、使用方式。

重新生成：`python evals/scripts/build_failure_set.py`。
