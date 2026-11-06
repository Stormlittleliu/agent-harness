# -*- coding: utf-8 -*-
"""质量层的输入/输出路径。

数据在 ``data/evals``（项目自建）与 ``data/datasets``（外置公开集）；
报告统一写 ``outputs/``。具体根目录见 :mod:`core.paths`。
"""
from core.paths import (
    DATASET_ROOT,
    EVALS_DATASETS_ROOT,
    EVALS_ROOT,
    PROJECT_ROOT,
    dataset_path,
)

ROOT = PROJECT_ROOT
EVALS_DIR = EVALS_ROOT
DATASETS_DIR = EVALS_DATASETS_ROOT
EXTERNAL_DATASETS_DIR = DATASET_ROOT
FAILURES_DIR = EVALS_DIR / "failures"

OUTPUTS_DIR = ROOT / "outputs"
AGENT_OUT = OUTPUTS_DIR / "agent"
RAG_OUT = OUTPUTS_DIR / "rag"
PUBLIC_OUT = OUTPUTS_DIR / "public"
BFCL_OUT = OUTPUTS_DIR / "bfcl"
STRUCTURED_OUT = OUTPUTS_DIR / "structured"
OUTCOME_OUT = OUTPUTS_DIR / "outcome"
TRACE_OUT = OUTPUTS_DIR / "traces"

__all__ = [
    "AGENT_OUT",
    "BFCL_OUT",
    "DATASETS_DIR",
    "EXTERNAL_DATASETS_DIR",
    "FAILURES_DIR",
    "OUTCOME_OUT",
    "OUTPUTS_DIR",
    "PUBLIC_OUT",
    "RAG_OUT",
    "ROOT",
    "STRUCTURED_OUT",
    "TRACE_OUT",
    "dataset_path",
]
