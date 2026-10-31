# -*- coding: utf-8 -*-
from core.agent.hooks import HookManager


def test_hook_trigger_stops_on_first_non_none():
    calls = []

    def first(request):
        calls.append("first")
        return None

    def second(request):
        calls.append("second")
        return "blocked"

    manager = HookManager({"PreToolUse": [first, second]})
    assert manager.trigger("PreToolUse", object()) == "blocked"
    assert calls == ["first", "second"]


def test_hook_exception_does_not_break_trigger():
    def broken(_request):
        raise RuntimeError("hook failed")

    manager = HookManager({"PreToolUse": [broken]})
    assert manager.trigger("PreToolUse", object()) is None
