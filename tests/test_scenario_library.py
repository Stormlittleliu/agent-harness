# -*- coding: utf-8 -*-
"""场景库：界面唯一的"有哪些场景"来源，以及 spec 接管规则。"""
from core.scenarios import library
from core.scenarios.registry import list_scenarios


def test_every_registered_scenario_has_library_entry():
    """registry 里有、场景库里没元数据的场景，界面就会显示成英文 id。"""
    names = set(list_scenarios())
    entries = {item.name for item in library.entries()}
    assert names <= entries


def test_entries_have_chinese_labels():
    for item in library.entries():
        assert item.label, item
        assert item.label != item.name or item.name.startswith("ui_"), item


def test_router_is_a_scenario_not_a_mode():
    item = library.entry("router")
    assert item is not None
    assert item.is_router
    assert item.kind == "router"
    assert item.title.startswith("🔀")


def test_flow_demo_is_spec_owned_and_editable():
    item = library.entry("flow_demo")
    assert item is not None
    assert item.from_spec is True
    assert item.editable is True
    assert item.owner == "spec"
    assert item.cases == 1


def test_code_scenario_is_marked_readonly():
    """没被 spec 接管的场景仍然标 code（robot_vacuum 还没仿造）。"""
    item = library.entry("robot_vacuum")
    assert item is not None
    assert item.from_spec is False
    assert item.editable is False
    assert item.cases > 0

    coding = library.entry("coding_demo")
    assert coding is not None and coding.supports_runtime is True
    assert coding.cases > 0


def test_default_name_prefers_editable_spec_scenario():
    default = library.default_name()
    assert default in library.names()
    editable = [item for item in library.entries() if item.from_spec and item.editable]
    if editable:
        assert default == editable[0].name


def test_summary_counts_match_entries():
    summary = library.summary()
    entries = library.entries()
    assert summary["total"] == len(entries)
    assert summary["spec"] == sum(1 for item in entries if item.from_spec)
    assert summary["routers"] == sum(1 for item in entries if item.is_router)


def test_spec_takes_over_same_named_code_scenario(monkeypatch):
    """data/specs/<name>/active.json 存在时，同名场景必须由 spec 构建。"""
    from core.scenarios.registry import get_scenario

    monkeypatch.setattr("core.scenarios.registry._spec_names", lambda: ["coding_demo"])
    monkeypatch.setattr(
        "core.scenarios.generic.build_generic_spec_scenario",
        lambda name, root=None: f"spec:{name}",
    )
    assert get_scenario("coding_demo") == "spec:coding_demo"


def test_code_builder_still_used_without_spec(monkeypatch):
    from core.scenarios.registry import get_scenario

    monkeypatch.setattr("core.scenarios.registry._spec_names", lambda: [])
    monkeypatch.setattr("core.scenarios.registry._BUILDERS", {"general": lambda: "code:general"})
    assert get_scenario("general") == "code:general"
