# -*- coding: utf-8 -*-
"""RAG 公开集适配器：RGB（中文）与 MultiHop-RAG（英文）。"""
import json

from core.benchmarks.adapters.base import BenchmarkAdapter, git_version
from core.benchmarks.paths import MULTIHOP_ROOT, RGB_ROOT
from core.benchmarks.schema import BenchTask

RGB_DATA = RGB_ROOT / "data" / "zh_refine.json"
MULTIHOP_DATA = MULTIHOP_ROOT / "data" / "MultiHopRAG.json"


def read_jsonl(path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


class RGBAdapter(BenchmarkAdapter):
    name = "rgb"
    license = "CC BY-NC-SA 4.0"
    url = "https://github.com/chen700564/RGB"

    def available(self) -> bool:
        return RGB_DATA.exists()

    def version(self) -> str:
        return git_version(RGB_ROOT)

    def note(self) -> str:
        return "中文 RAG 检索；300 条 zh_refine，非商业许可。"

    def load(self) -> list[BenchTask]:
        if not self.available():
            return []
        rows = []
        for index, item in enumerate(read_jsonl(RGB_DATA)):
            rows.append(BenchTask(
                id=f"rgb-zh-{item.get('id', index)}",
                source=self.name,
                source_version=self.version(),
                split="zh_refine",
                category="rag_rgb",
                task_type="rag_retrieval",
                instruction=item.get("query", ""),
                grader="mixed",
                bucket="capability",
                environment={"kind": "rgb", "split": "zh_refine", "runner": "native"},
                success_criteria=[
                    {"type": "answer", "value": item.get("answer", "")},
                    {"type": "evidence", "count": len(item.get("positive") or [])},
                ],
                license=self.license,
                url=self.url,
                metadata={
                    "positive_count": len(item.get("positive") or []),
                    "negative_count": len(item.get("negative") or []),
                },
            ))
        return rows


class MultiHopAdapter(BenchmarkAdapter):
    name = "multihop-rag"
    license = "ODC-BY 1.0"
    url = "https://github.com/yixuantt/MultiHop-RAG"

    def available(self) -> bool:
        return MULTIHOP_DATA.exists()

    def version(self) -> str:
        return git_version(MULTIHOP_ROOT)

    def note(self) -> str:
        return "英文多跳检索；2556 条，609 篇语料。"

    def load(self) -> list[BenchTask]:
        if not self.available():
            return []
        rows = []
        for index, item in enumerate(json.loads(MULTIHOP_DATA.read_text(encoding="utf-8"))):
            evidence = item.get("evidence_list") or []
            rows.append(BenchTask(
                id=f"multihop-{index}",
                source=self.name,
                source_version=self.version(),
                split="test",
                category=f"rag_multihop_{item.get('question_type', 'unknown')}",
                task_type="rag_retrieval",
                instruction=item.get("query", ""),
                grader="mixed",
                bucket="adversarial" if item.get("question_type") == "null_query" else "capability",
                environment={"kind": "multihop", "runner": "native"},
                success_criteria=[
                    {"type": "answer", "value": item.get("answer", "")},
                    {"type": "evidence", "count": len(evidence)},
                ],
                license=self.license,
                url=self.url,
                metadata={"question_type": item.get("question_type"), "evidence_count": len(evidence)},
            ))
        return rows
