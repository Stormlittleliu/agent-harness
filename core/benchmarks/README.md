# 公开 Benchmark 适配层

把 τ²-bench、BFCL、RGB、MultiHop-RAG、GAIA、SWE-bench、WebArena、OSWorld 的原始任务，
统一成 `BenchTask`，再按来源 / 类别分层抽样，生成项目自己的样例集。

## 目录

```text
core/benchmarks/
├── schema.py          # BenchTask 统一字段
├── sampling.py        # 分层抽样（固定 seed）
├── catalog.py         # 加载 → 抽样 → catalog.jsonl / manifest.json / catalog.md
├── runner.py          # 环境 runner 接口（external / native / data_only）
├── paths.py           # 本地仓库位置，可用 BENCHMARK_ROOT 覆盖
└── adapters/
    ├── tau2.py        # τ²-bench retail
    ├── bfcl.py        # BFCL v4 simple_python + irrelevance
    ├── rag.py         # RGB + MultiHop-RAG
    ├── gaia.py        # GAIA（需本地下载）
    ├── swebench.py    # SWE-bench（需本地数据 + Docker）
    ├── webarena.py    # WebArena（需本地 config + 自托管网站）
    └── osworld.py     # OSWorld（需本地 examples + VM）
```

## 统一字段

每条 `BenchTask` 包含：

```text
id / source / source_version / split
category / task_type / bucket / difficulty
instruction
initial_state / tools / policy
success_criteria / grader
environment {kind, runner, ...}
license / url / metadata
```

关键约定：

- `grader`：`code` / `llm` / `human` / `mixed`；
- `environment.runner`：`external`（官方 harness）、`native`（本项目）、`data_only`；
- `success_criteria` 是归一化后的检查项，不同 benchmark 的字段放在 `metadata`。

## 使用

```bash
# 查看各适配器是否可用
python -m core.benchmarks.catalog --list

# 每个来源抽 12 条，固定 seed
python -m core.benchmarks.catalog --build --per-source 12 --seed 42

# 只构建某个来源
python -m core.benchmarks.catalog --build --source tau2-bench
```

输出：

```text
data/benchmarks/catalog.jsonl
data/benchmarks/manifest.json
data/benchmarks/catalog.md
```

## 适配器状态

| 来源 | 状态 | 环境要求 |
|:---|:---|:---|
| τ²-bench retail | ✅ 本地数据 114 条 | 官方 CLI + DeepSeek；NL judge 需 OpenAI 或替代 |
| BFCL v4 | ✅ 本地数据 640 条 | 官方 `bfcl generate/evaluate`，需安装 `bfcl_eval` |
| RGB / MultiHop | ✅ 本地数据 300 / 2556 条 | 检索可本地跑；生成需 LLM judge |
| GAIA | ✅ 本地数据 165 条 | gated dataset，已用 HF token 下载 validation |
| SWE-bench | ✅ 本地数据 500 条 | 每个 instance 需要 Docker 仓库环境 |
| WebArena | ✅ 本地数据 812 条 | 需自托管 shopping/reddit/gitlab 等网站 |
| OSWorld | ✅ 本地数据 418 条 | 需 VM / Docker 桌面环境 |

## 环境 runner

`runner.py` 提供统一接口：

```python
from core.benchmarks.runner import run_task

result = run_task(task, execute=False)  # 默认只返回命令，不自动执行
```

- `external`：返回官方命令；`execute=True` 时才真正 subprocess；
- `native`：提示需要映射到本项目 Agent/工具；
- `data_only`：只加载数据，环境未安装。

## 许可

- τ²-bench：MIT
- BFCL：Apache-2.0
- RGB：CC BY-NC-SA 4.0（仅限非商业使用）
- MultiHop-RAG：ODC-BY 1.0
- GAIA / SWE-bench / WebArena / OSWorld：以其仓库 / 数据集卡片为准

样例集只保存任务元数据，不复制原始语料；使用时请遵守各数据集许可。
