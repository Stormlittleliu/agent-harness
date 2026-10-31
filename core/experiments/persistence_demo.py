# -*- coding: utf-8 -*-
"""P2：文件持久化演示。

单轮 benchmark 看不出 checkpoint 的收益；这里用同一 thread 的两轮对话验证：
- 第一次写入状态；
- 第二次从 SQLite checkpoint 读回。

运行：
    python -m core.experiments.persistence_demo
"""
import uuid
from pathlib import Path

from core.agent.framework import FrameworkAgent
from core.scenarios.registry import get_scenario

ROOT = Path(__file__).resolve().parents[2]


def main():
    scenario = get_scenario("general")
    scenario.checkpoint = True
    scenario.checkpoint_backend = "sqlite"
    scenario.checkpoint_path = "data/runtime/demo_persistence.sqlite"
    scenario.token_budget = 20000

    agent = FrameworkAgent(scenario)
    thread_id = f"persistence-{uuid.uuid4().hex[:8]}"

    first = agent.invoke("我叫小明，请记住这个名字。", thread_id=thread_id)
    second = agent.invoke("我叫什么名字？", thread_id=thread_id)

    print("第一轮：", first["messages"][-1].content)
    print("第二轮：", second["messages"][-1].content)
    print("thread_id：", thread_id)
    print("checkpoint：", ROOT / "data" / "runtime" / "demo_persistence.sqlite")


if __name__ == "__main__":
    main()
