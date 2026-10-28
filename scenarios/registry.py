"""场景注册表：框架通过名字获取场景，不直接 import 具体业务。"""
from agent.contracts import Scenario


def _build_robot_vacuum() -> Scenario:
    from scenarios.robot_vacuum.scenario import build_scenario
    return build_scenario()


_BUILDERS = {
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
