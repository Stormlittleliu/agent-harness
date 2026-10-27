# -*- coding: utf-8 -*-
"""一次性脚本：清空后只重新导入 4 份主文档。"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kbrag.knowledge_base import KnowledgeBaseService  # noqa: E402

ASSETS = ["尺码推荐.txt", "洗涤养护.txt", "颜色推荐.txt", "新品推荐.md"]

svc = KnowledgeBaseService()
for name in ASSETS:
    text = (ROOT / "scripts" / "assets" / name).read_text(encoding="utf-8")
    file_type = Path(name).suffix.lower().lstrip(".")
    print(name, "->", svc.upload_by_str(text, name, file_type=file_type))

data = svc.chroma.get(include=["metadatas"])
print("chunks:", len(data.get("ids", [])))
print("sources:", dict(Counter((m or {}).get("source") for m in data.get("metadatas", []))))
