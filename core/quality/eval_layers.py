# -*- coding: utf-8 -*-
"""评测分层：模型能力 vs 场景/工具。

这两个词在本仓库里是**判分口径**，不是难度：

- ``model_capability``：只看最终文本/答案，不检查工具调用、不检查环境状态。
  答对就是通过，答错就是失败；单条 case 可以独立跑。
- ``scenario_tool``：要看工具选择/参数、多轮对话或环境终态。最终文本答对
  但工具调错、状态没变，仍然算失败。

``execution`` 描述的是**本仓库当前**能不能跑，不是 benchmark 本身的能力：

- ``native``：已有本项目的 runner / 报告路径；
- ``judge_required``：要 LLM judge，尚未接；
- ``sandbox_required``：要代码执行沙箱，尚未接；
- ``harness_required``：要官方 harness / 环境，本仓库只做了数据适配；
- ``tools_required``：题面需要联网/文件/工具，但适配器没带工具。

所以一个 case 可以是 ``scenario_tool`` + ``harness_required``：它设计上测
场景/工具，但我们现在还跑不了。不要把 ``eval_scope`` 当成“已跑通”。
"""
from __future__ import annotations

MODEL_CAPABILITY = "model_capability"
SCENARIO_TOOL = "scenario_tool"

LAYER_LABELS = {
    MODEL_CAPABILITY: "模型能力",
    SCENARIO_TOOL: "场景/工具",
}

LAYER_DEFS = {
    MODEL_CAPABILITY: "只看最终输出（文本/代码/答案）；不检查工具调用或环境状态。",
    SCENARIO_TOOL: "要看工具选择/参数、多轮对话或环境终态；最终输出对不算通过。",
}

SOURCE_META = {
    "BFCL-v4": {
        "eval_scope": SCENARIO_TOOL,
        "execution": "harness_required",
        "why": "函数选择/参数/无关请求；要有工具 schema 和调用结果。",
    },
    "tau2-bench": {
        "eval_scope": SCENARIO_TOOL,
        "execution": "harness_required",
        "why": "多轮用户模拟 + 数据库终态；文本对但状态不对仍失败。",
    },
    "GAIA": {
        "eval_scope": SCENARIO_TOOL,
        "execution": "tools_required",
        "why": "官方任务要联网/读附件；当前适配器只带题面，没带工具。",
    },
    "SWE-bench": {
        "eval_scope": SCENARIO_TOOL,
        "execution": "harness_required",
        "why": "仓库 + Docker + F2P/P2P；补丁文本对不等于测试过。",
    },
    "WebArena": {
        "eval_scope": SCENARIO_TOOL,
        "execution": "harness_required",
        "why": "自托管站点 + 登录态 + DOM/URL/字符串断言。",
    },
    "OSWorld": {
        "eval_scope": SCENARIO_TOOL,
        "execution": "harness_required",
        "why": "VM + 桌面应用 + 终态 evaluator。",
    },
    "RGB": {
        "eval_scope": MODEL_CAPABILITY,
        "execution": "native",
        "why": "检索召回 / 答案质量；只看最终结果。",
    },
    "MultiHop-RAG": {
        "eval_scope": MODEL_CAPABILITY,
        "execution": "native",
        "why": "多跳检索召回 / 答案；只看最终结果。",
    },
    "CFBench": {
        "eval_scope": MODEL_CAPABILITY,
        "execution": "judge_required",
        "why": "约束是否满足靠 LLM judge，不检查工具或环境。",
    },
    "HumanEval": {
        "eval_scope": MODEL_CAPABILITY,
        "execution": "sandbox_required",
        "why": "函数补全，执行单测；不是场景/工具任务。",
    },
    "MBPP": {
        "eval_scope": MODEL_CAPABILITY,
        "execution": "sandbox_required",
        "why": "函数生成，执行单测；不是场景/工具任务。",
    },
}

DEFAULT_META = {
    "eval_scope": MODEL_CAPABILITY,
    "execution": "unknown",
    "why": "未登记；默认按模型能力处理，接入前先补元数据。",
}


def describe(benchmark: str) -> dict:
    """返回某个 benchmark 的分层元数据；未知源不猜成场景/工具。"""
    meta = dict(DEFAULT_META)
    meta.update(SOURCE_META.get(benchmark, {}))
    meta["benchmark"] = benchmark
    return meta


def label(eval_scope: str) -> str:
    return LAYER_LABELS.get(eval_scope, eval_scope)
