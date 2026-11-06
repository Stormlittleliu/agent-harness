# -*- coding: utf-8 -*-
"""素材对象的统一契约：kind、URI、引用与 descriptor。

URI 规范：

- 工具：``ah://tool/<id>``
- 场景：``ah://scenario/<id>``
- 工作流块：``ah://block/<id>``
- 场景内工作流：``ah://workflow/<scenario>/<workflow>``

工作流多一层，是因为同名工作流可以出现在多个场景里（例如 ``qa``）；
把场景名放进 URI 后，URI 才是全局唯一的。

这里只做解析 / 构造 / 校验 / 序列化，不读任何业务目录。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

URI_SCHEME = "ah"

KIND_LABELS: dict["ResourceKind", str] = {}
KIND_DESCRIPTIONS: dict["ResourceKind", str] = {}


class ResourceURIError(ValueError):
    """URI 不合法（格式、kind、id 或层级不对）。"""


class ResourceNotFoundError(LookupError):
    """URI 合法，但目录里没有这个资源。"""


class ResourceKind(str, Enum):
    TOOL = "tool"
    WORKFLOW = "workflow"
    SCENARIO = "scenario"
    BLOCK = "block"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def parse(cls, value: Any) -> "ResourceKind":
        """接受枚举或字符串（大小写不敏感）；未知 kind 抛 ResourceURIError。"""
        if isinstance(value, cls):
            return value
        text = str(value or "").strip().lower()
        for item in cls:
            if item.value == text:
                return item
        available = "、".join(item.value for item in cls)
        raise ResourceURIError(f"未知资源类型：{value!r}（可用：{available}）")


KIND_LABELS.update(
    {
        ResourceKind.TOOL: "工具",
        ResourceKind.WORKFLOW: "工作流",
        ResourceKind.SCENARIO: "场景",
        ResourceKind.BLOCK: "工作流块",
    }
)
KIND_DESCRIPTIONS.update(
    {
        ResourceKind.TOOL: "Agent 可调用的工具，按工具池登记，含参数 JSON schema。",
        ResourceKind.WORKFLOW: "spec 场景里的工作流（节点 + 边），按场景/工作流定位。",
        ResourceKind.SCENARIO: "场景库中的场景，含是否由 spec 接管、可编辑性等元数据。",
        ResourceKind.BLOCK: "spec 工作流可用的块（节点函数），含参数与输入/输出端口。",
    }
)


def normalize_kind(value: Any) -> ResourceKind:
    return ResourceKind.parse(value)


def empty_object_schema() -> dict[str, Any]:
    """没有 schema 时的统一兜底：合法但空的 object schema。"""
    return {"type": "object", "properties": {}, "required": []}


_FORBIDDEN_ID_CHARS = frozenset("/\\?#%")
_MAX_SEGMENT_LENGTH = 160


def validate_resource_id(kind: Any, resource_id: Any) -> str:
    """校验并返回 id 原文。

    - 所有 kind 的 id 都不能为空、不能带空白 / ``/\\?#%`` / 控制字符；
    - workflow 的 id 必须是 ``<scenario>/<workflow>`` 两段，其余 kind 只能一段。
    """
    kind = normalize_kind(kind)
    text = str(resource_id or "")
    if not text:
        raise ResourceURIError(f"{kind.value} 的 id 不能为空")
    if text != text.strip():
        raise ResourceURIError(f"{kind.value} 的 id 不能有首尾空白：{text!r}")
    segments = text.split("/")
    if kind is ResourceKind.WORKFLOW:
        if len(segments) != 2:
            raise ResourceURIError(
                f"workflow 的 id 必须是 <scenario>/<workflow>：{text!r}"
            )
    elif len(segments) != 1:
        raise ResourceURIError(f"{kind.value} 的 id 不能包含 '/'：{text!r}")
    for segment in segments:
        if not segment or segment in {".", ".."}:
            raise ResourceURIError(f"{kind.value} 的 id 含空段或相对路径：{text!r}")
        if len(segment) > _MAX_SEGMENT_LENGTH:
            raise ResourceURIError(f"{kind.value} 的 id 过长：{text!r}")
        if any(char.isspace() for char in segment):
            raise ResourceURIError(f"{kind.value} 的 id 不能含空白：{text!r}")
        if any(ord(char) < 32 for char in segment):
            raise ResourceURIError(f"{kind.value} 的 id 不能含控制字符：{text!r}")
        if _FORBIDDEN_ID_CHARS & set(segment):
            raise ResourceURIError(f"{kind.value} 的 id 含保留字符：{text!r}")
    return text


def build_uri(kind: Any, resource_id: Any) -> str:
    kind = normalize_kind(kind)
    resource_id = validate_resource_id(kind, resource_id)
    return f"{URI_SCHEME}://{kind.value}/{resource_id}"


@dataclass(frozen=True)
class ResourceRef:
    """一个素材对象的稳定引用。``str(ref)`` 就是规范 URI。"""

    kind: ResourceKind
    id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", normalize_kind(self.kind))
        object.__setattr__(self, "id", validate_resource_id(self.kind, self.id))

    @property
    def uri(self) -> str:
        return build_uri(self.kind, self.id)

    @classmethod
    def from_parts(cls, kind: Any, resource_id: Any) -> "ResourceRef":
        return cls(normalize_kind(kind), str(resource_id or ""))

    @classmethod
    def from_uri(cls, uri: str) -> "ResourceRef":
        return parse_uri(uri)

    def to_dict(self) -> dict[str, str]:
        return {"uri": self.uri, "kind": self.kind.value, "id": self.id}

    def __str__(self) -> str:
        return self.uri


def parse_uri(uri: str) -> ResourceRef:
    """把 ``ah://<kind>/<id>`` 解析成 ResourceRef；非法输入抛 ResourceURIError。"""
    text = str(uri or "").strip()
    if not text:
        raise ResourceURIError("URI 不能为空")
    parts = urlsplit(text)
    if parts.scheme.lower() != URI_SCHEME:
        raise ResourceURIError(f"URI 必须使用 {URI_SCHEME}:// 协议：{text!r}")
    if parts.query or parts.fragment:
        raise ResourceURIError(f"URI 不能带 query / fragment：{text!r}")
    if not parts.netloc:
        raise ResourceURIError(f"URI 缺少资源类型：{text!r}")
    kind = normalize_kind(parts.netloc)
    path = parts.path
    if not path.startswith("/") or path in {"", "/"}:
        raise ResourceURIError(f"URI 缺少 id：{text!r}")
    raw = path[1:]
    if raw.endswith("/"):
        raise ResourceURIError(f"URI 不能以 '/' 结尾：{text!r}")
    segments = raw.split("/")
    if any(not segment for segment in segments):
        raise ResourceURIError(f"URI 含空路径段：{text!r}")
    resource_id = "/".join(segments)
    # validate_resource_id 会按 kind 检查段数（workflow 两段，其余一段）。
    return ResourceRef(kind, resource_id)


def _as_tags(values: Iterable[Any] | None) -> tuple[str, ...]:
    tags: list[str] = []
    for value in values or ():
        text = str(value or "").strip()
        if text and text not in tags:
            tags.append(text)
    return tuple(tags)


def _as_schema(value: Mapping[str, Any] | None) -> dict[str, Any]:
    schema = dict(value or {})
    if schema.get("type") != "object" or "properties" not in schema:
        schema = empty_object_schema()
    else:
        schema["properties"] = dict(schema.get("properties") or {})
        schema.setdefault("required", [])
    return schema


@dataclass(frozen=True)
class ResourceDescriptor:
    """一个素材对象的只读描述；``to_dict()`` 可直接 JSON 序列化。"""

    kind: ResourceKind
    id: str
    name: str = ""
    label: str = ""
    description: str = ""
    tags: tuple[str, ...] = ()
    source: str = ""
    version: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    input_schema: dict[str, Any] = field(default_factory=dict)
    uri: str = ""

    def __post_init__(self) -> None:
        kind = normalize_kind(self.kind)
        resource_id = validate_resource_id(kind, self.id)
        canonical = build_uri(kind, resource_id)
        if self.uri and str(self.uri) != canonical:
            raise ResourceURIError(
                f"descriptor.uri 与 kind/id 不一致：{self.uri!r} != {canonical!r}"
            )
        name = str(self.name or resource_id)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "id", resource_id)
        object.__setattr__(self, "uri", canonical)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "label", str(self.label or name))
        object.__setattr__(self, "description", str(self.description or ""))
        object.__setattr__(self, "tags", _as_tags(self.tags))
        object.__setattr__(self, "source", str(self.source or ""))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))
        object.__setattr__(self, "input_schema", _as_schema(self.input_schema))

    @property
    def ref(self) -> ResourceRef:
        return ResourceRef(self.kind, self.id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "kind": self.kind.value,
            "id": self.id,
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "tags": list(self.tags),
            "source": self.source,
            "version": self.version,
            "metadata": dict(self.metadata),
            "input_schema": dict(self.input_schema),
        }
