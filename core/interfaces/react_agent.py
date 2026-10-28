"""业务入口的兼容层：默认加载 robot_vacuum 场景。

框架与业务的分离方式：
- agent/framework.py：通用 ReAct 运行时，不 import 业务工具；
- scenarios/<name>/：业务场景，提供工具、提示词、中间件、测试用例；
- 本文件只负责“按名字取场景 + 交给框架”，不再直接组装工具。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.agent.framework import FrameworkAgent
from core.scenarios.registry import get_scenario


class ReactAgent:
    def __init__(self, scenario_name: str = "robot_vacuum"):
        self.scenario = get_scenario(scenario_name)
        self.framework = FrameworkAgent(self.scenario)
        # 兼容旧代码：demo_agent_interfaces.py 直接访问 .agent
        self.agent = self.framework.agent

    def execute_stream(self, query: str, thread_id: str = "default"):
        yield from self.framework.execute_stream(query, thread_id=thread_id)

    def resume(self, thread_id: str, decisions: list[dict] | None = None):
        return self.framework.resume(thread_id, decisions=decisions)


if __name__ == '__main__':
    agent = ReactAgent()

    for chunk in agent.execute_stream("给我生成我的使用报告"):
        print(chunk, end="", flush=True)
