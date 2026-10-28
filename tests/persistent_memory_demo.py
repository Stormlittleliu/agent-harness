# -*- coding: utf-8 -*-
"""持久化记忆演示：两个独立的 ReactAgent 实例共享同一个 SQLite checkpoint。

第一次 invoke 写入“我叫小明”，销毁实例后新建第二个实例，
用同一个 thread_id 提问，验证会话不是只存在进程内存里。
"""
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.react_agent import ReactAgent  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def main():
    thread_id = f"persist-{uuid.uuid4().hex[:8]}"

    agent_a = ReactAgent()
    print("checkpoint backend：", agent_a.framework.scenario.checkpoint_backend)
    print("thread_id：", thread_id)
    agent_a.framework.invoke("我叫小明，请记住我的名字。", thread_id=thread_id)
    print("第一个实例已写入，销毁实例...")
    del agent_a

    agent_b = ReactAgent()
    state = agent_b.framework.invoke("我叫什么名字？", thread_id=thread_id)
    print("第二个实例回答：", state["messages"][-1].content)

    snapshot = agent_b.framework.get_state(thread_id)
    print("checkpoint 消息数：", len(snapshot.values.get("messages", [])))


if __name__ == "__main__":
    main()
