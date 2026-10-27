"""项目配置。

配置分为两部分：
1. 路径类配置（随项目目录变化）直接在这里计算，避免把绝对路径写死；
2. 业务参数（模型、检索、切片、Prompt）放在项目根目录的 config/*.yml，
   调整 Top-K、混合权重、切片参数或提示词时只需要改 YAML。

所有路径都以项目根目录为基准，因此从任意工作目录启动都能找到数据文件。
"""
from pathlib import Path

import yaml
from dotenv import load_dotenv

# src/kbrag/config.py 往上三级是项目根目录（config.py -> kbrag -> src -> 项目根）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 运行时数据统一放在项目根目录的 data/ 下（向量库、去重记录、会话历史、对比记录）
DATA_DIR = PROJECT_ROOT / "data"
# 业务参数配置文件目录
CONFIG_DIR = PROJECT_ROOT / "config"

# 加载项目根目录 .env 文件中的环境变量(如 DASHSCOPE_API_KEY)
load_dotenv(str(PROJECT_ROOT / ".env"))

# 路径配置由项目位置推导，不放进 YAML，避免出现依赖当前工作目录的相对路径
md5_path = str(DATA_DIR / "md5.text")
history_dir = str(DATA_DIR / "chat_history")
compare_history_path = str(DATA_DIR / "compare_history.json")
# Chroma 本地持久化目录
persist_directory = str(DATA_DIR / "chroma_db")


def _load_yml(name: str) -> dict:
    """读取 config/ 下的 YAML 配置；文件缺失或格式错误时给出中文提示。"""
    path = CONFIG_DIR / name
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"配置文件不存在：{path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"配置文件 {path} 格式有误：{exc}") from exc


_rag_conf = _load_yml("rag.yml")
_chroma_conf = _load_yml("chroma.yml")
_prompts_conf = _load_yml("prompts.yml")


# ===================== 模型与检索（config/rag.yml） =====================
embedding_model_name = _rag_conf["embedding_model_name"]
chat_model_name = _rag_conf["chat_model_name"]
# 检索返回的文档数量(top-k)
retrieval_k = int(_rag_conf["retrieval_k"])
# 默认检索模式：vector（纯向量）/ hybrid（向量 + 关键词兜底）
retrieval_mode = str(_rag_conf["retrieval_mode"]).lower()
# 混合检索两类检索器的融合权重
hybrid_weights = _rag_conf["hybrid_weights"]
# 中文关键词分词方式：jieba / bigram / char
bm25_tokenizer = str(_rag_conf["bm25_tokenizer"]).lower()


# ===================== 向量库与切分（config/chroma.yml） =====================
collection_name = _chroma_conf["collection_name"]
# 允许上传的文件类型，统一转小写，页面和解析器共用
allow_file_types = [str(item).lower() for item in _chroma_conf["allow_file_types"]]
max_split_char_number = int(_chroma_conf["max_split_char_number"])
# 按文件类型区分的切片参数：{类型: {chunk_size, chunk_overlap, separators}}
chunking = _chroma_conf["chunking"]

# 兼容旧调用点：以前只有一套切片参数，现在按文件类型查表。
# 这里仍然暴露 txt 的一套参数作为默认值，旧代码和未知文件类型可以继续使用。
_default_chunk_conf = chunking["txt"]
chunk_size = _default_chunk_conf["chunk_size"]
chunk_overlap = _default_chunk_conf["chunk_overlap"]
separators = _default_chunk_conf["separators"]


# ===================== Prompt 模板（config/prompts.yml） =====================
chat_system_template = _prompts_conf["chat_system_template"]
history_system_template = _prompts_conf["history_system_template"]
plain_system_template = _prompts_conf["plain_system_template"]
rag_system_template = _prompts_conf["rag_system_template"]
