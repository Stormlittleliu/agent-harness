# -*- coding: utf-8 -*-
"""Human-in-the-loop 演示：高风险工具需要人工批准后才执行。"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from interfaces.react_agent import ReactAgent  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision", default="approve", choices=["approve", "reject"])
    parser.add_argument("--question", default="重置设备 R-1001")
    args = parser.parse_args()

    agent = ReactAgent()
    thread_id = f"hitl-{args.decision}"

    state = agent.framework.invoke(args.question, thread_id=thread_id)
    interrupts = state.get("__interrupt__")
    if not interrupts:
        print("未触发审批，最终回答：")
        print(state["messages"][-1].content)
        return

    print("已触发人工审批：")
    for item in interrupts:
        print(f"  {getattr(item, 'value', item)}")

    decision = {"type": args.decision}
    if args.decision == "reject":
        decision["message"] = "演示：拒绝高风险操作"

    final = agent.framework.resume(thread_id, [decision])
    print(f"\n审批结果（{args.decision}）后的回答：")
    print(final["messages"][-1].content)


if __name__ == "__main__":
    main()
