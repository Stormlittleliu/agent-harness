# -*- coding: utf-8 -*-
"""工作区：安全路径、文件读取、glob、命令执行与运行窗口日志。"""
from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool

MAX_READ_LINES = 200
MAX_READ_CHARS = 50_000
MAX_OUTPUT_CHARS = 20_000

DENY_COMMANDS = (
    "rm -rf /",
    "sudo",
    "shutdown",
    "reboot",
    "mkfs",
    "dd if=",
    "format ",
    "del /f /s /q c:\\",
    "rd /s /q c:\\",
)


class Workspace:
    def __init__(self, root: Path | str, log_dir: Path | str | None = None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.log_dir = Path(log_dir).resolve() if log_dir else self.root / ".run_window"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def safe_path(self, path: str) -> Path:
        target = (self.root / path).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError(f"路径越界：{path}")
        return target

    def read_file(self, path: str, limit: int = MAX_READ_LINES) -> str:
        try:
            target = self.safe_path(path)
            text = target.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            limit = max(1, min(int(limit or MAX_READ_LINES), MAX_READ_LINES))
            shown = lines[:limit]
            body = "\n".join(f"{index:4d} | {line}" for index, line in enumerate(shown, 1))
            if len(lines) > limit:
                body += f"\n... ({len(lines) - limit} more lines)"
            return body[:MAX_READ_CHARS]
        except Exception as exc:  # noqa: BLE001
            return f"Error: {type(exc).__name__}: {exc}"

    def glob(self, pattern: str) -> str:
        try:
            matches = []
            for path in sorted(self.root.glob(pattern)):
                resolved = path.resolve()
                if resolved.is_relative_to(self.root):
                    matches.append(str(resolved.relative_to(self.root)).replace("\\", "/"))
            return "\n".join(matches[:200]) if matches else "(no matches)"
        except Exception as exc:  # noqa: BLE001
            return f"Error: {type(exc).__name__}: {exc}"

    def run_command(self, command: str, timeout: int = 30) -> str:
        lowered = command.lower()
        for pattern in DENY_COMMANDS:
            if pattern in lowered:
                return json.dumps({
                    "error": f"命令被拒绝：包含危险模式 {pattern!r}",
                    "command": command,
                }, ensure_ascii=False)

        timeout = max(1, min(int(timeout or 30), 120))
        log_path = self.log_dir / (
            f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}.log"
        )
        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=self.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            output = (completed.stdout + completed.stderr).strip()
            truncated = len(output) > MAX_OUTPUT_CHARS
            output = output[:MAX_OUTPUT_CHARS] if output else "(no output)"
            payload = {
                "command": command,
                "exit_code": completed.returncode,
                "output": output,
                "truncated": truncated,
                "log_path": str(log_path),
            }
        except subprocess.TimeoutExpired:
            payload = {
                "command": command,
                "exit_code": None,
                "output": f"Error: Timeout ({timeout}s)",
                "truncated": False,
                "log_path": str(log_path),
            }
        log_path.write_text(
            f"$ {command}\n\nexit={payload['exit_code']}\n\n{payload['output']}\n",
            encoding="utf-8",
        )
        return json.dumps(payload, ensure_ascii=False)


def build_workspace_tools(workspace: Workspace):
    @tool("read_file", description="读取工作区内的文件，返回带行号的内容。")
    def read_file(path: str, limit: int = MAX_READ_LINES) -> str:
        return workspace.read_file(path, limit)

    @tool("glob", description="在工作区内按 glob 查找文件，例如 **/*.py。")
    def glob(pattern: str) -> str:
        return workspace.glob(pattern)

    @tool("run_command", description="在工作区执行 shell 命令，输出会写入运行窗口日志。")
    def run_command(command: str, timeout: int = 30) -> str:
        return workspace.run_command(command, timeout)

    return [read_file, glob, run_command]
