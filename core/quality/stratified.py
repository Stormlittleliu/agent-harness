# -*- coding: utf-8 -*-
"""兼容 shim：分层抽样实现已移到 :mod:`dataset_ops.stratified`。

保留这个模块只为了两件事：

- 现有 ``from core.quality.stratified import build_all`` / 测试继续可用；
- ``python -m core.quality.stratified ...`` 仍能转发到真正的 ``main``。

新代码请直接 import ``dataset_ops.stratified``；``core`` 不再承载采样实现。
"""
from __future__ import annotations

from dataset_ops.stratified import *  # noqa: F401,F403  (re-export 原接口)
from dataset_ops.stratified import main as _main

if __name__ == "__main__":
    raise SystemExit(_main())
