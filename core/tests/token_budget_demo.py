# -*- coding: utf-8 -*-
"""Token 预算演示：把预算压到 200，观察 run 在超限前被截断。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.agent.framework import FrameworkAgent  # noqa: E402
from core.scenarios.registry import get_scenario  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def main():
    scenario = get_scenario()
    scenario.token_budget = 200
    agent = FrameworkAgent(scenario)
    state = agent.invoke("小户型适合哪些扫地机器人？")
    print("回答：", state["messages"][-1].content)
    print("trace_id：", agent.last_trace_id)


if __name__ == "__main__":
    main()
