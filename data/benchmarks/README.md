# 统一 Benchmark 样例集

由 `core/benchmarks/catalog.py` 从公开数据集抽样生成，只保存任务元数据，不复制原始语料。

```powershell
python -m core.benchmarks.catalog --list
python -m core.benchmarks.catalog --build --per-source 40 --seed 42
```

原始 benchmark 数据不在仓库里，用 `AH_BENCHMARK_ROOT` 指向本地源目录
（默认是仓库内空的 `benchmark_sources/`，见
[benchmark_sources/README.md](../../benchmark_sources/README.md)）。

## 输出位置

catalog 正文是派生产物，默认写到外置数据根，**不进 git**：

```text
data/datasets/benchmarks/catalog.jsonl   # 统一 BenchTask
data/datasets/benchmarks/manifest.json   # 来源、版本、许可、抽样数量
data/datasets/benchmarks/catalog.md      # 人读版本
```

本目录只保留 `manifest.json` 作为来源引用（旧快照）和本 README。数据目录约定见
[data/datasets/README.md](../datasets/README.md)；dashboard 会优先读外置 catalog，
读不到时回退到旧 `data/benchmarks/`。

## 来源与许可

| 来源 | 许可 |
|:---|:---|
| τ²-bench | MIT |
| BFCL v4 | Apache-2.0 |
| RGB | CC BY-NC-SA 4.0（非商业） |
| MultiHop-RAG | ODC-BY 1.0 |
| CFBench | 回上游确认 |
| GAIA | 见 HuggingFace 数据集卡片 |
| HumanEval | MIT |
| MBPP | Apache-2.0 |
| SWE-bench | MIT（见仓库） |
| WebArena | Apache-2.0 |
| OSWorld | Apache-2.0 |

使用时请遵守各数据集许可；RGB 仅限非商业用途。
