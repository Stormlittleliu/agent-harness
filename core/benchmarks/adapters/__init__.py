# -*- coding: utf-8 -*-
"""Benchmark 适配器注册表。"""
from core.benchmarks.adapters import (
    bfcl,
    cfbench,
    gaia,
    humaneval,
    mbpp,
    osworld,
    rag,
    swebench,
    tau2,
    webarena,
)

ADAPTERS = [
    tau2.Tau2Adapter(),
    bfcl.BFCLAdapter(),
    rag.RGBAdapter(),
    rag.MultiHopAdapter(),
    cfbench.CFBenchAdapter(),
    gaia.GAIAAdapter(),
    humaneval.HumanEvalAdapter(),
    mbpp.MBPPAdapter(),
    swebench.SWEBenchAdapter(),
    webarena.WebArenaAdapter(),
    osworld.OSWorldAdapter(),
]


def get_adapter(name: str):
    for adapter in ADAPTERS:
        if adapter.name == name:
            return adapter
    raise KeyError(f"未知 benchmark 适配器：{name}")
