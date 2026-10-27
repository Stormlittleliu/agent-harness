# -*- coding: utf-8 -*-
"""会话记忆演示：同一个 thread_id 下保留历史。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent.react_agent import ReactAgent  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def main():
    agent = ReactAgent()
    thread_id = "memory-demo"

    agent.framework.invoke("我叫小明，请记住我的名字。", thread_id=thread_id)
    state = agent.framework.invoke("我叫什么名字？", thread_id=thread_id)
    print("回答：", state["messages"][-1].content)

    snapshot = agent.framework.get_state(thread_id)
    print("消息数：", len(snapshot.values.get("messages", [])))


if __name__ == "__main__":
    main()
