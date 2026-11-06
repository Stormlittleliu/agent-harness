# -*- coding: utf-8 -*-
"""数据集采样实现（不属于 ``core`` 评测框架）。

这里放“怎么从上游 benchmark 源抽样本”的可执行代码：

- :mod:`dataset_ops.stratified`：按类别抽平衡样本 + 写出处记录；
- :mod:`dataset_ops.sampling`：按来源 / 类别分层抽样。

``core.quality.stratified`` 与 ``core.benchmarks.sampling`` 只保留薄兼容 shim；
新代码请直接 import 本包。数据本身放在 ``data/datasets``（可用
``AH_DATASET_ROOT`` 指到仓库外），不进 git。
"""
