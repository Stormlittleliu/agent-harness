# -*- coding: utf-8 -*-
"""评测指标：检索、生成、Agent 行为共用。"""
from __future__ import annotations

import os
import re

REFUSAL_MARKERS = [
    "没有", "无法", "未提供", "不清楚", "不能确定", "不知道",
    "无相关", "暂无", "不包含", "未包含", "资料不足", "未提及",
]


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", str(text)).lower()


def source_name(doc) -> str:
    return os.path.basename(str((doc.metadata or {}).get("source", "")))


def format_context(docs) -> str:
    return "\n\n".join(doc.page_content for doc in docs)


def score_retrieval(retrieved_sources, expected_sources):
    if not expected_sources:
        return None, None
    expected = [normalize(item) for item in expected_sources]
    hit = any(
        any(normalize(source) == exp or normalize(source).endswith(exp) or exp.endswith(normalize(source))
            for exp in expected)
        for source in retrieved_sources
    )
    mrr = 0.0
    for rank, source in enumerate(retrieved_sources, 1):
        if any(normalize(source) == exp or normalize(source).endswith(exp) or exp.endswith(normalize(source))
               for exp in expected):
            mrr = 1.0 / rank
            break
    return hit, mrr


def score_case(case, answer, tool_names):
    """Agent 行为用例的确定性评分。"""
    expected_points = case.get("expected_points", [])
    expected_regex = case.get("expected_regex", [])
    expected_tools = case.get("expected_tools", [])
    expected_tools_any = case.get("expected_tools_any", [])
    should_refuse = bool(case.get("should_refuse"))

    answer_norm = normalize(answer)
    matched = [point for point in expected_points if normalize(point) in answer_norm]
    regex_ok = any(re.search(pattern, answer) for pattern in expected_regex)
    if expected_points:
        coverage = len(matched) / len(expected_points)
    elif expected_regex:
        coverage = 1.0 if regex_ok else 0.0
    else:
        coverage = 1.0
    tools_ok = all(tool in tool_names for tool in expected_tools)
    if expected_tools_any:
        tools_ok = tools_ok and any(tool in tool_names for tool in expected_tools_any)
    refused = any(marker in answer for marker in REFUSAL_MARKERS)

    if should_refuse:
        passed = refused
    else:
        passed = coverage >= 0.5 and tools_ok

    return {
        "coverage": round(coverage, 4),
        "matched_points": matched,
        "regex_ok": regex_ok,
        "tools_ok": tools_ok,
        "refused": refused,
        "passed": passed,
    }


def detect_conflict(docs, question: str):
    """业务集里的尺码/单位冲突检测；需要原始 docs。"""
    texts = " ".join(doc.page_content for doc in docs)
    sources = {source_name(doc) for doc in docs}
    reasons = []
    q = question.lower()
    size_question = bool(re.search(r"尺码|码|身高|体重|size|斤|kg|公斤|号", q, re.IGNORECASE))
    new_product = bool(re.search(r"新品|防风外套|春季新品", q))
    has_jin = "斤" in texts
    has_kg = bool(re.search(r"kg|千克|公斤", texts, re.IGNORECASE))
    size_context = bool(re.search(r"尺码|建议尺码|size", texts, re.IGNORECASE))
    if size_question and has_jin and has_kg and size_context:
        reasons.append("unit_mismatch: 斤 vs kg")
    if new_product and {"尺码推荐.txt", "新品推荐.md"} <= sources and has_jin and has_kg:
        reasons.append("size_conflict: 尺码表与新品推荐同时命中")
    return bool(reasons), reasons
