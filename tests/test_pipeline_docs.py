# -*- coding: utf-8 -*-
"""中间件中文说明：策略文档要与注册表一一对应，UI 才不会出现英文裸类名。"""
import pytest

from core.agent.contracts import Scenario
from core.agent.pipeline import (
    LAYERS,
    POLICY_DOCS,
    SLOTS,
    available_policies,
    describe_chain,
    describe_pipeline,
)


def _has_chinese(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in str(text or ""))


def test_every_policy_has_chinese_docs():
    missing = [name for name in available_policies() if name not in POLICY_DOCS]
    assert not missing, f"缺中文说明的策略：{missing}"


@pytest.mark.parametrize("name", available_policies())
def test_docs_are_chinese_and_layered(name):
    doc = POLICY_DOCS[name]
    assert _has_chinese(doc.label), doc
    assert _has_chinese(doc.desc), doc
    assert doc.layer in LAYERS, doc


def test_docs_cover_every_slot():
    """POLICY_DOCS 里有、但没有 slot 的策略会被装配忽略，属于写错名字。"""
    extra = [name for name in POLICY_DOCS if name not in SLOTS]
    assert not extra, f"文档里的策略没有 slot：{extra}"


def _scenario(**kwargs):
    return Scenario(
        name="doc_demo",
        description="文档测试场景",
        system_prompt="你是助手。",
        model=None,
        tools=[],
        **kwargs,
    )


def test_describe_chain_matches_pipeline_order():
    scenario = _scenario()
    names = describe_pipeline(scenario)
    chain = describe_chain(scenario)
    assert [item["name"] for item in chain] == names
    assert [item["order"] for item in chain] == list(range(1, len(names) + 1))


def test_chain_labels_are_chinese():
    scenario = _scenario(pii_types=["email"])
    chain = describe_chain(scenario)
    for item in chain:
        assert _has_chinese(item["label"]), item
        assert item["layer"] in LAYERS, item
    pii = next(item for item in chain if item["name"] == "pii:email")
    assert "email" in pii["label"]


def test_custom_middleware_keeps_class_name():
    class MyMiddleware:
        pass

    scenario = _scenario(middleware=[MyMiddleware()])
    item = next(item for item in describe_chain(scenario) if item["policy"] == "custom")
    assert item["label"] == "MyMiddleware"
    assert item["desc"] == ""  # 具体说明由 UI 按类名补，避免这里瞎写
    assert item["layer"] == "自定义"
