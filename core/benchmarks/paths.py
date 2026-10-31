# -*- coding: utf-8 -*-
"""公开 benchmark 的本地仓库位置。

默认指向本机的 E:\\CODE\\benchmarks；其他机器用 BENCHMARK_ROOT 覆盖。
"""
import os
from pathlib import Path

BENCHMARK_ROOT = Path(os.environ.get("BENCHMARK_ROOT", r"E:\CODE\benchmarks"))

TAU2_ROOT = BENCHMARK_ROOT / "tau2-bench"
BFCL_ROOT = BENCHMARK_ROOT / "BFCL" / "berkeley-function-call-leaderboard"
MULTIHOP_ROOT = BENCHMARK_ROOT / "MultiHop-RAG"
RGB_ROOT = BENCHMARK_ROOT / "RGB"
GAIA_ROOT = BENCHMARK_ROOT / "GAIA"
SWEBENCH_ROOT = BENCHMARK_ROOT / "SWE-bench"
WEBARENA_ROOT = BENCHMARK_ROOT / "WebArena"
OSWORLD_ROOT = BENCHMARK_ROOT / "OSWorld"

CATALOG_OUT = Path(__file__).resolve().parents[2] / "data" / "benchmarks"
