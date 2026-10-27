"""检索器工厂：纯向量检索、关键词 BM25 检索、混合检索（向量 + 关键词兜底）。

设计说明（学习重点）：
1. 纯向量检索：直接复用 VectorStoreService 的 Chroma 检索器，语义相似即可命中，
   但型号、数字、专有名词等“字面精确匹配”场景容易漏召回；
2. 关键词 BM25 检索：经典的词频-逆文档频率打分，负责“字面兜底”；
3. 混合检索：把两路结果做加权融合（Reciprocal Rank Fusion），兼顾语义与字面匹配。

BM25 的语料在每次检索时从 Chroma 实时读取，保证新上传的文档立即能被关键词检索到。
"""
import hashlib
import logging
import math
from typing import Callable

from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.callbacks import (
    AsyncCallbackManagerForRetrieverRun,
    CallbackManagerForRetrieverRun,
)
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnableConfig

from kbrag import config
from kbrag.vector_store import VectorStoreService

logger = logging.getLogger(__name__)


# ===================== 分词器 =====================
def _tokenize_with_jieba(text: str) -> list[str]:
    """使用 jieba 做中文分词，并过滤空白词。"""
    import jieba  # 延迟导入：未安装时由 get_tokenizer 统一降级

    return [word.strip() for word in jieba.lcut(text) if word.strip()]


def _tokenize_bigram(text: str) -> list[str]:
    """字符二元组分词：中文检索的无依赖降级方案。

    例如“扫地机器人” -> ["扫地", "地机", "机器", "器人"]。
    """
    compact = "".join(text.split()).lower()
    if not compact:
        return []
    if len(compact) == 1:
        return [compact]
    return [compact[i:i + 2] for i in range(len(compact) - 1)]


def _tokenize_char(text: str) -> list[str]:
    """按单字分词：最粗糙的兜底方案。"""
    return list("".join(text.split()).lower())


def get_tokenizer() -> Callable[[str], list[str]]:
    """按配置返回分词函数；jieba 未安装时自动降级为 bigram 并输出警告。"""
    name = config.bm25_tokenizer
    if name == "jieba":
        try:
            import jieba  # noqa: F401  只做可用性检查
        except ImportError:
            logger.warning("[BM25]未安装 jieba，自动降级为 bigram 分词（检索效果略有下降）")
            return _tokenize_bigram
        return _tokenize_with_jieba
    if name == "char":
        return _tokenize_char
    return _tokenize_bigram


def _content_chunk_id(content: str) -> str:
    """内容指纹：为没有 chunk_id 的旧分块生成稳定 id，保证两路检索能对齐去重。"""
    return "content-" + hashlib.md5(content.encode("utf-8")).hexdigest()


# ===================== BM25 关键词检索器 =====================
def _load_chroma_corpus() -> list[Document]:
    """从 Chroma 拉取全部已入库分块，作为 BM25 的检索语料。"""
    data = VectorStoreService().vector_store.get(include=["documents", "metadatas"])
    documents = []
    for chunk_id, content, metadata in zip(
        data.get("ids", []),
        data.get("documents", []),
        data.get("metadatas", []),
    ):
        if not content or not content.strip():
            continue
        metadata = dict(metadata or {})
        # 新数据入库时已把 chunk_id 写进元数据；
        # 旧数据没有该字段，用内容指纹兜底（与向量侧的 ChunkIdRetriever 保持一致）。
        if not metadata.get("chunk_id"):
            metadata["chunk_id"] = _content_chunk_id(content)
        documents.append(Document(page_content=content, metadata=metadata))
    return documents


class KeywordBM25Retriever(BaseRetriever):
    """手写 BM25 关键词检索器（教学实现）。

    BM25 的核心思想：
    - 词频 TF：一个词在文档中出现得越多，文档越相关，但收益会逐渐饱和；
    - 逆文档频率 IDF：越少见的词区分度越高；
    - 文档长度归一化：长文档天然包含更多词，需要做惩罚。

    打分公式：
        score(D, Q) = Σ idf(qi) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * |D| / avgdl))

    语料每次检索时通过 corpus_loader 实时拉取，因此上传新文档后不需要重建索引。
    """

    # pydantic 字段：语料加载函数（必需）、返回条数、分词函数、BM25 调参
    corpus_loader: Callable[[], list[Document]]
    k: int = 4
    tokenize: Callable[[str], list[str]] = _tokenize_bigram
    k1: float = 1.5
    b: float = 0.75

    def _build_index(self):
        """实时构建索引所需的统计量：文档、分词结果、文档频率、文档长度、平均长度。"""
        documents = [doc for doc in self.corpus_loader() if (doc.page_content or "").strip()]
        tokenized = [self.tokenize(doc.page_content) for doc in documents]

        # 文档频率 df：某个词出现在多少个文档里（同一个词在一个文档中只计一次）
        document_frequency: dict[str, int] = {}
        for terms in tokenized:
            for term in set(terms):
                document_frequency[term] = document_frequency.get(term, 0) + 1

        doc_lengths = [len(terms) for terms in tokenized]
        avgdl = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 0.0
        return documents, tokenized, document_frequency, doc_lengths, avgdl

    def _get_relevant_documents(
            self,
            query: str,
            *,
            run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        documents, tokenized, document_frequency, doc_lengths, avgdl = self._build_index()
        if not documents:
            return []

        query_terms = set(self.tokenize(query))
        total_docs = len(documents)

        # IDF：词越稀有，权重越高；+0.5 的平滑避免除零和极端值
        idf = {
            term: math.log((total_docs - df + 0.5) / (df + 0.5) + 1.0)
            for term, df in document_frequency.items()
        }

        scored: list[tuple[float, Document]] = []
        for doc, terms, doc_len in zip(documents, tokenized, doc_lengths):
            # 只统计查询词在当前文档中的词频
            term_frequency: dict[str, int] = {}
            for term in terms:
                if term in query_terms:
                    term_frequency[term] = term_frequency.get(term, 0) + 1
            if not term_frequency:
                continue

            score = 0.0
            for term, tf in term_frequency.items():
                numerator = tf * (self.k1 + 1)
                if avgdl:
                    denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / avgdl)
                else:
                    denominator = tf
                score += idf.get(term, 0.0) * numerator / denominator

            if score > 0:
                scored.append((score, doc))

        # 按得分从高到低取前 k 条
        scored.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in scored[: self.k]]

    async def _aget_relevant_documents(
            self,
            query: str,
            *,
            run_manager: AsyncCallbackManagerForRetrieverRun,
    ) -> list[Document]:
        """异步接口：本检索器没有 IO，直接复用同步实现。"""
        return self._get_relevant_documents(query, run_manager=run_manager)  # type: ignore[arg-type]


# ===================== 混合检索 =====================
class ChunkIdRetriever(BaseRetriever):
    """包装检索器：确保每条结果的元数据里都有 chunk_id。

    EnsembleRetriever 按 id_key 去重时是直接取 doc.metadata["chunk_id"] 的，
    旧数据（改造前入库）没有这个字段会直接 KeyError。
    新数据入库时已经写入 chunk_id；旧数据在这里用内容指纹兜底，
    与 BM25 语料侧的 _content_chunk_id 保持一致，两路结果仍能正确合并。
    """

    inner: BaseRetriever

    def _enrich(self, documents: list[Document]) -> list[Document]:
        for doc in documents:
            if not doc.metadata.get("chunk_id"):
                doc.metadata["chunk_id"] = _content_chunk_id(doc.page_content)
        return documents

    def _get_relevant_documents(
            self,
            query: str,
            *,
            run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        return self._enrich(self.inner.invoke(query))

    async def _aget_relevant_documents(
            self,
            query: str,
            *,
            run_manager: AsyncCallbackManagerForRetrieverRun,
    ) -> list[Document]:
        return self._enrich(await self.inner.ainvoke(query))


class TopKEnsembleRetriever(EnsembleRetriever):
    """带 Top-K 截断的 EnsembleRetriever。

    LangChain 的 EnsembleRetriever 只做加权 RRF 融合，没有 k 参数：
    两个子检索器各返回 4 条时，融合结果最多会有 8 条。
    这里覆写融合方法，把最终结果截断到 k 条，保证和纯向量模式的上下文规模一致。

    注意：EnsembleRetriever 的 invoke/ainvoke 是直接调用 rank_fusion/arank_fusion 的，
    并没有走 _get_relevant_documents，所以这里必须覆写融合方法本身。
    """

    k: int = 4

    def rank_fusion(
            self,
            query: str,
            run_manager: CallbackManagerForRetrieverRun,
            *,
            config: RunnableConfig | None = None,
    ) -> list[Document]:
        documents = super().rank_fusion(query, run_manager, config=config)
        return documents[: self.k]

    async def arank_fusion(
            self,
            query: str,
            run_manager: AsyncCallbackManagerForRetrieverRun,
            *,
            config: RunnableConfig | None = None,
    ) -> list[Document]:
        documents = await super().arank_fusion(query, run_manager, config=config)
        return documents[: self.k]


# ===================== 工厂函数 =====================
def get_vector_retriever() -> BaseRetriever:
    """纯向量检索器（Chroma 语义检索）。"""
    return VectorStoreService().get_retriever()


def get_hybrid_retriever() -> BaseRetriever:
    """混合检索器：向量检索 + BM25 关键词兜底，按配置权重做 RRF 融合。"""
    # 向量侧包一层 ChunkIdRetriever：旧分块没有 chunk_id 时用内容指纹补齐
    vector_retriever = ChunkIdRetriever(inner=get_vector_retriever())
    keyword_retriever = KeywordBM25Retriever(
        corpus_loader=_load_chroma_corpus,
        k=config.retrieval_k,
        tokenize=get_tokenizer(),
    )
    return TopKEnsembleRetriever(
        retrievers=[vector_retriever, keyword_retriever],
        weights=[
            float(config.hybrid_weights["vector"]),
            float(config.hybrid_weights["bm25"]),
        ],
        # 同一分块被两路同时命中时，按 chunk_id 合并去重
        id_key="chunk_id",
        k=config.retrieval_k,
    )


def get_retriever(mode: str = None) -> BaseRetriever:
    """按模式返回检索器；mode 缺省时使用 config/rag.yml 中的默认检索模式。"""
    mode = str(mode or config.retrieval_mode or "vector").lower()
    if mode == "vector":
        return get_vector_retriever()
    if mode == "hybrid":
        return get_hybrid_retriever()
    raise ValueError(f"未知的检索模式：{mode}（可选：vector / hybrid）")
