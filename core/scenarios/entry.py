# -*- coding: utf-8 -*-
"""对话入口：决定"哪些场景对用户开放"的唯一开关。

三层各回答一个问题，别混在一起：

- ``library``：有哪些场景；
- ``ownership.state``：这个场景谁说了算（spec / code）；
- ``entry``（本模块）：用户能不能从对话端用它。

入口是**显式动作**，不是"存在即上线"：

- 发布前先校验（spec 能编译、工具在工具箱里、提示词块齐全、节点都有中文说明）；
- 校验不过不写盘，发布失败不会留下半截配置；
- 改完结构但没重新发布，构建页会显示"有未发布改动"，入口仍按发布时的状态。

数据：``data/specs/<name>/entry.yml``。入口只写产品信息（标题 / 一句话 /
开场白 / 排序），结构仍由 spec 决定——所以它不需要参与归属守卫。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SPEC_ROOT = Path(__file__).resolve().parents[2] / "data" / "specs"
ENTRY_FILENAME = "entry.yml"
DEFAULT_ORDER = 100


class EntryError(ValueError):
    """发布校验失败：``errors`` 是给人看的原因列表。"""

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__("；".join(self.errors) or "发布失败")


@dataclass(frozen=True)
class ChatEntry:
    """一个场景在对话端的入口配置。"""

    name: str
    enabled: bool = False
    title: str = ""
    tagline: str = ""
    starters: tuple[str, ...] = ()
    order: int = DEFAULT_ORDER
    # 发布时锁定的结构指纹；和当前 active spec 不一致就是"有未发布改动"。
    published_hash: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def display_title(self) -> str:
        return self.title.strip() or self.name


def entry_path(name: str, root: Path | str = SPEC_ROOT) -> Path:
    return Path(root) / name / ENTRY_FILENAME


def load_entry(name: str, root: Path | str = SPEC_ROOT) -> ChatEntry:
    """读入口配置；没有文件就是"未发布"（不报错，入口页据此过滤）。"""
    path = entry_path(name, root)
    if not path.is_file():
        return ChatEntry(name=name)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return ChatEntry(name=name)
    if not isinstance(data, dict):
        return ChatEntry(name=name)
    starters = data.get("starters") or []
    return ChatEntry(
        name=name,
        enabled=bool(data.get("enabled", False)),
        title=str(data.get("title") or ""),
        tagline=str(data.get("tagline") or ""),
        starters=tuple(str(item) for item in starters if str(item).strip()),
        order=_as_int(data.get("order"), DEFAULT_ORDER),
        published_hash=str(data.get("published_hash") or ""),
        extra={key: value for key, value in data.items() if key not in _KNOWN_FIELDS},
    )


_KNOWN_FIELDS = {"enabled", "title", "tagline", "starters", "order", "published_hash"}


def _as_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def save_entry(entry: ChatEntry, root: Path | str = SPEC_ROOT) -> Path:
    """写 ``entry.yml``；固定 key 顺序 + LF，保证 diff 干净。"""
    path = entry_path(entry.name, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "enabled": bool(entry.enabled),
        "title": entry.title,
        "tagline": entry.tagline,
        "starters": list(entry.starters),
        "order": int(entry.order),
        "published_hash": entry.published_hash,
        **entry.extra,
    }
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
        newline="\n",
    )
    return path


def _has_spec(name: str, root: Path | str) -> bool:
    return (Path(root) / name / "active.json").is_file()


def published_names(root: Path | str = SPEC_ROOT) -> list[str]:
    """已发布（enabled 且还有 spec）的场景名，按入口排序。"""
    root = Path(root)
    if not root.is_dir():
        return []
    found: list[ChatEntry] = []
    for directory in root.iterdir():
        if not directory.is_dir():
            continue
        item = load_entry(directory.name, root)
        if item.enabled and _has_spec(directory.name, root):
            found.append(item)
    found.sort(key=lambda item: (item.order, item.name))
    return [item.name for item in found]


def published_entries(root: Path | str = SPEC_ROOT) -> list[ChatEntry]:
    return [load_entry(name, root) for name in published_names(root)]


def fingerprint(name: str, root: Path | str = SPEC_ROOT) -> str:
    """结构指纹：active spec + 提示词块。用来判断"发布后改过没有"。"""
    from core.prompts.blocks import load_book
    from core.scenarios.spec import load_active_spec

    root = Path(root)
    spec = load_active_spec(name, root=root)
    digest = hashlib.sha256()
    if spec is not None:
        payload = json.dumps(spec.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        digest.update(payload.encode("utf-8"))
    book = load_book(root / name / "prompt.yml")
    for block_id in book.ids():
        block = book.get(block_id)
        if block is None:
            continue
        digest.update(f"{block_id}\x00{block.title}\x00{block.when}\x00{block.body}".encode("utf-8"))
    return digest.hexdigest()[:16]


def drifted(name: str, root: Path | str = SPEC_ROOT) -> bool:
    """已发布但结构变了：入口仍然可用，只是构建页要提醒重新发布。"""
    item = load_entry(name, root)
    if not item.enabled:
        return False
    if not item.published_hash:
        return True
    return item.published_hash != fingerprint(name, root)


# ---------------------------------------------------------------- 校验 / 发布


def validate(name: str, root: Path | str = SPEC_ROOT) -> list[str]:
    """发布前的静态校验：不调用模型，只看"能不能真的跑起来"。

    刻意不构建 Agent：发布是一次明确的点击，不该顺手加载知识库。
    """
    from core.prompts.blocks import load_book
    from core.scenarios.generic import spec_scenario_names
    from core.scenarios.node_docs import describe_node
    from core.scenarios.pools import tool_names
    from core.scenarios.spec import load_active_spec, validate_spec

    root = Path(root)
    errors: list[str] = []
    if name not in spec_scenario_names(root):
        errors.append("这个场景还没有可由 spec 构建的版本（先保存一个版本，或它已被 eject 成代码）")
        return errors
    spec = load_active_spec(name, root=root)
    if spec is None:
        errors.append(f"读不到 active spec：{root / name / 'active.json'}")
        return errors

    available = set(tool_names(name))
    missing = [tool for tool in spec.tools if tool not in available]
    if missing:
        errors.append(
            f"spec 引用了工具箱里没有的工具：{', '.join(missing)}（可用：{', '.join(sorted(available)) or '（空）'}）"
        )
    book = load_book(root / name / "prompt.yml")
    errors.extend(validate_spec(spec, tool_names=available, prompt_book=book))

    if not spec.description.strip():
        errors.append("场景描述是空的：对话入口没有一句话介绍，用户不知道它能干什么")
    for workflow_name, workflow in spec.workflows.items():
        for node in workflow.nodes:
            if describe_node(name, node.id) is None:
                errors.append(
                    f"workflow[{workflow_name}].{node.id} 没有中文说明：调用链上只能显示英文 id"
                )
    return errors


def publish(
    name: str,
    *,
    title: str = "",
    tagline: str = "",
    starters: tuple[str, ...] | list[str] = (),
    order: int = DEFAULT_ORDER,
    root: Path | str = SPEC_ROOT,
) -> ChatEntry:
    """校验通过才写盘；失败抛 ``EntryError``，旧配置保持不变。"""
    errors = validate(name, root)
    if errors:
        raise EntryError(errors)
    entry = ChatEntry(
        name=name,
        enabled=True,
        title=title.strip(),
        tagline=tagline.strip(),
        starters=tuple(str(item).strip() for item in starters if str(item).strip()),
        order=_as_int(order, DEFAULT_ORDER),
        published_hash=fingerprint(name, root),
    )
    save_entry(entry, root)
    return entry


def unpublish(name: str, root: Path | str = SPEC_ROOT) -> ChatEntry:
    """撤回入口：保留产品信息，只把 enabled 关掉。"""
    current = load_entry(name, root)
    entry = ChatEntry(
        name=name,
        enabled=False,
        title=current.title,
        tagline=current.tagline,
        starters=current.starters,
        order=current.order,
        published_hash="",
        extra=current.extra,
    )
    save_entry(entry, root)
    return entry
