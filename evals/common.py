# -*- coding: utf-8 -*-
"""RAG/LLM 评测公共组件：复用 Agent 项目的 embedding、chat model 和检索器。

评测使用独立的内存 Chroma 集合，不污染业务知识库（chroma_db/）。
"""
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_chroma import Chroma  # noqa: E402
from langchain_core.documents import Document  # noqa: E402
from langchain_core.output_parsers import StrOutputParser  # noqa: E402
from langchain_core.prompts import PromptTemplate  # noqa: E402
from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: E402

from model.factory import chat_model, embed_model  # noqa: E402
from rag.retrievers import (  # noqa: E402
    ChunkIdRetriever,
    KeywordBM25Retriever,
    TopKEnsembleRetriever,
    get_tokenizer,
)
from utils.config_handler import chroma_conf, rag_conf  # noqa: E402
from utils.prompt_loader import load_rag_prompts  # noqa: E402

EVALS_ROOT = Path(__file__).resolve().parent
DATASETS_DIR = EVALS_ROOT / "datasets"
REPORTS_DIR = EVALS_ROOT / "reports"
BATCH_SIZE = 10


def load_jsonl(path: Path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", str(text)).lower()


def source_name(doc) -> str:
    return os.path.basename(str((doc.metadata or {}).get("source", "")))


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


def build_store(collection_name: str, documents):
    """构建内存 Chroma 集合；不写业务 chroma_db。"""
    store = Chroma(collection_name=collection_name, embedding_function=embed_model)
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


def build_rag_chain():
    """复用 Agent 项目的 RAG 提示词与聊天模型。"""
    prompt = PromptTemplate.from_template(load_rag_prompts())
    return prompt | chat_model | StrOutputParser()


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
