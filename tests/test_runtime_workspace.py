# -*- coding: utf-8 -*-
from core.runtime.workspace import Workspace


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
