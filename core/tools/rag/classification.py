# -*- coding: utf-8 -*-
"""知识库分类：给入库文档打 ``domain`` / ``category``，并做统计。

分类是**入库元数据**，不是模型判断：

- 规则按文件名优先，文件名看不出时再看正文关键词；
- 返回的 ``domain`` 用于检索过滤（服装问题不能召回扫地机器人文档）；
- ``category`` 用于知识库视图分组和后续按类过滤。

新增知识时只改这里的规则，不要让 Chroma 里出现没有 domain 的旧分块。
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

DOMAIN_LABELS = {
    "robot": "扫地机器人",
    "clothing": "服装",
    "general": "通用",
}

CATEGORY_LABELS = {
    ("robot", "faq"): "常见问答",
    ("robot", "troubleshoot"): "故障排除",
    ("robot", "maintenance"): "维护保养",
    ("robot", "purchase"): "选购指南",
    ("clothing", "size"): "尺码",
    ("clothing", "color"): "颜色",
    ("clothing", "care"): "洗涤养护",
    ("clothing", "new"): "新品",
    ("general", "uncategorized"): "未分类",
}

# 文件名 -> (domain, category)；顺序无关，先精确匹配，再前缀匹配。
SOURCE_RULES: tuple[tuple[str, str, str], ...] = (
    ("服装-尺码推荐", "clothing", "size"),
    ("服装-颜色推荐", "clothing", "color"),
    ("服装-洗涤养护", "clothing", "care"),
    ("服装-新品推荐", "clothing", "new"),
    ("故障排除", "robot", "troubleshoot"),
    ("维护保养", "robot", "maintenance"),
    ("选购指南", "robot", "purchase"),
    ("扫地机器人100问", "robot", "faq"),
    ("扫拖一体机器人100问", "robot", "faq"),
)

# 文件名没有命中时的正文兜底；只做“明显属于哪一类”的判断。
CONTENT_RULES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("clothing", "size", "尺码", ("尺码", "身高", "体重", "码数", "S码", "XL")),
    ("clothing", "color", "颜色", ("肤色", "颜色搭配", "冷白皮", "黄皮", "撞色")),
    ("clothing", "care", "洗涤养护", ("洗涤", "机洗", "晾干", "烘干", "面料")),
    ("clothing", "new", "新品", ("新品", "春季新品", "上新")),
    ("robot", "troubleshoot", "故障", ("回充", "不开机", "故障", "报错", "连不上")),
    ("robot", "maintenance", "保养", ("滤网", "拖布", "主刷", "边刷", "清洁")),
    ("robot", "purchase", "选购", ("吸力", "续航", "小户型", "选购")),
)


@dataclass(frozen=True)
class DocClass:
    domain: str
    category: str

    @property
    def domain_label(self) -> str:
        return DOMAIN_LABELS.get(self.domain, self.domain)

    @property
    def category_label(self) -> str:
        return CATEGORY_LABELS.get((self.domain, self.category), self.category)


def classify(filename: str, text: str = "") -> DocClass:
    """文件名优先，正文兜底；都不命中时归到 general/uncategorized。"""
    name = str(filename or "")
    for prefix, domain, category in SOURCE_RULES:
        if prefix in name:
            return DocClass(domain, category)

    lowered = str(text or "").lower()
    best: tuple[int, str, str] | None = None
    for domain, category, _label, words in CONTENT_RULES:
        hits = sum(1 for word in words if word.lower() in lowered)
        if hits and (best is None or hits > best[0]):
            best = (hits, domain, category)
    if best:
        return DocClass(best[1], best[2])
    return DocClass("general", "uncategorized")


def stats() -> list[dict]:
    """按 (domain, category, source) 统计 Chroma 分块；知识库视图用。"""
    from core.tools.rag.vector_store import VectorStoreService

    store = VectorStoreService().vector_store
    data = store.get(include=["metadatas"])
    counters: Counter[tuple[str, str, str]] = Counter()
    for metadata in data.get("metadatas", []):
        metadata = metadata or {}
        domain = str(metadata.get("domain") or "general")
        category = str(metadata.get("category") or "uncategorized")
        source = str(metadata.get("source") or "—")
        counters[(domain, category, source)] += 1

    rows = []
    for (domain, category, source), chunks in sorted(counters.items()):
        rows.append({
            "domain": domain,
            "domain_label": DOMAIN_LABELS.get(domain, domain),
            "category": category,
            "category_label": CATEGORY_LABELS.get((domain, category), category),
            "source": source,
            "chunks": chunks,
        })
    return rows


def summary() -> dict:
    """知识库总览：文档数、分块数、domain/category 计数。"""
    rows = stats()
    by_domain: dict[str, int] = defaultdict(int)
    by_category: dict[str, int] = defaultdict(int)
    sources: set[str] = set()
    for row in rows:
        by_domain[row["domain_label"]] += row["chunks"]
        by_category[f"{row['domain_label']} / {row['category_label']}"] += row["chunks"]
        sources.add(row["source"])
    return {
        "documents": len(sources),
        "chunks": sum(row["chunks"] for row in rows),
        "by_domain": dict(sorted(by_domain.items())),
        "by_category": dict(sorted(by_category.items())),
        "rows": rows,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(summary(), ensure_ascii=False, indent=2))
