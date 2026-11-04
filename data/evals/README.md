# RAG / Agent / LLM 评测

评测代码在 `core/quality/`，本目录只保存数据；报告统一写到 `outputs/`。

```text
data/evals/
├── datasets/
│   ├── business/               # 服装客服业务集（42 条）+ 4 份文档
│   │   ├── docs/
│   │   ├── eval_set.jsonl      # 20 条原始
│   │   ├── eval_set_hard.jsonl # 22 条困难/多跳/冲突
│   │   └── eval_set_all.jsonl  # 42 条合并
│   ├── public/                 # 公开 benchmark 抽样
│   │   ├── rag_rgb_sample.jsonl
│   │   ├── rag_multihop_sample.jsonl
│   │   └── multihop_corpus.json
│   └── stratified/             # 每类 5 条的平衡抽样（原始样本不随仓库分发）
│       ├── selections.jsonl    # 逐条出处：源文件 / hash / 行号 / id
│       ├── selections.md
│       └── manifest.json
└── failures/                   # 失败集（RAG / Agent / BFCL / τ²）
```

报告目录：

```text
outputs/
├── agent/  rag/  public/  bfcl/
└── traces/
```

## 两层评测

| 层 | 调用链 | 测什么 |
|:---|:---|:---|
| 能力层 | `FrameworkAgent.invoke_tool` → `Scenario.get_tool` → `rag_retrieve` / `rag_summarize` | 检索 Hit@K/MRR、RAG 生成、拒答、grounded |
| 行为层 | `FrameworkAgent.invoke` → model + middleware + tools | 工具选择、参数、拒答、多步 |

能力层把 query 原样传给工具，k 由评测控制；RAG 指标不会被模型改写 query / 多次调用污染。

## 运行

```bash
# 行为层：13 条 Agent 用例
python -m core.quality.runner agent
python -m core.quality.runner agent --limit 2
python -m core.quality.runner agent --case agent-rag-001 --judge

# 能力层：RAG 检索 / 生成
python -m core.quality.runner rag retrieval --limit 5
python -m core.quality.runner rag generation --mode hybrid --limit 5

# 公开 benchmark
python -m core.quality.runner public --rgb-limit 2 --skip-multihop
python -m core.quality.runner bfcl --simple 2 --irrelevance 2

# LLM judge / 失败集
python -m core.quality.runner judge --input outputs/rag/eval_generation.json
python -m core.quality.runner failures
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
- BFCL：<https://github.com/ShishirPatil/gorilla>，**Apache-2.0**；原抽样为 simple_python + irrelevance，简化评分。
- τ²-bench：<https://github.com/sierra-research/tau2-bench>，**MIT**。
- CFBench：<https://github.com/PKU-Baichuan-MLSystemLab/CFBench>，本地未附 LICENSE，商用前回上游确认。
- HumanEval：<https://github.com/openai/human-eval>，**MIT**。
- MBPP：<https://github.com/google-research/google-research/tree/master/mbpp>，**Apache-2.0**。

公开 benchmark 为抽样评测，不是官方完整榜单成绩。

`stratified/` 的原始样本由本地 benchmark 源生成，**不随仓库分发**（RGB 是
CC BY-NC-SA，不能直接复制进 MIT 仓库）。仓库只保留 `selections.jsonl` /
`selections.md` / `manifest.json` 作为出处记录；当前 11 个源、381 条。
每条样本带 `eval_scope`（`model_capability` / `scenario_tool`）和 `execution`
（当前能不能跑），不要把两层混成一张分。重新生成命令：

```powershell
python -m core.quality.stratified --per-category 5 --seed 42
```

## Failure Set

`failures/` 归档最新一轮的失败/部分通过案例：

- `rag_failures.jsonl`：RAG 42 条中 fail/partial；
- `agent_failures.jsonl`：Agent 13 条中未通过；
- `bfcl_failures.jsonl`：BFCL 200 条中参数错误/无关工具误调用；
- `tau2_failures.jsonl`：τ²-bench 外部结果；
- `README.md`：字段、分类、使用方式。

重新生成：`python -m core.quality.runner failures`。

> BFCL / τ² 保留外部官方 harness 口径；能力层 RAG 指标是工具级指标，不是 Agent 端到端指标。
