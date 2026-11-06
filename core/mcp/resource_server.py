# -*- coding: utf-8 -*-
"""本地资源 MCP server：把只读资源目录暴露成 4 个工具。

启动：

    python -m core.mcp.resource_server

工具返回 JSON 字符串；参数错误 / 非法 URI / 资源不存在都返回
``{"ok": false, "error": "..."}``，不把 traceback 抛给调用方。
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from mcp.server.fastmcp import FastMCP

from core.resources.catalog import ResourceCatalog

mcp = FastMCP("resources")


@lru_cache(maxsize=1)
def _catalog() -> ResourceCatalog:
    # 延迟到第一次调用：import server 本身不读场景库 / 块库。
    return ResourceCatalog()


def _dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _error(exc: BaseException, *, code: str = "error") -> str:
    return _dumps(
        {
            "ok": False,
            "code": code,
            "error": f"{type(exc).__name__}: {exc}",
        }
    )


@mcp.tool()
def resource_kinds() -> str:
    """列出四类素材对象（tool / workflow / scenario / block）及数量。"""
    try:
        return _dumps({"ok": True, "kinds": _catalog().kinds()})
    except Exception as exc:  # noqa: BLE001 - MCP 工具返回结构化错误
        return _error(exc)


@mcp.tool()
def resource_list(kind: str = "", query: str = "", limit: int = 200) -> str:
    """列出资源。kind 可留空（全部）；query 只做词法过滤；limit 上限 200。"""
    try:
        catalog = _catalog()
        items = catalog.list(kind=kind or None, query=query or None, limit=limit)
        return _dumps(
            {
                "ok": True,
                "kind": kind or None,
                "query": query or None,
                "count": len(items),
                "items": items,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc, code="list_failed")


@mcp.tool()
def resource_get(uri: str) -> str:
    """按 URI 取一个资源详情。URI 形如 ah://tool/search_notes。"""
    try:
        return _dumps({"ok": True, "resource": _catalog().get(uri)})
    except Exception as exc:  # noqa: BLE001
        code = "not_found" if type(exc).__name__ == "ResourceNotFoundError" else "get_failed"
        return _error(exc, code=code)


@mcp.tool()
def resource_search(query: str, kind: str = "", limit: int = 20) -> str:
    """在 name / label / description / tags 上做中英词法搜索，返回分数与命中原因。"""
    try:
        items = _catalog().search(query=query, kind=kind or None, limit=limit)
        return _dumps(
            {
                "ok": True,
                "query": query,
                "kind": kind or None,
                "count": len(items),
                "items": items,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc, code="search_failed")


if __name__ == "__main__":
    mcp.run(transport="stdio")
