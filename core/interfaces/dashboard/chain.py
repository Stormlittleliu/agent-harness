# -*- coding: utf-8 -*-
"""把 trace 事件画成调用链（对话端"这次怎么答的"和任务页共用）。

一条链是"用户问题 → 模型 / 工具步骤 → 最终回答"；
每个模型/工具节点都会标上它所属的 LangGraph 节点（如"复核 · verify"），
悬停显示该节点的中文说明。
"""
from __future__ import annotations

from core.scenarios.node_docs import describe_node


def dot_escape(text: object) -> str:
    """Graphviz 标签转义：反斜杠、引号、换行。"""
    return str(text).replace("\\", "\\\\").replace('"', "'").replace("\n", "\\n")


def node_tag(scenario: str | None, event: dict) -> tuple[str, str]:
    """返回 ``(展示名, 悬停说明)``：这一步属于哪个工作流节点。"""
    node = event.get("node")
    if not node:
        return "", ""
    try:
        doc = describe_node(scenario, str(node))
    except Exception:  # noqa: BLE001 - 说明是辅助信息
        doc = None
    if doc is None:
        return f"节点 {node}", ""
    return doc.title, doc.desc


def call_chain_dot(
    events: list[dict],
    messages: list,
    interrupted: bool = False,
    scenario: str | None = None,
) -> str:
    """把 trace 事件画成调用链。

    优先用 trace 的时序；没有 trace 时退回 messages 里的 tool_calls。
    工具节点在 `tool_start` 时创建，`tool_end/tool_error` 时补状态和耗时。
    """
    nodes: list[list[str]] = []  # [id, label, kind, tooltip]
    edges: list[tuple[str, str]] = []

    def add(label: str, kind: str, tooltip: str = "") -> int:
        node_id = f"n{len(nodes)}"
        nodes.append([node_id, label, kind, tooltip])
        if len(nodes) > 1:
            edges.append((nodes[-2][0], node_id))
        return len(nodes) - 1

    add("用户问题", "start")
    model_no = 0
    tool_starts: dict[str, list[int]] = {}
    processed = False
    truncated = False

    def can_add() -> bool:
        nonlocal truncated
        if len(nodes) >= 30:
            truncated = True
            return False
        return True

    for event in events:
        name = event.get("event")
        if name == "model_end":
            model_no += 1
            if not can_add():
                break
            tag, tooltip = node_tag(scenario, event)
            label = f"模型 #{model_no}"
            meta = []
            tokens = event.get("total_tokens")
            if tokens:
                meta.append(f"{int(tokens)} tok")
            latency = event.get("latency_ms")
            if latency is not None:
                meta.append(f"{float(latency):.0f} ms")
            if meta:
                label += "\n" + " · ".join(meta)
            if tag:
                label += f"\n{tag}"
            add(label, "model", tooltip)
            processed = True
        elif name == "tool_start":
            if not can_add():
                break
            tool = str(event.get("tool") or "tool")
            tag, tooltip = node_tag(scenario, event)
            label = f"工具: {tool}\n运行中"
            if tag:
                label += f"\n{tag}"
            index = add(label, "tool", tooltip)
            tool_starts.setdefault(tool, []).append(index)
            processed = True
        elif name in {"tool_end", "tool_error"}:
            tool = str(event.get("tool") or "tool")
            status = str(event.get("status") or ("error" if name == "tool_error" else "完成"))
            tag, tooltip = node_tag(scenario, event)
            label = f"工具: {tool}\n{status}"
            latency = event.get("latency_ms")
            if latency is not None:
                label += f" · {float(latency):.0f} ms"
            if tag:
                label += f"\n{tag}"
            kind = "tool_error" if name == "tool_error" or status == "error" else "tool"
            stack = tool_starts.get(tool) or []
            if stack:
                index = stack.pop()
                nodes[index][1] = label
                nodes[index][2] = kind
                nodes[index][3] = tooltip
            elif can_add():
                add(label, kind, tooltip)
            processed = True
        elif name == "model_error":
            if can_add():
                tag, tooltip = node_tag(scenario, event)
                add("模型错误" + (f"\n{tag}" if tag else ""), "error", tooltip)
            processed = True

    if not processed:
        for message in messages:
            calls = getattr(message, "tool_calls", None) or []
            if not calls:
                continue
            if not can_add():
                break
            model_no += 1
            add(f"模型 #{model_no}", "model")
            for call in calls:
                if not can_add():
                    break
                tool = call.get("name") if isinstance(call, dict) else getattr(call, "name", "tool")
                add(f"工具: {tool}", "tool")
        if model_no == 0:
            add("模型 #1", "model")

    if truncated:
        add("…更多步骤", "more")
    if interrupted:
        add("等待人工审批", "hitl")
    else:
        add("最终回答", "end")

    colors = {
        "start": "#E3F2FD",
        "model": "#E8EAF6",
        "tool": "#E8F5E9",
        "tool_error": "#FFEBEE",
        "error": "#FFEBEE",
        "hitl": "#FFF3E0",
        "more": "#F5F5F5",
        "end": "#E8F5E9",
    }
    lines = [
        "digraph G {",
        "rankdir=LR;",
        "graph [nodesep=0.25, ranksep=0.35];",
        'node [shape=box, style="rounded,filled", fontsize=10, fontname="Microsoft YaHei"];',
    ]
    for node_id, label, kind, tooltip in nodes:
        shape = "oval" if kind in {"start", "end"} else "box"
        fill = colors.get(kind, "#F5F5F5")
        extra = f', tooltip="{dot_escape(tooltip)}"' if tooltip else ""
        lines.append(
            f'"{node_id}" [label="{dot_escape(label)}", shape={shape}, fillcolor="{fill}"{extra}];'
        )
    for source, target in edges:
        lines.append(f'"{source}" -> "{target}";')
    lines.append("}")
    return "\n".join(lines)
