# 统一 Benchmark 样例集

由 `core/benchmarks/catalog.py` 从公开数据集抽样生成，只保存任务元数据，不复制原始语料。

```bash
python -m core.benchmarks.catalog --build --per-source 40 --seed 42
```

输出：

- `catalog.jsonl`：统一 `BenchTask`，320 条；
- `manifest.json`：来源、版本、许可、抽样数量；
- `catalog.md`：人读版本。

## 来源与许可

| 来源 | 许可 |
|:---|:---|
| τ²-bench | MIT |
| BFCL v4 | Apache-2.0 |
| RGB | CC BY-NC-SA 4.0（非商业） |
| MultiHop-RAG | ODC-BY 1.0 |
| GAIA | 见 HuggingFace 数据集卡片 |
| SWE-bench | MIT（见仓库） |
| WebArena | Apache-2.0 |
| OSWorld | Apache-2.0 |

使用时请遵守各数据集许可；RGB 仅限非商业用途。
