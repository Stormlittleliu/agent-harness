"""向量库服务：文件解析 → 按类型切片 → 分批写入 Chroma。

与基础项目 KnowledgeBase-RAG-LLM-System 对齐的关键点：
1. 支持 txt / pdf / docx / md 四种格式；
2. 每种文件类型使用自己的切片参数（config/chroma.yml）；
3. md5 去重记录带来源文件名（`md5\\t文件名`），同一文件内容变化时替换旧分块；
4. 兼容 DashScope text-embedding-v4 的单批 10 条限制；本地 BGE 同样分批写入。
"""
import os
import uuid
from datetime import datetime

from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from tools.rag.embedding import embed_model
from utils.config_handler import chroma_conf, rag_conf
from utils.file_handler import (
    get_bytes_md5_hex,
    get_file_type,
    listdir_with_allowed_type,
    parse_document,
)
from utils.logger_handler import logger
from utils.path_tool import get_abs_path

# 批量写入：兼容 DashScope 单批 10 条限制（本地 BGE 也可用）
EMBEDDING_BATCH_SIZE = 10


class VectorStoreService:
    def __init__(self):
        self.persist_directory = get_abs_path(chroma_conf["persist_directory"])
        os.makedirs(self.persist_directory, exist_ok=True)

        self.vector_store = Chroma(
            collection_name=chroma_conf["collection_name"],
            embedding_function=embed_model,
            persist_directory=self.persist_directory,
        )

        # 按文件类型缓存的切片器：不同类型使用 config/chroma.yml 中各自的参数
        self._splitters: dict[str, RecursiveCharacterTextSplitter] = {}

    # ===================== 切片器 =====================
    def _get_splitter(self, file_type: str) -> RecursiveCharacterTextSplitter:
        """按文件类型返回切片器；同一类型只创建一次（惰性缓存）。"""
        chunking_conf = chroma_conf["chunking"]
        if file_type not in chunking_conf:
            # 未在 YAML 中配置的类型回退到 txt 的切片参数
            file_type = "txt"

        if file_type not in self._splitters:
            chunk_conf = chunking_conf[file_type]
            self._splitters[file_type] = RecursiveCharacterTextSplitter(
                chunk_size=chunk_conf["chunk_size"],
                chunk_overlap=chunk_conf["chunk_overlap"],
                separators=chunk_conf["separators"],
                length_function=len,
            )
        return self._splitters[file_type]

    def split_text(self, data: str, file_type: str) -> list[str]:
        """按文件类型切片；短文本整段入库，避免被切得过碎。"""
        if len(data) <= int(chroma_conf["max_split_char_number"]):
            return [data]
        return self._get_splitter(file_type).split_text(data)

    # ===================== 检索器 =====================
    def get_retriever(self, k: int = None):
        """纯向量检索器（语义检索）。"""
        return self.vector_store.as_retriever(
            search_kwargs={"k": int(k or rag_conf["retrieval_k"])}
        )

    # ===================== md5 去重记录 =====================
    @property
    def md5_store_path(self) -> str:
        return get_abs_path(chroma_conf["md5_hex_store"])

    def _read_md5_records(self) -> list[tuple[str, str]]:
        """读取 md5 记录，返回 [(md5, 来源文件), ...]；兼容旧格式（只有 md5）。"""
        if not os.path.exists(self.md5_store_path):
            return []
        records = []
        with open(self.md5_store_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if "\t" in line:
                    md5_str, source = line.split("\t", 1)
                else:
                    md5_str, source = line, ""
                records.append((md5_str, source))
        return records

    def _write_md5_records(self, records: list[tuple[str, str]]):
        os.makedirs(os.path.dirname(self.md5_store_path), exist_ok=True)
        with open(self.md5_store_path, "w", encoding="utf-8") as f:
            for md5_str, source in records:
                f.write(f"{md5_str}\t{source}\n" if source else f"{md5_str}\n")

    def check_md5(self, md5_str: str, source: str = "") -> bool:
        """同一来源下内容是否已处理过。旧格式记录没有来源，按全局去重处理。"""
        for old_md5, old_source in self._read_md5_records():
            if old_md5 == md5_str and (not old_source or old_source == source):
                return True
        return False

    def save_md5(self, md5_str: str, source: str = ""):
        """记录 md5 与来源；同一来源的旧记录会被覆盖。"""
        records = [
            (old_md5, old_source)
            for old_md5, old_source in self._read_md5_records()
            if old_source != source
        ]
        records.append((md5_str, source))
        self._write_md5_records(records)

    # ===================== 入库 =====================
    def _add_texts_in_batches(self, texts: list[str], metadatas: list[dict], ids: list[str]):
        """分批写入向量库；任一批失败会回滚本文件已写入的新分块。"""
        written_ids: list[str] = []
        try:
            for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
                end = start + EMBEDDING_BATCH_SIZE
                batch_ids = ids[start:end]
                self.vector_store.add_texts(
                    texts[start:end],
                    metadatas=metadatas[start:end],
                    ids=batch_ids,
                )
                written_ids.extend(batch_ids)
                logger.info(f"[加载知识库]已写入 {end if end < len(texts) else len(texts)}/{len(texts)} 个分块")
        except Exception:
            # 新内容没有完整写入：删掉已写的部分，旧分块仍然保留，下次可安全重试
            if written_ids:
                self.vector_store.delete(ids=written_ids)
            raise

    def load_document(self) -> None:
        """从 data 目录读取允许类型的文件，解析、切片并写入向量库。"""
        data_path = get_abs_path(chroma_conf["data_path"])
        allowed_files_path = listdir_with_allowed_type(data_path, chroma_conf["allow_file_types"])

        if not allowed_files_path:
            logger.warning(f"[加载知识库]{data_path} 下没有可加载的文档")
            return

        for path in allowed_files_path:
            filename = os.path.basename(path)
            try:
                with open(path, "rb") as f:
                    content = f.read()

                md5_hex = get_bytes_md5_hex(content)
                if self.check_md5(md5_hex, filename):
                    logger.info(f"[加载知识库]{filename} 内容未变化，跳过")
                    continue

                file_type = get_file_type(filename)
                text = parse_document(content, filename)
                if not text.strip():
                    logger.warning(f"[加载知识库]{filename} 内没有有效文本内容，跳过")
                    continue

                knowledge_chunks = self.split_text(text, file_type)
                if not knowledge_chunks:
                    logger.warning(f"[加载知识库]{filename} 分片后没有有效文本内容，跳过")
                    continue

                metadata = {
                    "source": filename,
                    "file_type": file_type,
                    "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "operator": "客户",
                }

                # 同一来源内容变化：先取旧分块 id，新内容写入成功后再删除（更新替换）
                old_ids = self.vector_store.get(where={"source": filename}).get("ids", [])

                chunk_ids = [uuid.uuid4().hex for _ in knowledge_chunks]
                metadatas = [
                    {**metadata, "chunk_id": chunk_id} for chunk_id in chunk_ids
                ]

                self._add_texts_in_batches(knowledge_chunks, metadatas, chunk_ids)

                if old_ids:
                    self.vector_store.delete(ids=old_ids)

                self.save_md5(md5_hex, filename)

                if old_ids:
                    logger.info(f"[加载知识库]{filename} 内容已更新，旧分块 {len(old_ids)} 个已替换")
                else:
                    logger.info(f"[加载知识库]{filename} 内容加载成功，共 {len(knowledge_chunks)} 个分块")
            except Exception as e:
                logger.error(f"[加载知识库]{filename} 加载失败：{str(e)}", exc_info=True)


if __name__ == '__main__':
    vs = VectorStoreService()
    vs.load_document()

    retriever = vs.get_retriever()
    res = retriever.invoke("迷路")
    for r in res:
        print(r.page_content)
        print("-" * 20)
