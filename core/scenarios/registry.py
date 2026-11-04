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


def _build_structured_demo() -> Scenario:
    from core.scenarios.structured_demo.scenario import build_scenario
    return build_scenario()


def _build_workspace_assistant() -> Scenario:
    from core.scenarios.workspace_assistant.scenario import build_scenario
    return build_scenario()


def _build_research_assistant() -> Scenario:
    from core.scenarios.research_assistant.scenario import build_scenario
    return build_scenario()


def _build_router() -> Scenario:
    from core.scenarios.router.scenario import build_scenario
    return build_scenario()


def _build_flow_demo() -> Scenario:
    from core.scenarios.flow_demo.scenario import build_scenario
    return build_scenario()


_BUILDERS = {
    "coding_demo": _build_coding_demo,
    "flow_demo": _build_flow_demo,
    "general": _build_general,
    "mcp_demo": _build_mcp_demo,
    "research_assistant": _build_research_assistant,
    "robot_vacuum": _build_robot_vacuum,
    "router": _build_router,
    "structured_demo": _build_structured_demo,
    "workspace_assistant": _build_workspace_assistant,
}


def list_scenarios() -> list[str]:
    """已注册场景 + 用 spec 构建的场景（控制台里新建的也算）。"""
    return sorted(set(_BUILDERS) | set(_spec_names()))


def get_scenario(name: str = "robot_vacuum") -> Scenario:
    builder = _BUILDERS.get(name)
    if builder is not None:
        return builder()
    if name in _spec_names():
        from core.scenarios.generic import build_generic_spec_scenario

        return build_generic_spec_scenario(name)
    available = ", ".join(list_scenarios())
    raise ValueError(f"未知场景：{name}（可用：{available}）")


def _spec_names() -> list[str]:
    """延迟 import：只读数据视图不该顺带加载工具链。"""
    from core.scenarios.generic import spec_scenario_names

    return spec_scenario_names()
