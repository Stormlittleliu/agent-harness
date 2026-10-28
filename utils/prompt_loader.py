"""提示词加载。

- RAG 总结提示词是能力级配置：`config/rag_prompts.yml`；
- 场景提示词（main/report）由 `scenarios/<name>/config/prompts.yml` 提供，
  由场景层把路径传进来。
"""
from functools import lru_cache

from utils.config_handler import load_prompts_config
from utils.logger_handler import logger
from utils.path_tool import get_abs_path

RAG_PROMPTS_PATH = get_abs_path("config/rag_prompts.yml")


@lru_cache(maxsize=8)
def _load_prompts(config_path: str) -> dict:
    return load_prompts_config(config_path)


def _load_prompt(config_path: str, key: str, description: str) -> str:
    try:
        prompt = _load_prompts(config_path)[key]
    except KeyError as e:
        logger.error(f"[prompt_loader] {config_path} 中缺少 {key} 配置项")
        raise KeyError(f"{config_path} 中缺少 {key} 配置项") from e

    if not isinstance(prompt, str) or not prompt.strip():
        logger.error(f"[prompt_loader] {description}为空或格式错误")
        raise ValueError(f"{config_path} 中的 {key} 必须是非空字符串")
    return prompt


def load_system_prompts(config_path: str) -> str:
    """普通问答场景的系统提示词。"""
    return _load_prompt(config_path, "main_prompt", "系统提示词")


def load_rag_prompts(config_path: str = RAG_PROMPTS_PATH) -> str:
    """RAG 总结提示词（含 {input} / {context} 占位符）。"""
    return _load_prompt(config_path, "rag_summarize_prompt", "RAG 总结提示词")


def load_report_prompts(config_path: str) -> str:
    """报告生成场景的系统提示词。"""
    return _load_prompt(config_path, "report_prompt", "报告生成提示词")


if __name__ == '__main__':
    print(load_rag_prompts())
