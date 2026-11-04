from pathlib import Path

from core.quality import agent_eval
from core.scenarios import spec as spec_module
from core.scenarios.spec import save_spec

root = Path("data/specs")

ws = spec_module.load_active_spec("workspace_assistant")
data = spec_module.spec_to_dict(ws)
qa = data["workflows"]["document_qa"]
qa["edges"] = [
    ["__start__", "retrieve"],
    ["retrieve", "branch"],
    ["branch", "refuse", "refuse"],
    ["branch", "answer", "miss"],
    ["refuse", "__end__"],
    ["answer", "cite"],
    ["cite", "__end__"],
]
spec_obj = spec_module.spec_from_dict(data)
print("errors:", spec_module.validate_spec(spec_obj))
path = save_spec(spec_obj)
print("workspace v:", path)

compiled = spec_module.build_workflows(spec_obj, type("S", (), {"tools": []})())
print("nodes:", {k: sorted(n for n in v.get_graph().nodes if not n.startswith("__")) for k, v in compiled.items()})

summary = agent_eval.run("workspace_assistant")
print("workspace cases:", summary["passed"], "/", summary["total"])

summary = agent_eval.run("robot_vacuum")
print("robot cases:", summary["passed"], "/", summary["total"])