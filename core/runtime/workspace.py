# -*- coding: utf-8 -*-
"""工作区：安全路径、文件读取、glob、命令执行与运行窗口日志。"""
from __future__ import annotations

import json
import re
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool

MAX_READ_LINES = 200
MAX_READ_CHARS = 50_000
MAX_OUTPUT_CHARS = 20_000
MAX_WRITE_CHARS = 200_000
MAX_GREP_FILE_BYTES = 1_000_000
MAX_GREP_RESULTS = 200

# 写操作不进入这些目录；读操作仍允许（例如读 README 或调试）。
DENY_WRITE_PARTS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
}

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


def _error_json(message: str) -> str:
    return json.dumps({"ok": False, "error": message}, ensure_ascii=False)


class Workspace:
    def __init__(self, root: Path | str, log_dir: Path | str | None = None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.log_dir = Path(log_dir).resolve() if log_dir else self.root / ".run_window"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def safe_path(self, path: str, *, for_write: bool = False) -> Path:
        target = (self.root / path).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError(f"路径越界：{path}")
        if for_write:
            relative = target.relative_to(self.root)
            blocked = [part for part in relative.parts if part in DENY_WRITE_PARTS]
            if blocked:
                raise ValueError(f"受保护目录，禁止写入：{blocked[0]}")
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

    def write_file(self, path: str, content: str, overwrite: bool = False) -> str:
        """写入文本文件；默认不覆盖已有文件，避免误删。"""
        try:
            content = str(content or "")
            if len(content) > MAX_WRITE_CHARS:
                return _error_json(f"内容超过上限（{MAX_WRITE_CHARS} 字符）")
            target = self.safe_path(path, for_write=True)
            exists = target.exists()
            if exists and not overwrite:
                return _error_json(
                    f"{path} 已存在；修改请用 edit_file，覆盖请传 overwrite=true"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return json.dumps(
                {
                    "ok": True,
                    "path": path,
                    "chars": len(content),
                    "bytes": len(content.encode("utf-8")),
                    "created": not exists,
                },
                ensure_ascii=False,
            )
        except Exception as exc:  # noqa: BLE001
            return _error_json(f"{type(exc).__name__}: {exc}")

    def edit_file(
        self,
        path: str,
        old_text: str,
        new_text: str,
        replace_all: bool = False,
    ) -> str:
        """精确替换文本；old_text 必须唯一出现，除非 replace_all=True。"""
        try:
            if not old_text:
                return _error_json("old_text 不能为空")
            target = self.safe_path(path, for_write=True)
            if not target.is_file():
                return _error_json(f"文件不存在：{path}")
            text = target.read_text(encoding="utf-8", errors="replace")
            count = text.count(old_text)
            if count == 0:
                return _error_json(f"old_text 未在 {path} 中找到")
            if count > 1 and not replace_all:
                return _error_json(
                    f"old_text 在 {path} 中出现 {count} 次；请提供更长的上下文，"
                    "或传 replace_all=true"
                )
            updated = (
                text.replace(old_text, new_text)
                if replace_all
                else text.replace(old_text, new_text, 1)
            )
            if len(updated) > MAX_WRITE_CHARS:
                return _error_json(f"修改后内容超过上限（{MAX_WRITE_CHARS} 字符）")
            target.write_text(updated, encoding="utf-8")
            return json.dumps(
                {
                    "ok": True,
                    "path": path,
                    "replacements": count if replace_all else 1,
                },
                ensure_ascii=False,
            )
        except Exception as exc:  # noqa: BLE001
            return _error_json(f"{type(exc).__name__}: {exc}")

    def grep(
        self,
        pattern: str,
        path: str = ".",
        file_glob: str = "*",
        ignore_case: bool = False,
        max_results: int = 100,
    ) -> str:
        """在工作区内按正则搜索文本，返回 path:line: content。"""
        try:
            regex = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
        except re.error as exc:
            return f"Error: 正则表达式无效：{exc}"
        try:
            base = self.safe_path(path)
        except Exception as exc:  # noqa: BLE001
            return f"Error: {type(exc).__name__}: {exc}"
        if base.is_file():
            files = [base]
        elif base.is_dir():
            files = sorted(base.rglob(file_glob or "*"))
        else:
            return "(no matches)"

        limit = max(1, min(int(max_results or 100), MAX_GREP_RESULTS))
        results: list[str] = []
        for file in files:
            try:
                relative_parts = file.relative_to(self.root).parts
                if any(part in DENY_WRITE_PARTS for part in relative_parts):
                    continue
                if file.stat().st_size > MAX_GREP_FILE_BYTES:
                    continue
                raw = file.read_bytes()
                if b"\x00" in raw[:1024]:
                    continue
                text = raw.decode("utf-8", errors="replace")
            except (OSError, ValueError):
                continue
            relative = file.relative_to(self.root).as_posix()
            for lineno, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    results.append(f"{relative}:{lineno}: {line.strip()[:200]}")
                    if len(results) >= limit:
                        return "\n".join(results)
        return "\n".join(results) if results else "(no matches)"

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

    @tool(
        "write_file",
        description=(
            "创建或覆盖工作区内的文本文件。新建文件优先用本工具；"
            "修改已有文件优先用 edit_file；覆盖已有文件需 overwrite=true。"
        ),
    )
    def write_file(path: str, content: str, overwrite: bool = False) -> str:
        return workspace.write_file(path, content, overwrite)

    @tool(
        "edit_file",
        description=(
            "对工作区内的文本文件做精确替换；old_text 必须在文件中唯一出现，"
            "否则报错；replace_all=true 可替换全部出现。"
        ),
    )
    def edit_file(
        path: str,
        old_text: str,
        new_text: str,
        replace_all: bool = False,
    ) -> str:
        return workspace.edit_file(path, old_text, new_text, replace_all)

    @tool("glob", description="在工作区内按 glob 查找文件，例如 **/*.py。")
    def glob(pattern: str) -> str:
        return workspace.glob(pattern)

    @tool(
        "grep",
        description=(
            "在工作区内按正则搜索文本，返回 path:line: content。"
            "可用 path 限定目录、file_glob 限定文件类型，例如 *.py。"
        ),
    )
    def grep(
        pattern: str,
        path: str = ".",
        file_glob: str = "*",
        ignore_case: bool = False,
        max_results: int = 100,
    ) -> str:
        return workspace.grep(pattern, path, file_glob, ignore_case, max_results)

    @tool("run_command", description="在工作区执行 shell 命令，输出会写入运行窗口日志。")
    def run_command(command: str, timeout: int = 30) -> str:
        return workspace.run_command(command, timeout)

    return [read_file, write_file, edit_file, glob, grep, run_command]
