# -*- coding: utf-8 -*-
"""兼容 shim：分层抽样实现已移到 :mod:`dataset_ops.sampling`。

旧入口 ``core.benchmarks.sampling`` 只 re-export 原接口，方便已有 import 不炸；
``core/benchmarks`` 现在只保留适配器、schema、runner 与数据引用。
"""
from __future__ import annotations

from dataset_ops.sampling import PREFERRED_SPLITS, stratified_sample

__all__ = ["PREFERRED_SPLITS", "stratified_sample"]
