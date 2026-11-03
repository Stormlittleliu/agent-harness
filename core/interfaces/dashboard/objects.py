# -*- coding: utf-8 -*-
"""对象索引：把 UI 上的案例 / 运行结果链接到具体实现对象。

对象包括场景构造器、LangChain 工具函数、中间件类、工作流节点、评测函数与
本地 trace。`inspect` 失败时降级为模块名，不阻塞页面。
"""
from __future__ import annotations

import functools
import importlib
import inspect
import textwrap
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable

import streamlit as st

from core.interfaces.dashboard.layout import compact_table, navigate
from core.interfaces.dashboard.traces import render_trace_timeline

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAX_SOURCE_LINES = 120
MAX_SOURCE_CHARS = 8000


@dataclass(frozen=True)
class ObjectRef:
    kind: str
    name: str
    module: str = ""
    qualname: str = ""
    file: str | None = None
    lineno: int | None = None
    end_lineno: int | None = None
    source: str | None = None
    summary: str = ""
    external: bool = False
    note: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def location(self) -> str:
        # 项目内对象显示相对路径 + 行号；第三方对象只显示模块.类名，
        # 避免把 site-packages 的绝对路径铺在页面上。
        if self.file and self.lineno and not self.external:
            return f"{self.file}:{self.lineno}"
        if self.module and self.qualname:
            return f"{self.module}.{self.qualname}"
        if self.file and self.lineno:
            return f"{self.file}:{self.lineno}"
        return self.module or self.name


@dataclass
class ObjectIndex:
    scenario: ObjectRef
    agent: ObjectRef
    tools: dict[str, ObjectRef]
    middleware: list[ObjectRef]
    workflow_nodes: dict[str, list[ObjectRef]]
    eval_refs: dict[str, ObjectRef]

    def find(self, kind: str, name: str) -> ObjectRef | None:
        if kind == "scenario":
            return self.scenario if name in {self.scenario.name, self.scenario.qualname} else None
        if kind == "agent":
            return self.agent if name in {self.agent.name, self.agent.qualname} else None
        if kind == "tool":
            return self.tools.get(name)
        if kind == "middleware":
            return next((ref for ref in self.middleware if ref.name == name), None)
        if kind == "eval":
            return self.eval_refs.get(name)
        if kind == "workflow_node":
            for refs in self.workflow_nodes.values():
                for ref in refs:
                    if ref.name == name or ref.name.endswith(f".{name}"):
                        return ref
        return None


def _relative_file(path: str | Path) -> str:
    try:
        resolved = Path(path).resolve()
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except (OSError, ValueError):
        return str(path)


def _is_external(path: str | Path) -> bool:
    try:
        resolved = Path(path).resolve()
    except OSError:
        return True
    return "site-packages" in resolved.as_posix() or "dist-packages" in resolved.as_posix()


def _unwrap(obj: Any) -> Any:
    """把 StructuredTool / RunnableCallable / partial / bound method 解到源码对象。"""
    seen: set[int] = set()
    for _ in range(10):
        if obj is None or id(obj) in seen:
            return obj
        seen.add(id(obj))
        if inspect.isclass(obj) or inspect.isfunction(obj) or inspect.ismethod(obj) or inspect.ismodule(obj):
            return obj
        if isinstance(obj, functools.partial):
            obj = obj.func
            continue
        moved = False
        for attr in ("func", "bound", "coroutine", "runnable"):
            candidate = getattr(obj, attr, None)
            if candidate is not None and candidate is not obj:
                obj = candidate
                moved = True
                break
        if moved:
            continue
        func = getattr(obj, "__func__", None)
        if func is not None and func is not obj:
            obj = func
            continue
        return obj
    return obj


def _first_doc(obj: Any, limit: int = 180) -> str:
    try:
        doc = inspect.getdoc(obj) or ""
    except Exception:  # noqa: BLE001
        doc = ""
    return doc.split("\n")[0][:limit] if doc else ""


def ref_from_object(
    kind: str,
    name: str,
    obj: Any,
    *,
    summary: str = "",
    meta: dict[str, Any] | None = None,
    max_lines: int = MAX_SOURCE_LINES,
) -> ObjectRef:
    raw = obj
    target = _unwrap(obj)
    module = getattr(target, "__module__", "") or ""
    qualname = getattr(target, "__qualname__", getattr(target, "__name__", "")) or ""
    if not module and target is not None:
        module = type(target).__module__
    if not qualname and target is not None:
        qualname = type(target).__name__

    file: str | None = None
    lineno: int | None = None
    end_lineno: int | None = None
    source: str | None = None
    external = False
    note = ""

    if target is None:
        external = True
        note = "对象未注册或为动态工具"
    else:
        try:
            file_path = inspect.getsourcefile(target) or inspect.getfile(target)
            file = _relative_file(file_path)
            external = _is_external(file_path)
            lines, lineno = inspect.getsourcelines(target)
            end_lineno = lineno + len(lines) - 1
            if not external:
                source = textwrap.dedent("".join(lines))
                if source.count("\n") + 1 > max_lines:
                    source = "\n".join(source.splitlines()[:max_lines])
                    source += f"\n... (仅展示前 {max_lines} 行)"
                source = source[:MAX_SOURCE_CHARS]
        except (TypeError, OSError, IOError, IndentationError) as exc:
            external = True
            note = f"源码不可用：{type(exc).__name__}"

    return ObjectRef(
        kind=kind,
        name=name,
        module=module,
        qualname=qualname,
        file=file,
        lineno=lineno,
        end_lineno=end_lineno,
        source=source,
        summary=summary or _first_doc(target),
        external=external,
        note=note,
        meta={**(meta or {}), "raw_type": type(raw).__name__ if raw is not None else "None"},
    )


def _scenario_ref(scenario) -> ObjectRef:
    name = getattr(scenario, "name", "scenario")
    try:
        module = importlib.import_module(f"core.scenarios.{name}.scenario")
        builder = getattr(module, "build_scenario", None)
        if builder is not None:
            return ref_from_object(
                "scenario",
                name,
                builder,
                summary=getattr(scenario, "description", "") or "",
                meta={"scenario": name},
            )
    except Exception:  # noqa: BLE001
        pass
    return ref_from_object("scenario", name, scenario, summary=getattr(scenario, "description", "") or "")


def _build_workflow_nodes(scenario, graphs: dict | None) -> dict[str, list[ObjectRef]]:
    if graphs is None and getattr(scenario, "workflow_factory", None):
        try:
            graphs = scenario.workflow_factory(scenario)
        except Exception:  # noqa: BLE001 - 工作流构建失败不应影响对象索引
            graphs = {}
    result: dict[str, list[ObjectRef]] = {}
    for graph_name, compiled in (graphs or {}).items():
        refs: list[ObjectRef] = []
        try:
            graph_view = compiled.get_graph() if hasattr(compiled, "get_graph") else compiled
            node_names = list(getattr(graph_view, "nodes", {}) or {})
        except Exception:  # noqa: BLE001
            node_names = []
        builder_nodes = getattr(getattr(compiled, "builder", None), "nodes", {}) or {}
        for node_name in node_names:
            if node_name in {"__start__", "__end__"}:
                continue
            node_obj = builder_nodes.get(node_name)
            runnable = getattr(node_obj, "runnable", None) or node_obj
            func = getattr(runnable, "func", None) or getattr(runnable, "bound", None) or runnable
            if func is None and getattr(scenario, "workflow_factory", None):
                func = scenario.workflow_factory
            refs.append(
                ref_from_object(
                    "workflow_node",
                    f"{graph_name}.{node_name}",
                    func,
                    summary=f"工作流 {graph_name} 的节点 {node_name}",
                    meta={"graph": graph_name, "node": node_name},
                )
            )
        result[str(graph_name)] = refs
    return result


def build_object_index(agent, graphs: dict | None = None) -> ObjectIndex:
    scenario = agent.scenario
    scenario_ref = _scenario_ref(scenario)
    agent_ref = ref_from_object(
        "agent",
        type(agent).__name__,
        type(agent),
        summary=(inspect.getdoc(type(agent)) or "").split("\n")[0][:180],
    )

    tools: dict[str, ObjectRef] = {}
    for tool in getattr(scenario, "tools", []) or []:
        name = getattr(tool, "name", str(tool))
        target = getattr(tool, "func", None) or getattr(tool, "coroutine", None) or tool
        tools[str(name)] = ref_from_object(
            "tool",
            str(name),
            target,
            summary=(getattr(tool, "description", "") or "").split("\n")[0][:180],
            meta={"tool_type": type(tool).__name__},
        )

    middleware: list[ObjectRef] = []
    seen: set[tuple[str, str]] = set()
    for mw in getattr(agent, "middleware", []) or []:
        cls = type(mw)
        key = (cls.__module__, cls.__qualname__)
        if key in seen:
            continue
        seen.add(key)
        middleware.append(
            ref_from_object(
                "middleware",
                cls.__name__,
                cls,
                summary=(inspect.getdoc(cls) or "").split("\n")[0][:180],
            )
        )

    workflow_nodes = _build_workflow_nodes(scenario, graphs)

    eval_refs: dict[str, ObjectRef] = {}
    try:
        from core.quality.agent_eval import evaluate_case
        from core.quality.metrics import score_case

        eval_refs["evaluate_case"] = ref_from_object(
            "eval", "evaluate_case", evaluate_case, summary="行为层用例评测入口"
        )
        eval_refs["score_case"] = ref_from_object(
            "eval", "score_case", score_case, summary="确定性评分：覆盖 / 工具 / 拒答"
        )
    except Exception:  # noqa: BLE001
        pass

    return ObjectIndex(
        scenario=scenario_ref,
        agent=agent_ref,
        tools=tools,
        middleware=middleware,
        workflow_nodes=workflow_nodes,
        eval_refs=eval_refs,
    )


def case_tool_index(
    cases: Iterable[dict],
    results: Iterable[dict] | None = None,
) -> dict[str, dict[str, list[str]]]:
    """工具 → 期望/实际使用它的案例 ID、通过案例 ID。"""
    index: dict[str, dict[str, list[str]]] = {}

    def entry(name: str) -> dict[str, list[str]]:
        return index.setdefault(name, {"expected": [], "actual": [], "passed": [], "total": []})

    def add(bucket: dict[str, list[str]], key: str, value: Any) -> None:
        if value is None:
            return
        text = str(value)
        bucket[key].append(text)
        bucket["total"].append(text)

    for case in cases or []:
        names = list(case.get("expected_tools") or []) + list(case.get("expected_tools_any") or [])
        for name in dict.fromkeys(str(item) for item in names if item):
            add(entry(name), "expected", case.get("id"))

    for row in results or []:
        for name in dict.fromkeys(str(item) for item in (row.get("tool_names") or []) if item):
            bucket = entry(name)
            add(bucket, "actual", row.get("id"))
            if row.get("passed"):
                bucket["passed"].append(str(row.get("id")))

    for bucket in index.values():
        for key in ("expected", "actual", "passed", "total"):
            bucket[key] = list(dict.fromkeys(bucket[key]))
    return index


def trace_ref(trace_id: str | None, events: list[dict] | None = None) -> ObjectRef:
    events = events or []
    return ObjectRef(
        kind="trace",
        name=str(trace_id or "（无 trace_id）"),
        summary=f"{len(events)} 个事件" if trace_id else "该结果没有记录 trace",
        note="本地 trace" if trace_id else "未运行或旧版结果",
        meta={"events": len(events), "trace_id": trace_id},
    )


def case_object_chain(
    agent,
    row: dict,
    *,
    index: ObjectIndex | None = None,
) -> list[ObjectRef]:
    index = index or build_object_index(agent)
    refs: list[ObjectRef] = [index.scenario]

    actual = [str(item) for item in (row.get("tool_names") or []) if item]
    expected = [
        str(item)
        for item in (list(row.get("expected_tools") or []) + list(row.get("expected_tools_any") or []))
        if item
    ]
    for name in dict.fromkeys(actual + expected):
        ref = index.tools.get(name) or ref_from_object(
            "tool", name, None, summary="场景未注册该工具（可能来自旧报告）"
        )
        refs.append(replace(ref, note="实际调用" if name in actual else "期望调用"))

    seen: set[tuple[str, str]] = set()
    for order, mw in enumerate(getattr(agent, "middleware", []) or [], 1):
        cls = type(mw)
        key = (cls.__module__, cls.__qualname__)
        if key in seen:
            continue
        seen.add(key)
        ref = index.find("middleware", cls.__name__)
        if ref is not None:
            refs.append(replace(ref, note=f"第 {order} 层"))

    refs.extend(index.eval_refs.values())
    refs.append(trace_ref(row.get("trace_id")))
    return refs


def render_object_card(ref: ObjectRef, *, show_source: bool = True) -> None:
    with st.container(border=True):
        badge = "外部" if ref.external else "项目"
        st.markdown(f"**{ref.name}** · `{ref.kind}` · {badge}")
        if ref.summary:
            st.caption(ref.summary)
        if ref.note:
            st.caption(ref.note)
        st.code(ref.location, language="text")
        if show_source and ref.source:
            with st.popover("查看源码"):
                st.code(ref.source, language="python")
        elif show_source:
            st.caption("源码不可用（第三方对象或动态对象）")


def _render_tool_group(tools: list[ObjectRef]) -> None:
    if not tools:
        return
    st.markdown("**工具对象**")
    for ref in tools:
        render_object_card(ref)
        st.button(
            "在架构页查看该工具",
            key=f"object-arch-{ref.kind}-{ref.name}",
            on_click=navigate,
            args=("architecture", ref.name),
        )


def _render_middleware_group(middleware: list[ObjectRef]) -> None:
    if not middleware:
        return
    rows = [
        {"层": ref.note or "-", "中间件": ref.name, "来源": ref.location}
        for ref in middleware
    ]
    compact_table(rows, height=260, key="object-middleware-table")
    names = [ref.name for ref in middleware]
    selected = st.selectbox("查看中间件对象", names, key="object-middleware-select")
    ref = next((item for item in middleware if item.name == selected), None)
    if ref is not None:
        render_object_card(ref)
        st.button(
            "在架构页查看该中间件",
            key=f"object-arch-middleware-{ref.name}",
            on_click=navigate,
            args=("architecture", ref.name),
        )


def _render_eval_group(refs: list[ObjectRef]) -> None:
    if not refs:
        return
    for ref in refs:
        with st.container(border=True):
            st.markdown(f"**{ref.name}** · `{ref.kind}`")
            st.caption(ref.summary)
            st.code(ref.location, language="text")


def render_case_object_panel(
    agent,
    row: dict,
    *,
    index: ObjectIndex | None = None,
) -> None:
    """从一条案例结果渲染：场景 → 工具 → 中间件 → 评测 → trace。"""
    index = index or build_object_index(agent)
    chain = case_object_chain(agent, row, index=index)
    groups: dict[str, list[ObjectRef]] = {}
    for ref in chain:
        groups.setdefault(ref.kind, []).append(ref)

    st.caption("从当前案例出发，定位它涉及的具体实现对象；点击源码可查看实现。")
    scenario_refs = groups.get("scenario") or [index.scenario]
    for ref in scenario_refs:
        render_object_card(ref)

    _render_tool_group(groups.get("tool") or [])

    middleware_refs = groups.get("middleware") or []
    if middleware_refs:
        with st.expander(f"中间件链（{len(middleware_refs)} 层）", expanded=False):
            _render_middleware_group(middleware_refs)

    eval_refs = groups.get("eval") or []
    if eval_refs:
        with st.expander("评测对象", expanded=False):
            _render_eval_group(eval_refs)

    trace_refs = groups.get("trace") or []
    if trace_refs:
        ref = trace_refs[0]
        with st.expander("执行轨迹", expanded=False):
            st.caption(f"`{ref.name}` ｜ {ref.summary} ｜ {ref.note}")
            render_trace_timeline(ref.meta.get("trace_id"))
