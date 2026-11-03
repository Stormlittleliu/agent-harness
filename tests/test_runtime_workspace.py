# -*- coding: utf-8 -*-
import json

from core.runtime.workspace import Workspace, build_workspace_tools


def _payload(result: str) -> dict:
    return json.loads(result)


def test_read_glob_and_run(tmp_path):
    workspace = Workspace(tmp_path, tmp_path / "logs")
    (tmp_path / "README.md").write_text("Demo Workspace\n", encoding="utf-8")

    assert "Demo Workspace" in workspace.read_file("README.md")
    assert workspace.glob("*.md") == "README.md"

    result = workspace.run_command("echo hello")
    assert '"output": "hello"' in result
    assert list((tmp_path / "logs").glob("run_*.log"))


def test_dangerous_command_is_rejected(tmp_path):
    workspace = Workspace(tmp_path)
    result = workspace.run_command("rm -rf /")
    assert "命令被拒绝" in result


def test_write_edit_and_overwrite_guard(tmp_path):
    workspace = Workspace(tmp_path)

    created = _payload(workspace.write_file("pkg/utils.py", "def add(a, b):\n    return a + b\n"))
    assert created["ok"] is True
    assert created["created"] is True
    assert (tmp_path / "pkg" / "utils.py").exists()

    blocked = _payload(workspace.write_file("pkg/utils.py", "x"))
    assert blocked["ok"] is False
    assert "edit_file" in blocked["error"]

    overwritten = _payload(
        workspace.write_file("pkg/utils.py", "def add(a, b):\n    return a + b\n", overwrite=True)
    )
    assert overwritten["ok"] is True
    assert overwritten["created"] is False

    edited = _payload(workspace.edit_file("pkg/utils.py", "return a + b", "return a - b"))
    assert edited["ok"] is True
    assert edited["replacements"] == 1
    assert "return a - b" in (tmp_path / "pkg" / "utils.py").read_text(encoding="utf-8")

    missing = _payload(workspace.edit_file("pkg/utils.py", "not-there", "x"))
    assert missing["ok"] is False


def test_edit_requires_unique_match(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.write_file("dup.txt", "x\nx\n")
    ambiguous = _payload(workspace.edit_file("dup.txt", "x", "y"))
    assert ambiguous["ok"] is False
    assert "2" in ambiguous["error"]

    all_replaced = _payload(workspace.edit_file("dup.txt", "x", "y", replace_all=True))
    assert all_replaced["ok"] is True
    assert all_replaced["replacements"] == 2


def test_grep_searches_text_files(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.write_file("src/a.py", "def hello():\n    return 1\n")
    workspace.write_file("src/b.txt", "hello world\n")

    matches = workspace.grep("hello", path="src", file_glob="*.py")
    assert "src/a.py:1: def hello():" in matches
    assert "b.txt" not in matches

    case_insensitive = workspace.grep("HELLO", path="src", ignore_case=True)
    assert "src/b.txt" in case_insensitive
    assert workspace.grep("zzz") == "(no matches)"


def test_write_rejects_escape_and_protected_dirs(tmp_path):
    workspace = Workspace(tmp_path)
    escaped = _payload(workspace.write_file("../outside.txt", "x"))
    assert escaped["ok"] is False
    assert "路径越界" in escaped["error"]

    protected = _payload(workspace.write_file(".git/config", "x"))
    assert protected["ok"] is False
    assert "受保护" in protected["error"]


def test_workspace_tool_suite(tmp_path):
    tools = {tool.name for tool in build_workspace_tools(Workspace(tmp_path))}
    assert {
        "read_file",
        "write_file",
        "edit_file",
        "glob",
        "grep",
        "run_command",
    } <= tools
