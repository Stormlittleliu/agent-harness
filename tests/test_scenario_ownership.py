# -*- coding: utf-8 -*-
"""场景归属：spec-owned / code-owned 的守卫。

这些用例不调用模型，全部在 tmp_path 上跑。
"""
import json
from pathlib import Path

import pytest

from core.scenarios.ownership import (
    OWNER_CODE,
    OWNER_SPEC,
    OwnershipError,
    ensure_spec_editable,
    eject,
    load_state,
    save_state,
    scenario_code_hash,
    state_path,
    status,
    ScenarioState,
)

NAME = "demo_scene"


def _make_scene(tmp_path: Path, source: str = "SPEC = 1\n") -> tuple[Path, Path]:
    code_root = tmp_path / "scenarios"
    scene_dir = code_root / NAME
    scene_dir.mkdir(parents=True)
    (scene_dir / "scenario.py").write_text(source, encoding="utf-8")
    spec_root = tmp_path / "specs"
    (spec_root / NAME).mkdir(parents=True)
    return code_root, spec_root


def test_code_hash_tracks_file_content(tmp_path):
    code_root, _ = _make_scene(tmp_path)
    first = scenario_code_hash(NAME, code_root)
    assert first.startswith("sha256:")
    (code_root / NAME / "scenario.py").write_text("SPEC = 2\n", encoding="utf-8")
    assert scenario_code_hash(NAME, code_root) != first


def test_code_hash_ignores_pycache(tmp_path):
    code_root, _ = _make_scene(tmp_path)
    baseline = scenario_code_hash(NAME, code_root)
    cache = code_root / NAME / "__pycache__"
    cache.mkdir()
    (cache / "scenario.cpython-310.pyc").write_bytes(b"x")
    assert scenario_code_hash(NAME, code_root) == baseline


def test_ensure_bootstraps_state_on_first_call(tmp_path):
    code_root, spec_root = _make_scene(tmp_path)
    assert load_state(NAME, spec_root) is None
    state = ensure_spec_editable(NAME, root=spec_root, code_root=code_root)
    assert state.owner == OWNER_SPEC
    assert state.code_hash == scenario_code_hash(NAME, code_root)
    assert state_path(NAME, spec_root).is_file()


def test_ensure_fails_when_code_drifted(tmp_path):
    code_root, spec_root = _make_scene(tmp_path)
    ensure_spec_editable(NAME, root=spec_root, code_root=code_root)
    (code_root / NAME / "scenario.py").write_text("SPEC = 99\n", encoding="utf-8")

    with pytest.raises(OwnershipError) as excinfo:
        ensure_spec_editable(NAME, root=spec_root, code_root=code_root)
    message = str(excinfo.value)
    assert "分叉" in message
    assert f"python -m core.scenarios.eject {NAME}" in message


def test_ensure_is_stable_when_only_spec_changed(tmp_path):
    code_root, spec_root = _make_scene(tmp_path)
    ensure_spec_editable(NAME, root=spec_root, code_root=code_root)
    (spec_root / NAME / "v1.json").write_text("{}", encoding="utf-8")
    assert ensure_spec_editable(NAME, root=spec_root, code_root=code_root).owner == OWNER_SPEC


def test_eject_switches_owner_and_blocks_editing(tmp_path):
    code_root, spec_root = _make_scene(tmp_path)
    ensure_spec_editable(NAME, root=spec_root, code_root=code_root)
    state = eject(NAME, "改用自定义块", root=spec_root, code_root=code_root)

    assert state.owner == OWNER_CODE
    assert state.reason == "改用自定义块"
    assert state.ejected_at
    assert load_state(NAME, spec_root).owner == OWNER_CODE
    with pytest.raises(OwnershipError) as excinfo:
        ensure_spec_editable(NAME, root=spec_root, code_root=code_root)
    assert "code-owned" in str(excinfo.value)


def test_eject_then_code_change_is_allowed(tmp_path):
    code_root, spec_root = _make_scene(tmp_path)
    ensure_spec_editable(NAME, root=spec_root, code_root=code_root)
    eject(NAME, root=spec_root, code_root=code_root)
    (code_root / NAME / "scenario.py").write_text("SPEC = 3\n", encoding="utf-8")
    # code-owned 下不再校验 hash，改动是预期行为
    with pytest.raises(OwnershipError):
        ensure_spec_editable(NAME, root=spec_root, code_root=code_root)


def test_status_reports_editable_and_drift(tmp_path):
    code_root, spec_root = _make_scene(tmp_path)
    ensure_spec_editable(NAME, root=spec_root, code_root=code_root)
    assert status(NAME, root=spec_root, code_root=code_root)["editable"] is True

    (code_root / NAME / "scenario.py").write_text("SPEC = 42\n", encoding="utf-8")
    drifted = status(NAME, root=spec_root, code_root=code_root)
    assert drifted["hash_match"] is False
    assert drifted["editable"] is False
    assert "eject" in drifted["next_action"]

    eject(NAME, root=spec_root, code_root=code_root)
    ejected = status(NAME, root=spec_root, code_root=code_root)
    assert ejected["owner"] == OWNER_CODE
    assert ejected["editable"] is False
    assert "只读" in ejected["next_action"]


def test_state_json_is_plain_json(tmp_path):
    code_root, spec_root = _make_scene(tmp_path)
    save_state(
        ScenarioState(name=NAME, owner=OWNER_CODE, code_hash="sha256:abc", reason="test"),
        spec_root,
    )
    payload = json.loads(state_path(NAME, spec_root).read_text(encoding="utf-8"))
    assert payload["owner"] == OWNER_CODE
    assert payload["reason"] == "test"
    assert set(payload) == {
        "name",
        "owner",
        "code_hash",
        "spec_file",
        "ejected_at",
        "reason",
    }
