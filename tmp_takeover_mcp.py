import shutil, tempfile
from pathlib import Path

from core.quality import agent_eval
from core.scenarios.registry import get_scenario
from core.scenarios.spec import ScenarioSpec, save_spec

name = "mcp_demo"
root = Path("data/specs")
target = root / name
backup = Path(tempfile.mkdtemp()) / name
if target.exists():
    shutil.move(str(target), str(backup))

legacy = get_scenario(name)
spec = ScenarioSpec(
    name=name,
    kind="agent",
    description="MCP 演示：Memory（跨会话记忆）+ Fetch（网页读取）",
    tools=[t.name for t in legacy.tools],
    system_prompt=legacy.system_prompt,
    cases_path=f"core/scenarios/{name}/cases.jsonl",
    harness={"enable_todo": False, "enable_summarization": False, "tool_call_limit": 6, "token_budget": 40000},
    workflows={},
)
print("=== baseline (code) ===")
base = agent_eval.run(name)
print("baseline:", base["passed"], "/", base["total"])

save_spec(spec, root=root)
print("=== facsimile (spec) ===")
fac = agent_eval.run(name)
print("facsimile:", fac["passed"], "/", fac["total"])
print("kept:", target)