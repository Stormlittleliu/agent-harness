# -*- coding: utf-8 -*-
"""Agent 回答的 LLM-as-judge（可选，--judge 时启用）。

与 KnowledgeBase 项目的 eval_rag_judge.py 同一套思路：
- 同义改写算覆盖；
- 期望要点里的“A 或 B”覆盖任一即可；
- 应拒答时只看是否明确说明资料不足且不编造。
"""
import json
import re
import sys
from pathlib import Path

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model.factory import chat_model  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

JUDGE_PROMPT = """你是严格的 Agent 评测员。只依据【期望要点】判断【模型回答】，不要使用外部知识。

【问题】
{question}

【期望要点】
{points}

【是否应拒答】
{should_refuse}

【实际调用工具】
{tools}

【模型回答】
{answer}

请输出严格 JSON：
{{
  "covered": ["已覆盖的要点"],
  "missing": ["未覆盖的要点"],
  "coverage": 0.0,
  "refusal_correct": false,
  "verdict": "pass|partial|fail",
  "reason": "一句话说明"
}}

规则：
1. 允许同义改写，只要语义等价就算覆盖。
2. 数字、单位、否定条件必须一致。
3. 期望要点中出现“A 或 B”时，回答覆盖其中任意一个即可。
4. 如果【是否应拒答】为“是”：回答明确说明资料中没有相关信息且没有编造，则 refusal_correct=true、coverage=1、verdict=pass；
   如果补充了资料之外的具体信息，则 refusal_correct=false、verdict=fail。
5. 工具调用只作参考，不单独判分。
6. 只输出 JSON，不要 Markdown 代码块。"""


def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no json object found")
    return json.loads(text[start:end + 1])


def build_judge():
    prompt = ChatPromptTemplate.from_template(JUDGE_PROMPT)
    return prompt | chat_model | StrOutputParser()


def judge_answer(chain, question, expected_points, should_refuse, tool_names, answer):
    try:
        raw = chain.invoke({
            "question": question,
            "points": "\n".join(f"- {item}" for item in expected_points) or "（无）",
            "should_refuse": "是" if should_refuse else "否",
            "tools": ", ".join(tool_names) or "（无）",
            "answer": answer,
        })
        return _parse_json(raw)
    except Exception as exc:  # noqa: BLE001
        return {
            "covered": [],
            "missing": expected_points,
            "coverage": 0.0,
            "refusal_correct": False,
            "verdict": "fail",
            "reason": f"judge error: {exc}",
        }
