# -*- coding: utf-8 -*-
"""质量层的输入/输出路径。

数据留在 evals/，报告统一写 outputs/。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALS_DIR = ROOT / "evals"
DATASETS_DIR = EVALS_DIR / "datasets"
FAILURES_DIR = EVALS_DIR / "failures"

OUTPUTS_DIR = ROOT / "outputs"
AGENT_OUT = OUTPUTS_DIR / "agent"
RAG_OUT = OUTPUTS_DIR / "rag"
PUBLIC_OUT = OUTPUTS_DIR / "public"
BFCL_OUT = OUTPUTS_DIR / "bfcl"
TRACE_OUT = OUTPUTS_DIR / "traces"
