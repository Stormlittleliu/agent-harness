# 公开 Benchmark 原始数据（本地挂载点）

仓库**不再写死任何作者机器的盘符**。公开 benchmark 的原始仓库通过环境变量
`AH_BENCHMARK_ROOT` 指向，默认是这里的空目录：

```powershell
$env:AH_BENCHMARK_ROOT = "D:\benchmarks"      # 你的本地 benchmark 仓库
python -m core.benchmarks.catalog --list      # 检查各适配器是否可用
```

未设置或目录为空时，适配器会报告 `available=no` 并打印下载地址；评测入口不会
因为找不到数据而崩，只会提示“未安装数据源”。

## 目录约定

路径映射在 `core/benchmarks/paths.py`（统一从 `core.paths.BENCHMARK_ROOT` 派生）：

```text
<AH_BENCHMARK_ROOT>/
├── tau2-bench/
├── BFCL/berkeley-function-call-leaderboard/
├── MultiHop-RAG/
├── RGB/
├── CFBench/
├── human-eval/
├── mbpp/
├── GAIA/
├── SWE-bench/
├── WebArena/
└── OSWorld/
```

## 从上游获取

| 来源 | 仓库 / 数据集 | 许可 |
|:---|:---|:---|
| τ²-bench | <https://github.com/sierra-research/tau2-bench> | MIT |
| BFCL | <https://github.com/ShishirPatil/gorilla> | Apache-2.0 |
| RGB | <https://github.com/chen700564/RGB> | CC BY-NC-SA 4.0（非商业） |
| MultiHop-RAG | <https://github.com/yixuantt/MultiHop-RAG> | ODC-BY 1.0 |
| CFBench | <https://github.com/PKU-Baichuan-MLSystemLab/CFBench> | 回上游确认 |
| HumanEval | <https://github.com/openai/human-eval> | MIT |
| MBPP | <https://github.com/google-research/google-research/tree/master/mbpp> | Apache-2.0 |
| GAIA | <https://huggingface.co/datasets/gaia-benchmark/GAIA> | 数据集卡片 |
| SWE-bench | <https://github.com/princeton-nlp/SWE-bench> | MIT |
| WebArena | <https://github.com/web-arena-x/webarena> | Apache-2.0 |
| OSWorld | <https://github.com/xlang-ai/OSWorld> | Apache-2.0 |

## 数据流

```text
AH_BENCHMARK_ROOT（上游原始数据，仓库外）
        │  dataset_ops.stratified / core.benchmarks.catalog
        ▼
data/datasets/（抽样正文，git 忽略）
        │  selections.jsonl / manifest.json
        ▼
data/evals/datasets/stratified/（出处记录，进仓库）
```

原始数据与抽样正文都不进 git；仓库只保留引用、provenance 和项目自有数据。
本目录的 `.gitignore` 会忽略除 `README.md` / `.gitignore` 外的全部内容，
所以把数据放在这里也不会污染 `git status`。
