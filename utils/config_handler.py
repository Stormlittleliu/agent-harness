"""YAML 配置加载：四个配置文件统一在这里读取。

与基础项目一致：
- 使用 yaml.safe_load（不执行任意 Python 对象）
- 文件缺失 / 格式错误时给出中文提示，便于排查
"""
import yaml

from utils.path_tool import get_abs_path


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


def load_prompts_config(config_path: str = get_abs_path("config/prompts.yml"), encoding: str = "utf-8"):
    return _load_yml(config_path, "config/prompts.yml", encoding)


def load_agent_config(config_path: str = get_abs_path("config/agent.yml"), encoding: str = "utf-8"):
    return _load_yml(config_path, "config/agent.yml", encoding)


rag_conf = load_rag_config()
chroma_conf = load_chroma_config()
agent_conf = load_agent_config()
prompts_conf = load_prompts_config()


if __name__ == '__main__':
    print("chat_model_name:", rag_conf["chat_model_name"])
    print("retrieval_mode:", rag_conf["retrieval_mode"])
    print("max_model_calls:", agent_conf["max_model_calls"])
    print("prompt keys:", list(prompts_conf.keys()))
