# -*- coding: utf-8 -*-
"""MCP 客户端：连接外部 server，把 async 工具包装成同步 LangChain 工具。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from core.mcp.runner import run_async
from core.paths import runtime_path

ROOT = Path(__file__).resolve().parents[2]
MEMORY_FILE = runtime_path("mcp_memory.json")
MAX_TOOL_CHARS = 6000


def memory_connection() -> dict:
    env = dict(os.environ)
    env["MEMORY_FILE_PATH"] = str(MEMORY_FILE)
    if os.name == "nt":
        return {
            "transport": "stdio",
            "command": "cmd",
            "args": ["/c", "npx", "-y", "@modelcontextprotocol/server-memory"],
            "env": env,
        }
    return {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "env": env,
    }


def fetch_connection(allowed_domains: list[str] | None = None, allow_local: bool = False) -> dict:
    env = dict(os.environ)
    env["MCP_FETCH_ALLOWED_DOMAINS"] = ",".join(allowed_domains or ["example.com", "www.example.com"])
    env["MCP_FETCH_ALLOW_LOCAL"] = "1" if allow_local else "0"
    return {
        "transport": "stdio",
        "command": sys.executable,
        "args": ["-m", "core.mcp.fetch_server"],
        "cwd": str(ROOT),
        "env": env,
    }


def resource_connection() -> dict:
    """本地资源目录 server（只读；不启动模型 / 网络）。"""
    return {
        "transport": "stdio",
        "command": sys.executable,
        "args": ["-m", "core.mcp.resource_server"],
        "cwd": str(ROOT),
        "env": dict(os.environ),
    }


def _content_text(result) -> str:
    if isinstance(result, list):
        parts = []
        for item in result:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        text = "\n".join(parts)
    elif isinstance(result, str):
        text = result
    else:
        text = json.dumps(result, ensure_ascii=False)
    return text[:MAX_TOOL_CHARS]


def _to_sync_tool(tool) -> StructuredTool:
    def _run(**kwargs):
        return _content_text(run_async(tool.ainvoke(kwargs)))

    return StructuredTool.from_function(
        func=_run,
        name=tool.name,
        description=tool.description or "",
        args_schema=tool.args_schema,
    )


def load_tools(connections: dict) -> list[StructuredTool]:
    client = MultiServerMCPClient(connections, tool_name_prefix=True)
    tools = run_async(client.get_tools())
    return [_to_sync_tool(tool) for tool in tools]


def _safe_load(connections: dict, label: str) -> list[StructuredTool]:
    try:
        return load_tools(connections)
    except Exception as exc:  # noqa: BLE001 - 缺少某个 server 时仍可用其他工具
        print(f"[mcp] {label} 加载失败：{type(exc).__name__}: {exc}")
        return []


def load_memory_tools() -> list[StructuredTool]:
    return _safe_load({"memory": memory_connection()}, "memory")


def load_fetch_tools(allowed_domains: list[str] | None = None, allow_local: bool = False) -> list[StructuredTool]:
    return _safe_load({"fetch": fetch_connection(allowed_domains, allow_local)}, "fetch")


def load_resource_tools() -> list[StructuredTool]:
    """加载资源目录工具；失败时返回空列表，不影响默认 MCP 工具。"""
    return _safe_load({"resources": resource_connection()}, "resources")


def load_default_tools() -> list[StructuredTool]:
    return load_memory_tools() + load_fetch_tools()
