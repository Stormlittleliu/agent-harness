"""场景注册表：框架通过名字获取场景，不直接 import 具体业务。"""
from core.agent.contracts import Scenario


def _build_general() -> Scenario:
    from core.scenarios.general.scenario import build_scenario
    return build_scenario()


def _build_coding_demo() -> Scenario:
    from core.scenarios.coding_demo.scenario import build_scenario
    return build_scenario()


def _build_mcp_demo() -> Scenario:
    from core.scenarios.mcp_demo.scenario import build_scenario
    return build_scenario()


def _build_robot_vacuum() -> Scenario:
    from core.scenarios.robot_vacuum.scenario import build_scenario
    return build_scenario()


_BUILDERS = {
    "coding_demo": _build_coding_demo,
    "general": _build_general,
    "mcp_demo": _build_mcp_demo,
    "robot_vacuum": _build_robot_vacuum,
}


def list_scenarios() -> list[str]:
    return sorted(_BUILDERS)


def get_scenario(name: str = "robot_vacuum") -> Scenario:
    try:
        builder = _BUILDERS[name]
    except KeyError as exc:
        available = ", ".join(list_scenarios())
        raise ValueError(f"未知场景：{name}（可用：{available}）") from exc
    return builder()
