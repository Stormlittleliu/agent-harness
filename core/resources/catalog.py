# -*- coding: utf-8 -*-
"""资源目录：把四类素材统一成一个只读的 list / get / search 接口。

搜索是**词法**的，不是向量检索：

- 在 name / label / description / tags 上打分；
- 中文优先用 jieba 切词，jieba 不可用时退化为整段 + 二元组；
- 英文按 ``[a-z0-9_]+`` 切词；
- 排序固定为 ``(-score, kind 顺序, uri)``，同一 query 多次结果一致；
- 返回里带 ``score`` / ``match_reasons``，明确告诉调用方"为什么命中"。

不读取 embedding、不发起模型调用、不访问网络；工具 / 工作流 / 场景 / 块 provider
都不构造场景，也不 import ``core.llm.factory``（已用无 API key 环境验证）。
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from core.resources.contracts import (
    KIND_DESCRIPTIONS,
    KIND_LABELS,
    ResourceDescriptor,
    ResourceKind,
    ResourceNotFoundError,
    normalize_kind,
    parse_uri,
)
from core.resources.providers import default_providers

_ASCII_RE = re.compile(r"[a-z0-9_]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")

# 允许测试 monkeypatch 成"jieba 不可用"来验证降级路径。
_JIEBA: Any = None
_JIEBA_TRIED = False


def _jieba_module():
    global _JIEBA, _JIEBA_TRIED
    if not _JIEBA_TRIED:
        _JIEBA_TRIED = True
        try:
            import jieba  # type: ignore

            _JIEBA = jieba
        except Exception:  # noqa: BLE001 - 可选依赖，缺了就用 n-gram
            _JIEBA = None
    return _JIEBA


def tokenize(text: Any) -> list[str]:
    """把查询切成用于词法匹配的词；中英文都覆盖，结果去重且保序。"""
    lowered = str(text or "").strip().lower()
    if not lowered:
        return []
    terms: list[str] = []
    for match in _ASCII_RE.finditer(lowered):
        terms.append(match.group(0))
    jieba = _jieba_module()
    for match in _CJK_RE.finditer(lowered):
        run = match.group(0)
        if jieba is not None:
            try:
                parts = [str(part).strip().lower() for part in jieba.lcut(run)]
            except Exception:  # noqa: BLE001 - 分词失败不能影响搜索
                parts = []
            terms.extend(part for part in parts if part)
        else:
            terms.append(run)
            if len(run) > 1:
                terms.extend(run[index:index + 2] for index in range(len(run) - 1))
    result: list[str] = []
    for term in terms:
        if not term or term in result:
            continue
        if _CJK_RE.fullmatch(term) and len(term) < 2:
            continue
        result.append(term)
    return result


def _phrase(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or "").strip().lower())


_FIELD_WEIGHTS = (
    ("名称", 4.0),
    ("显示名", 4.0),
    ("描述", 1.5),
)


def score_descriptor(
    descriptor: ResourceDescriptor,
    terms: Iterable[str],
    phrase: str = "",
) -> tuple[float, list[str], list[str]]:
    """对一个 descriptor 做词法打分，返回 ``(score, reasons, matched_terms)``。"""
    score = 0.0
    reasons: list[str] = []
    matched: list[str] = []
    fields = (
        ("名称", descriptor.name, _FIELD_WEIGHTS[0][1]),
        ("显示名", descriptor.label, _FIELD_WEIGHTS[1][1]),
        ("描述", descriptor.description, _FIELD_WEIGHTS[2][1]),
    )
    for term in terms:
        hits: list[str] = []
        for field_label, value, weight in fields:
            lowered = (value or "").lower()
            count = lowered.count(term)
            if count:
                score += weight * (1.0 + 0.15 * min(count - 1, 3))
                hits.append(field_label)
        tag_hits = [tag for tag in descriptor.tags if term in tag.lower()]
        if tag_hits:
            score += 2.5 * (1.0 + 0.1 * min(len(tag_hits) - 1, 3))
            hits.append("标签")
        if hits:
            matched.append(term)
            reasons.append(f"「{term}」命中" + "、".join(dict.fromkeys(hits)))
    if phrase and len(phrase) >= 2:
        name = (descriptor.name or "").lower()
        label = (descriptor.label or "").lower()
        if phrase in name or phrase in label:
            score += 3.0
            reasons.append(f"整体短语「{phrase}」命中名称/显示名")
        elif phrase in (descriptor.description or "").lower():
            score += 1.0
            reasons.append(f"整体短语「{phrase}」命中描述")
        elif any(phrase in tag.lower() for tag in descriptor.tags):
            score += 1.5
            reasons.append(f"整体短语「{phrase}」命中标签")
    return score, list(dict.fromkeys(reasons)), matched


_KIND_ORDER = {kind.value: index for index, kind in enumerate(ResourceKind)}


def _clamp(limit: Any, default: int) -> int:
    if limit is None:
        return default
    try:
        value = int(limit)
    except (TypeError, ValueError):
        return default
    return max(1, min(value, 200))


class ResourceCatalog:
    """四类素材的只读目录；默认 provider 全部惰性 import。"""

    def __init__(self, providers: Iterable[Any] | None = None) -> None:
        self._providers = list(default_providers() if providers is None else providers)
        self._by_kind: dict[ResourceKind, Any] = {}
        for provider in self._providers:
            kind = normalize_kind(getattr(provider, "kind", None))
            self._by_kind[kind] = provider

    # ------------------------------------------------------------ 内部
    def _kind_sequence(self, kind: Any = None) -> list[ResourceKind]:
        if kind is None or (isinstance(kind, str) and not kind.strip()):
            return list(ResourceKind)
        return [normalize_kind(kind)]

    def _items(self, kind: Any = None) -> list[ResourceDescriptor]:
        items: list[ResourceDescriptor] = []
        for current in self._kind_sequence(kind):
            provider = self._by_kind.get(current)
            if provider is not None:
                items.extend(provider.items())
        return items

    @staticmethod
    def _sorted(items: Iterable[ResourceDescriptor]) -> list[ResourceDescriptor]:
        return sorted(items, key=lambda item: (_KIND_ORDER[item.kind.value], item.uri))

    # ------------------------------------------------------------ 公共 API
    def kinds(self) -> list[dict[str, Any]]:
        """四类资源的说明与数量；用于 Agent 先了解目录里有什么。"""
        result = []
        for kind in ResourceKind:
            provider = self._by_kind.get(kind)
            count = len(provider.items()) if provider is not None else 0
            result.append(
                {
                    "kind": kind.value,
                    "label": KIND_LABELS.get(kind, kind.value),
                    "description": KIND_DESCRIPTIONS.get(kind, ""),
                    "count": count,
                }
            )
        return result

    def list(self, kind: Any = None, query: Any = None, limit: int = 200) -> list[dict[str, Any]]:
        """列出 descriptor；``query`` 只做词法过滤，不返回分数。"""
        items = self._sorted(self._items(kind))
        text = str(query or "").strip()
        if text:
            terms = tokenize(text)
            if not terms:
                return []
            phrase = _phrase(text)
            items = [
                item for item in items
                if score_descriptor(item, terms, phrase)[0] > 0
            ]
        return [item.to_dict() for item in items[: _clamp(limit, 200)]]

    def get(self, uri: str) -> dict[str, Any]:
        """按 URI 取一个 descriptor；非法 URI / 不存在都抛异常。"""
        ref = parse_uri(uri)
        provider = self._by_kind.get(ref.kind)
        descriptor = provider.get(ref.id) if provider is not None else None
        if descriptor is None:
            raise ResourceNotFoundError(f"没有找到资源：{ref.uri}")
        return descriptor.to_dict()

    def search(self, query: Any, kind: Any = None, limit: int = 20) -> list[dict[str, Any]]:
        """词法搜索；返回 descriptor + score / match_reasons / matched_terms。"""
        text = str(query or "").strip()
        terms = tokenize(text)
        phrase = _phrase(text)
        rows: list[dict[str, Any]] = []
        for descriptor in self._items(kind):
            if terms:
                score, reasons, matched = score_descriptor(descriptor, terms, phrase)
                if score <= 0:
                    continue
            else:
                score, reasons, matched = 0.0, ["空查询：按目录顺序返回"], []
            row = descriptor.to_dict()
            row.update(
                {
                    "score": round(float(score), 3),
                    "match_reasons": reasons,
                    "match_reason": "；".join(reasons),
                    "matched_terms": list(matched),
                }
            )
            rows.append(row)
        rows.sort(key=lambda row: (-row["score"], _KIND_ORDER[row["kind"]], row["uri"]))
        return rows[: _clamp(limit, 20)]
