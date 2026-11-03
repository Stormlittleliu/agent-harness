# -*- coding: utf-8 -*-
"""启动 Streamlit 控制台，默认自动选择空闲端口。

用法：
    python run_dashboard.py
    python run_dashboard.py --app app_rag.py
    python run_dashboard.py --port 8600
    python run_dashboard.py -- --server.address 0.0.0.0

默认从 8501 开始找空闲端口，避免 8501 被占用时启动失败。
"""
from __future__ import annotations

import argparse
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def port_in_use(port: int) -> bool:
    """检测端口是否已被监听。

    Windows 上 SO_REUSEADDR 会让已被占用的端口仍然 bind 成功，所以先做
    connect 探测，再尝试 bind；两步都通过才认为是空闲。
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            return True
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return True
    return False


def find_free_port(start: int = 8501, end: int = 8599) -> int:
    """在 [start, end] 内找一个可绑定的本地端口。"""
    for port in range(start, end + 1):
        if not port_in_use(port):
            return port
    raise RuntimeError(f"没有找到空闲端口（{start}-{end}）")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="启动 Agent Harness 控制台")
    parser.add_argument("--app", default="app_agent.py", help="Streamlit 入口文件")
    parser.add_argument("--port", type=int, default=0, help="指定端口；0 = 自动选择")
    args, extra = parser.parse_known_args(argv)

    app_path = (ROOT / args.app).resolve()
    if not app_path.exists():
        print(f"入口文件不存在：{app_path}", file=sys.stderr)
        return 1

    port = args.port or find_free_port()
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        *extra,
    ]
    print(f"Dashboard: http://localhost:{port}")
    print(f"App: {app_path.name}")
    try:
        return subprocess.run(command, cwd=str(ROOT), check=False).returncode
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
