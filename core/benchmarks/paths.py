# -*- coding: utf-8 -*-
"""公开 benchmark 的本地源路径与样例输出路径。

默认不再写死作者机器盘符：用 ``AH_BENCHMARK_ROOT`` 指向本地 benchmark 仓库；
未设置时是仓库内空目录 ``benchmark_sources``，适配器会报告 unavailable。
"""
from core.paths import BENCHMARK_ROOT, DATASET_ROOT

__all__ = [
    "BENCHMARK_ROOT",
    "BFCL_ROOT",
    "CFBENCH_ROOT",
    "GAIA_ROOT",
    "HUMANEVAL_ROOT",
    "MBPP_ROOT",
    "MULTIHOP_ROOT",
    "OSWORLD_ROOT",
    "RGB_ROOT",
    "SWEBENCH_ROOT",
    "TAU2_ROOT",
    "WEBARENA_ROOT",
    "CATALOG_OUT",
]

TAU2_ROOT = BENCHMARK_ROOT / "tau2-bench"
BFCL_ROOT = BENCHMARK_ROOT / "BFCL" / "berkeley-function-call-leaderboard"
MULTIHOP_ROOT = BENCHMARK_ROOT / "MultiHop-RAG"
RGB_ROOT = BENCHMARK_ROOT / "RGB"
CFBENCH_ROOT = BENCHMARK_ROOT / "CFBench"
HUMANEVAL_ROOT = BENCHMARK_ROOT / "human-eval"
MBPP_ROOT = BENCHMARK_ROOT / "mbpp"
GAIA_ROOT = BENCHMARK_ROOT / "GAIA"
SWEBENCH_ROOT = BENCHMARK_ROOT / "SWE-bench"
WEBARENA_ROOT = BENCHMARK_ROOT / "WebArena"
OSWORLD_ROOT = BENCHMARK_ROOT / "OSWorld"

# 样例集是派生产物，放外置数据根；旧 data/benchmarks 由 UI 回退读取。
CATALOG_OUT = DATASET_ROOT / "benchmarks"
