# -*- coding: utf-8 -*-
"""场景归属 CLI（给人和编码 Agent 用）。

用法::

    python -m core.scenarios.eject flow_demo --status
    python -m core.scenarios.eject flow_demo --reason "改用自定义块"

``eject`` 是单向门：把场景从 spec-owned 转成 code-owned。
之后 spec 不再参与构建，可视化从代码内省、只读。
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.scenarios.ownership import eject, status  # noqa: E402


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="场景归属：查看或转为 code-owned")
    parser.add_argument("name", help="场景名，例如 flow_demo")
    parser.add_argument("--reason", default="", help="转 code-owned 的原因")
    parser.add_argument("--status", action="store_true", help="只看状态，不改归属")
    args = parser.parse_args(argv)

    if args.status:
        print(json.dumps(status(args.name), ensure_ascii=False, indent=2))
        return

    state = eject(args.name, args.reason)
    print(json.dumps(state.to_dict(), ensure_ascii=False, indent=2))
    print(
        f"已转为 code-owned：spec 失效，可视化只读。"
        f"请直接实现 core/scenarios/{args.name}/ 下的场景。",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
