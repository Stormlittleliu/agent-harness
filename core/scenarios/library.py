# -*- coding: utf-8 -*-
"""场景库：界面层唯一的"有哪些场景"来源。

三件事：

1. **元数据**：中文名 / 图标 / 类型 / 一句话描述 / 示例任务 / 是否有工作流 / 运行时页；
   代码场景写静态表，spec 场景从 `data/specs/<name>/active.json` 动态发现；
2. **归属**：可编辑与否只读 ``ownership.status()``，不另造开关；
3. **接管**：`data/specs/<name>/active.json` 一旦存在，同名场景就由 spec 构建，
   原代码实现降为参考（删掉 spec 目录即可回退）。

为什么要有这一层：之前"哪个场景"被分散在顶部的入口模式、`SCENARIO_LABELS`、
`DASHBOARD_PRESETS` 和编辑器的 `data/specs` 扫描里，四处各说各话。现在只有这一张表。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from core.scenarios.ownership import OWNER_CODE, status
from core.scenarios.spec import SPEC_ROOT, active_spec_path, load_active_spec

KIND_AGENT = "agent"
KIND_ROUTER = "router"


@dataclass(frozen=True)
class ScenarioEntry:
    """场景库里的一条记录。"""

    name: str
    label: str
    icon: str = "💬"
    kind: str = KIND_AGENT
    description: str = ""
    examples: tuple[str, ...] = ()
    has_workflow: bool = False
    supports_runtime: bool = False
    # 工具来自哪个"工具箱"；None 表示这个场景还没有命名工具箱（走通用池）。
    pool: str | None = None
    owner: str | None = None
    editable: bool = False
    from_spec: bool = False
    cases: int = 0
    issue: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def is_router(self) -> bool:
        return self.kind == KIND_ROUTER

    @property
    def title(self) -> str:
        return f"{self.icon} {self.label}"

    @property
    def badge(self) -> str:
        if not self.from_spec:
            return "code"
        return "spec · 可编辑" if self.editable else "spec · 只读"


# 代码场景的元数据。新增场景时补一行，`tests/test_scenario_library.py` 会检查覆盖率。
_STATIC: dict[str, dict] = {
    "router": {
        "label": "总路由",
        "icon": "🔀",
        "kind": KIND_ROUTER,
        "description": "对话式前台，按确定性规则把请求分流到子场景",
        "examples": (
            "扫地机器人回充失败怎么办？",
            "帮我写一个输出 99 乘法表的 Python 脚本并运行验证。",
            "对比三份资料，告诉我它们对 Agent 评测的主要差异。",
        ),
        "pool": "router",
    },
    "workspace_assistant": {
        "label": "办公学习",
        "icon": "📚",
        "description": "办公 / 学习 / 内容创作 / 信息管理 / 跨语言助手",
        "examples": (
            "根据笔记，Agent 评测应该关注哪些指标？",
            "Summarize the product brief in Chinese.",
            "请记住：我喜欢简洁的回答，并用要点列出。",
        ),
        "has_workflow": True,
        "pool": "workspace_assistant",
    },
    "coding_demo": {
        "label": "编码运行时",
        "icon": "💻",
        "description": "读写文件 / 跑命令 / 任务图 / hooks / 单层 subagent",
        "examples": (
            "读取 README.md，并告诉我这个工作区叫什么名字。",
            "在工作区运行 echo hello，并告诉我输出。",
            "创建一个任务：检查项目结构。",
        ),
        "supports_runtime": True,
        "pool": "coding_demo",
    },
    "robot_vacuum": {
        "label": "扫地机器人",
        "icon": "🤖",
        "description": "扫地 / 扫拖机器人客服：知识库问答 + 报告 + 审批",
        "examples": (
            "小户型适合哪些扫地机器人？",
            "给我生成我的使用报告",
            "今天天气怎么样",
        ),
        "has_workflow": True,
        "pool": "robot_vacuum",
    },
    "research_assistant": {
        "label": "研究调研",
        "icon": "🔎",
        "description": "多资料研究：规划 → 只读 fan-out → 汇总 → 引用 → 报告",
        "examples": (
            "列出当前有哪些研究资料。",
            "对比三份资料对 Agent 评测的主要观点，并给出来源。",
        ),
        "has_workflow": True,
        "pool": "research_assistant",
    },
    "mcp_demo": {
        "label": "MCP 工具",
        "icon": "🔌",
        "description": "stdio MCP：Memory + Fetch",
        "examples": (
            "请记住：我喜欢小户型，家里有猫。",
            "读取 https://example.com 并告诉我页面标题。",
        ),
        "pool": "mcp_demo",
    },
    "structured_demo": {
        "label": "结构化输出",
        "icon": "🧱",
        "description": "Pydantic schema 约束最终报告",
        "examples": (
            "材料：接口联调延后到周五；测试环境不稳定。请生成结构化报告。",
            "Material: X1 supports 5000Pa suction and 180 minutes runtime.",
        ),
        "pool": "structured_demo",
    },
    "general": {
        "label": "白板",
        "icon": "📝",
        "description": "没有工具、没有工作流的纯对话场景",
        "examples": ("你好，请用一句话介绍你自己。", "1+1 等于几？"),
        "pool": "general",
    },
    "flow_demo": {
        "label": "流程演示",
        "icon": "🎛",
        "description": "由 spec 构建的演示场景：检索 → 生成 → 引用校验",
        "examples": ("根据笔记，Agent 评测应该关注哪些指标？",),
        "has_workflow": True,
        "pool": "office",
    },
}


def _count_cases(path: Path | str | None) -> int:
    if not path:
        return 0
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return 0
    return sum(1 for line in text.splitlines() if line.strip())


def _spec_names() -> list[str]:
    directory = Path(SPEC_ROOT)
    if not directory.is_dir():
        return []
    return sorted(
        child.name
        for child in directory.iterdir()
        if child.is_dir() and (child / "active.json").is_file()
    )


def _entry_from_spec(name: str) -> ScenarioEntry:
    static = _STATIC.get(name, {})
    spec = load_active_spec(name) if active_spec_path(name) else None
    info = status(name)
    owner = info.get("owner")
    # 还没构建过（没有 state.json）时也算可编辑：第一次构建会自动写入基线。
    editable = owner is not None and bool(info.get("editable"))
    path = active_spec_path(name)
    if spec is None:
        return ScenarioEntry(
            name=name,
            label=static.get("label", name),
            icon=static.get("icon", "🧩"),
            kind=static.get("kind", KIND_AGENT),
            description=static.get("description", ""),
            owner=owner,
            editable=False,
            from_spec=True,
            issue=f"active spec 读取失败：{path}",
        )
    cases = 0
    if spec.cases_path:
        candidate = Path(spec.cases_path)
        cases = _count_cases(candidate if candidate.is_absolute() else Path.cwd() / candidate)
    else:
        cases = _count_cases(Path(SPEC_ROOT) / name / "cases.jsonl")
    return ScenarioEntry(
        name=name,
        label=static.get("label", name),
        icon=static.get("icon", "🎛" if name == "flow_demo" else "🧩"),
        kind=spec.kind,
        description=spec.description or static.get("description", ""),
        examples=tuple(static.get("examples", ())),
        has_workflow=bool(spec.workflows) or static.get("has_workflow", False),
        supports_runtime=bool(static.get("supports_runtime", False)),
        pool=static.get("pool"),
        owner=owner or "spec",
        editable=True if owner is None else editable,
        from_spec=True,
        cases=cases,
    )


def _entry_from_code(name: str, static: dict) -> ScenarioEntry:
    info = status(name)
    cases_path = Path("core/scenarios") / name / "cases.jsonl"
    return ScenarioEntry(
        name=name,
        label=static.get("label", name),
        icon=static.get("icon", "💬"),
        kind=static.get("kind", KIND_AGENT),
        description=static.get("description", ""),
        examples=tuple(static.get("examples", ())),
        has_workflow=bool(static.get("has_workflow", False)),
        supports_runtime=bool(static.get("supports_runtime", False)),
        pool=static.get("pool"),
        owner=info.get("owner"),
        editable=False,
        from_spec=False,
        cases=_count_cases(cases_path),
    )


def entries() -> list[ScenarioEntry]:
    """场景库全量：router 优先，其余按中文名排序。"""
    from core.scenarios.registry import list_scenarios

    spec_names = set(_spec_names())
    items: list[ScenarioEntry] = []
    for name in list_scenarios():
        if name in spec_names:
            items.append(_entry_from_spec(name))
        elif name in _STATIC:
            items.append(_entry_from_code(name, _STATIC[name]))
        else:
            # 既不在静态表、也没有 spec 的场景：给一个能用的兜底，别让界面崩。
            items.append(ScenarioEntry(name=name, label=name, description="（缺少场景元数据）"))
    items.sort(key=lambda entry: (entry.kind != KIND_ROUTER, entry.label))
    return items


def names() -> list[str]:
    return [entry.name for entry in entries()]


def entry(name: str) -> ScenarioEntry | None:
    return next((item for item in entries() if item.name == name), None)


def label(name: str) -> str:
    found = entry(name)
    return found.title if found else name


def default_name() -> str:
    """默认打开的场景：优先"可编辑且有工作流"（画布一打开就有东西看）。"""
    items = entries()
    editable = [item for item in items if item.from_spec and item.editable]
    with_workflow = [item for item in editable if item.has_workflow]
    for group in (with_workflow, editable):
        if group:
            return group[0].name
    names_ = {item.name for item in items}
    for candidate in ("workspace_assistant", "general"):
        if candidate in names_:
            return candidate
    return items[0].name if items else "general"


def summary() -> dict:
    """给总览 / 场景页用的一行统计。"""
    items = entries()
    return {
        "total": len(items),
        "spec": sum(1 for item in items if item.from_spec),
        "editable": sum(1 for item in items if item.editable),
        "cases": sum(item.cases for item in items),
        "routers": sum(1 for item in items if item.is_router),
        "items": [item.__dict__ | {"title": item.title, "badge": item.badge} for item in items],
    }


def dump_json() -> str:
    """调试用：把场景库打成 JSON（CLI / 测试都能看）。"""
    return json.dumps(summary(), ensure_ascii=False, indent=2)
