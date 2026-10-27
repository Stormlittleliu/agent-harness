"""提示词加载：模板统一存放在 config/prompts.yml。

对外函数名保持不变，调用方（agent / tools / middleware）无需改动。
"""
from utils.config_handler import prompts_conf
from utils.logger_handler import logger


def _load_prompt(key: str, description: str) -> str:
    try:
        prompt = prompts_conf[key]
    except KeyError as e:
        logger.error(f"[prompt_loader] config/prompts.yml 中缺少 {key} 配置项")
        raise KeyError(f"config/prompts.yml 中缺少 {key} 配置项") from e

    if not isinstance(prompt, str) or not prompt.strip():
        logger.error(f"[prompt_loader] {description}为空或格式错误")
        raise ValueError(f"config/prompts.yml 中的 {key} 必须是非空字符串")
    return prompt


def load_system_prompts():
    """普通问答场景的系统提示词。"""
    return _load_prompt("main_prompt", "系统提示词")


def load_rag_prompts():
    """RAG 总结提示词（含 {input} / {context} 占位符）。"""
    return _load_prompt("rag_summarize_prompt", "RAG 总结提示词")


def load_report_prompts():
    """报告生成场景的系统提示词。"""
    return _load_prompt("report_prompt", "报告生成提示词")


if __name__ == '__main__':
    print(load_report_prompts())
