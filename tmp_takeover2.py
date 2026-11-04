import shutil, tempfile
from pathlib import Path

from core.quality import agent_eval
from core.scenarios import library
from core.scenarios.registry import get_scenario
from core.scenarios.spec import ScenarioSpec, save_spec

root = Path("data/specs")

SPECS = {
    "general": dict(
        description="白板：没有工具、没有工作流",
        tools=[],
        harness={"enable_todo": False, "enable_summarization": False, "tool_call_limit": 8, "token_budget": None},
        workflows={},
    ),
    "structured_demo": dict(
        description="结构化输出：Pydantic ReportSchema 约束最终报告",
        tools=[],
        response_format="ReportSchema",
        harness={"enable_todo": False, "enable_summarization": False, "tool_call_limit": 8, "token_budget": None},
        workflows={},
    ),
}

for name, extra in SPECS.items():
    target = root / name
    backup = Path(tempfile.mkdtemp()) / name
    if target.exists():
        shutil.move(str(target), str(backup))

    legacy = get_scenario(name)  # 还没有 spec，走代码
    spec = ScenarioSpec(
        name=name,
        kind="agent",
        system_prompt=legacy.system_prompt,
        cases_path=f"core/scenarios/{name}/cases.jsonl",
        **extra,
    )
    print(f"=== {name} baseline (code) ===")
    base = agent_eval.run(name)
    print("baseline:", base["passed"], "/", base["total"])

    save_spec(spec, root=root)
    print(f"=== {name} facsimile (spec) ===")
    fac = agent_eval.run(name)
    print("facsimile:", fac["passed"], "/", fac["total"])
    print("kept:", target)

print("library:", [(e.name, e.from_spec, e.editable, e.cases) for e in library.entries() if e.from_spec])