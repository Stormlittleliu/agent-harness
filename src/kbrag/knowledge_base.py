"""知识库：md5 去重记录 + 按文档类型切分 + 写入向量库。"""
import hashlib
import os
import uuid
from datetime import datetime

from langchain_text_splitters import RecursiveCharacterTextSplitter

from kbrag import config
from kbrag.vector_store import VectorStoreService

# text-embedding-v4 的批量上限是 10：一次 add_texts 的条数不能超过该值
EMBEDDING_BATCH_SIZE = 10


def _read_md5_records():
    """读取 md5.text，返回 [(md5, 来源文件), ...]。

    兼容旧格式：只有 md5 的行，来源按空字符串处理。
    """
    if not os.path.exists(config.md5_path):
        return []
    records = []
    with open(config.md5_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()  # 处理字符串前后的空格和回车
            if not line:
                continue
            if "\t" in line:
                md5_str, source = line.split("\t", 1)
            else:
                md5_str, source = line, ""
            records.append((md5_str, source))
    return records


def _write_md5_records(records):
    """把 [(md5, 来源文件), ...] 写回 md5.text。"""
    parent = os.path.dirname(config.md5_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(config.md5_path, "w", encoding="utf-8") as f:
        for md5_str, source in records:
            f.write(f"{md5_str}\t{source}\n" if source else f"{md5_str}\n")


def check_md5(md5_str: str, source: str = ""):
    """检查同一文件是否已经处理过相同内容
            return False未处理，True已处理
    """
    for old_md5, old_source in _read_md5_records():
        # 旧格式记录没有来源文件名，仍按全局去重处理
        if old_md5 == md5_str and (not old_source or old_source == source):
            return True  # 已处理过
    return False


def save_md5(md5_str: str, source: str = ""):
    """记录 md5 和来源文件；同一来源的旧记录会被覆盖"""
    records = [(old_md5, old_source) for old_md5, old_source in _read_md5_records()
               if old_source != source]
    records.append((md5_str, source))
    _write_md5_records(records)


def remove_md5_by_source(source: str):
    """删除指定来源的去重记录；删除文档后应同步调用，避免无法重新上传"""
    records = [(md5_str, old_source) for md5_str, old_source in _read_md5_records()
               if old_source != source]
    _write_md5_records(records)


def clear_md5():
    """清空全部去重记录"""
    _write_md5_records([])


def get_string_md5(input_str: str, encoding="utf-8"):
    """将出传入的字符串转换为md5字符串"""

    # 将字符串转换为bytes字节数组
    str_bytes = input_str.encode(encoding=encoding)

    # 创建md5 对象
    md5_obj = hashlib.md5()  # 得到md5对象
    md5_obj.update(str_bytes)  # 更新内容（传入即将要转换的字节数组）
    md5_hex = md5_obj.hexdigest()  # 得到md5的十六进制字符串

    return md5_hex


class KnowledgeBaseService(object):
    def __init__(self):
        # 如果文件夹不存在则创建，如果存在则跳过
        os.makedirs(config.persist_directory, exist_ok=True)

        # 向量库统一由 VectorStoreService 创建，避免项目里出现多个 Chroma 实例
        self.vector_service = VectorStoreService()
        self.chroma = self.vector_service.vector_store

        # 按文件类型缓存的切片器：不同类型使用 config/chroma.yml 中各自的参数
        self._splitters: dict[str, RecursiveCharacterTextSplitter] = {}

    def _get_splitter(self, file_type: str) -> RecursiveCharacterTextSplitter:
        """按文件类型返回切片器；同一类型只创建一次（惰性缓存）。"""
        if file_type not in config.chunking:
            # 未在 YAML 中配置的类型回退到 txt 的切片参数
            file_type = "txt"

        if file_type not in self._splitters:
            chunk_conf = config.chunking[file_type]
            self._splitters[file_type] = RecursiveCharacterTextSplitter(
                chunk_size=chunk_conf["chunk_size"],  # 分割后的文本段最大长度
                chunk_overlap=chunk_conf["chunk_overlap"],  # 连续文本段之间的字符重叠数量
                separators=chunk_conf["separators"],  # 自然段落划分的符号
                length_function=len,  # 使用python自带的len函数做长度统计的依赖
            )
        return self._splitters[file_type]

    def upload_by_str(self, data: str, filename, file_type: str = None):
        """将传入的字符串，进行向量化，存入向量数据库中

        同一文件名内容未变化时跳过；内容变化时用新分块替换旧分块。
        file_type 缺省时从文件名后缀推断，不同文件类型使用不同的切片参数。
        """
        if not data or not data.strip():
            return "[Error] 内容为空，未写入知识库"

        # 只保留文件名，避免把路径写进 source 元数据；同时去掉制表符/换行，防止 md5 记录串行
        filename = os.path.basename(str(filename).replace("\\", "/"))
        filename = filename.replace("\t", "_").replace("\r", "_").replace("\n", "_") or "unknown"

        # 文件类型：优先使用调用方传入的值，否则从文件名后缀推断
        if not file_type:
            file_type = os.path.splitext(filename)[1].lower().lstrip(".")
        if file_type not in config.chunking:
            file_type = "txt"  # 未知类型按 txt 处理，保证旧调用方式不受影响

        # 先得到出传入的字符串的md5值
        md5_hex = get_string_md5(data)
        if check_md5(md5_hex, filename):
            return "[Repeat] 内容已存在知识库"
        if len(data) > config.max_split_char_number:
            # 按文件类型选择切片器（txt/pdf/docx/md 的参数可以不同）
            knowledge_chunks: list[str] = self._get_splitter(file_type).split_text(data)  # 类型统一，均用列表套字符串
        else:
            knowledge_chunks = [data]

        metadata = {
            "source": filename,
            "file_type": file_type,
            # 2026-3-8 15:43:30
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "operator": "客户",
        }

        # 同一来源更新内容时，先取出旧分块 id，新内容写入成功后再删除，避免更新失败丢数据
        old_ids = self.chroma.get(where={"source": filename}).get("ids", [])

        # 为每个分块生成独立 id：
        # 1. 写入时显式传 ids，Chroma 主键由我们控制；
        # 2. chunk_id 同时写进元数据，供混合检索按 id 融合去重（EnsembleRetriever 的 id_key）
        chunk_ids = [uuid.uuid4().hex for _ in knowledge_chunks]
        metadatas = [{**metadata, "chunk_id": chunk_id} for chunk_id in chunk_ids]

        # 分批写入：text-embedding-v4 单次批量上限为 10；
        # 任一批失败时回滚本文件已写入的新分块，旧分块与 md5 记录保持不变，下次可安全重试。
        written_ids = []
        try:
            for start in range(0, len(knowledge_chunks), EMBEDDING_BATCH_SIZE):
                end = start + EMBEDDING_BATCH_SIZE
                batch_ids = chunk_ids[start:end]
                self.chroma.add_texts(  # 内容加载到向量库中
                    # iterable-> list \tuple
                    knowledge_chunks[start:end],
                    # 注意:langchain-chroma 的参数名是 metadatas(复数);
                    # 写成 metadata= 在旧版是笔误、在新版(1.x)会被静默忽略导致元数据不入库
                    metadatas=metadatas[start:end],
                    ids=batch_ids,
                )
                written_ids.extend(batch_ids)
        except Exception:
            if written_ids:
                self.chroma.delete(ids=written_ids)
            raise

        if old_ids:
            self.chroma.delete(ids=old_ids)
        save_md5(md5_hex, filename)
        if old_ids:
            return "[Success] 内容已更新，旧数据已替换"
        return "[Success] 内容已经成功载入向量库"

    def list_chunks(self):
        """返回向量库中的全部分块，供管理页面查看"""
        data = self.chroma.get(include=["metadatas", "documents"])
        chunks = []
        for chunk_id, metadata, document in zip(
            data.get("ids", []),
            data.get("metadatas", []),
            data.get("documents", []),
        ):
            metadata = metadata or {}
            content = document or ""
            chunks.append({
                "id": chunk_id,
                "source": metadata.get("source") or "(未知来源)",
                # 旧数据没有 file_type 字段，返回空串由页面显示为“未知”
                "file_type": metadata.get("file_type") or "",
                "create_time": metadata.get("create_time") or "",
                "operator": metadata.get("operator") or "",
                "content": content,
                "length": len(content),
            })
        return chunks

    def count_md5_records(self):
        """返回当前去重记录数量"""
        return len(_read_md5_records())

    def delete_by_source(self, source: str):
        """删除指定来源的全部分块，并移除对应的去重记录

        返回删除的分块数量。移除去重记录后，同一文件可以重新上传。
        """
        data = self.chroma.get(include=["metadatas"])
        ids = [
            chunk_id
            for chunk_id, metadata in zip(data.get("ids", []), data.get("metadatas", []))
            if ((metadata or {}).get("source") or "(未知来源)") == source
        ]
        if ids:
            self.chroma.delete(ids=ids)
        remove_md5_by_source(source)
        return len(ids)

    def clear_all(self):
        """清空向量库全部分块和去重记录，返回删除的分块数量"""
        ids = self.chroma.get().get("ids", [])
        if ids:
            self.chroma.delete(ids=ids)
        clear_md5()
        return len(ids)


if __name__ == "__main__":
    # 简单自测：只演示 md5 计算，不写入向量库
    print(get_string_md5("流星"))
