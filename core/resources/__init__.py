# -*- coding: utf-8 -*-
"""统一素材对象目录：tool / workflow / scenario / block。

这一层是**只读**的：给 Agent 编辑（以及控制台）一个语义一致的方式去
"列出 / 搜索 / 取详情"，不负责改 spec、不构建场景、不起模型。

常用入口：

    from core.resources import ResourceCatalog
    catalog = ResourceCatalog()

``ResourceCatalog`` 用惰性 ``__getattr__`` 暴露，避免仅 import 本包就加载
场景库 / 块库。
"""
from __future__ import annotations

from core.resources.contracts import (
    KIND_DESCRIPTIONS,
    KIND_LABELS,
    ResourceDescriptor,
    ResourceKind,
    ResourceNotFoundError,
    ResourceRef,
    ResourceURIError,
    build_uri,
    empty_object_schema,
    normalize_kind,
    parse_uri,
    validate_resource_id,
)

__all__ = [
    "KIND_DESCRIPTIONS",
    "KIND_LABELS",
    "ResourceCatalog",
    "ResourceDescriptor",
    "ResourceKind",
    "ResourceNotFoundError",
    "ResourceRef",
    "ResourceURIError",
    "build_uri",
    "empty_object_schema",
    "normalize_kind",
    "parse_uri",
    "validate_resource_id",
]


def __getattr__(name: str):
    if name == "ResourceCatalog":
        from core.resources.catalog import ResourceCatalog

        return ResourceCatalog
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
