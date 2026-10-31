# -*- coding: utf-8 -*-
"""评测数据与检索组件：复用 tools.rag 的 embedding 和检索器。

评测使用独立的内存 Chroma 集合，不污染业务知识库（chroma_db/）。
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_chroma import Chroma  # noqa: E402
from langchain_core.documents import Document  # noqa: E402
from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: E402

from core.tools.rag.embedding import embed_model  # noqa: E402
from core.tools.rag.retrievers import (  # noqa: E402
    ChunkIdRetriever,
    KeywordBM25Retriever,
    TopKEnsembleRetriever,
    get_tokenizer,
)
from core.utils.config_handler import chroma_conf, rag_conf  # noqa: E402
from core.quality.paths import DATASETS_DIR  # noqa: E402

BATCH_SIZE = 10


def load_jsonl(path: Path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def split_documents(docs_dir: Path):
    """按 chroma.yml 的切片参数切分目录下的 txt/md 文档。"""
    documents = []
    for path in sorted(Path(docs_dir).iterdir()):
        if path.suffix.lower() not in {".txt", ".md"}:
            continue
        text = path.read_text(encoding="utf-8")
        file_type = path.suffix.lower().lstrip(".")
        conf = chroma_conf["chunking"].get(file_type, chroma_conf["chunking"]["txt"])
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=conf["chunk_size"],
            chunk_overlap=conf["chunk_overlap"],
            separators=conf["separators"],
            length_function=len,
        )
        chunks = splitter.split_text(text) if len(text) > int(chroma_conf["max_split_char_number"]) else [text]
        for index, chunk in enumerate(chunks):
            documents.append(Document(
                page_content=chunk,
                metadata={
                    "source": path.name,
                    "file_type": file_type,
                    "chunk_id": f"{path.stem}-{index}",
                },
            ))
    return documents


def build_store(collection_name: str, documents, embedding_function=None):
    """构建内存 Chroma 集合；不写业务 chroma_db。"""
    store = Chroma(collection_name=collection_name, embedding_function=embedding_function or embed_model)
    for start in range(0, len(documents), BATCH_SIZE):
        batch = documents[start:start + BATCH_SIZE]
        for attempt in range(3):
            try:
                store.add_documents(batch)
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == 2:
                    raise
                print(f"  embedding batch {start} failed ({exc}), retry {attempt + 1}")
                time.sleep(2)
    return store


def build_retrievers(store, corpus_documents, k: int = None):
    k = int(k or rag_conf["retrieval_k"])
    vector = store.as_retriever(search_kwargs={"k": k})
    hybrid = TopKEnsembleRetriever(
        retrievers=[
            ChunkIdRetriever(inner=vector),
            KeywordBM25Retriever(
                corpus_loader=lambda: corpus_documents,
                k=k,
                tokenize=get_tokenizer(),
            ),
        ],
        weights=[
            float(rag_conf["hybrid_weights"]["vector"]),
            float(rag_conf["hybrid_weights"]["bm25"]),
        ],
        id_key="chunk_id",
        k=k,
    )
    return {"vector": vector, "hybrid": hybrid}
