"""YAML 配置加载。

能力配置（rag/chroma）是全局的；场景配置（agent/prompts）按路径加载，
由 scenarios/<name>/scenario.py 负责传入。
"""
import yaml

from core.utils.path_tool import get_abs_path


def _load_yml(config_path: str, config_name: str, encoding: str = "utf-8"):
    """读取 YAML 文件；失败时抛出带中文说明的异常。"""
    try:
        with open(config_path, "r", encoding=encoding) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"配置文件不存在：{config_path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"配置文件 {config_name} 格式错误：{exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"配置文件 {config_name} 的顶层必须是键值对（dict）")
    return data


def load_rag_config(config_path: str = get_abs_path("config/rag.yml"), encoding: str = "utf-8"):
    return _load_yml(config_path, "config/rag.yml", encoding)


def load_chroma_config(config_path: str = get_abs_path("config/chroma.yml"), encoding: str = "utf-8"):
    return _load_yml(config_path, "config/chroma.yml", encoding)


def load_prompts_config(config_path: str, encoding: str = "utf-8"):
    return _load_yml(config_path, "prompts.yml", encoding)


def load_agent_config(config_path: str, encoding: str = "utf-8"):
    return _load_yml(config_path, "agent.yml", encoding)


rag_conf = load_rag_config()
chroma_conf = load_chroma_config()


if __name__ == '__main__':
    print("chat_model_name:", rag_conf["chat_model_name"])
    print("retrieval_mode:", rag_conf["retrieval_mode"])
    print("collection_name:", chroma_conf["collection_name"])
