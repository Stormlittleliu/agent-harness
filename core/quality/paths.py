# -*- coding: utf-8 -*-
"""质量层的输入/输出路径。

数据在 data/evals/，报告统一写 outputs/。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVALS_DIR = ROOT / "data" / "evals"
DATASETS_DIR = EVALS_DIR / "datasets"
FAILURES_DIR = EVALS_DIR / "failures"

OUTPUTS_DIR = ROOT / "outputs"
AGENT_OUT = OUTPUTS_DIR / "agent"
RAG_OUT = OUTPUTS_DIR / "rag"
PUBLIC_OUT = OUTPUTS_DIR / "public"
BFCL_OUT = OUTPUTS_DIR / "bfcl"
STRUCTURED_OUT = OUTPUTS_DIR / "structured"
TRACE_OUT = OUTPUTS_DIR / "traces"
