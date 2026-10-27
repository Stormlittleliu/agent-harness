# -*- coding: utf-8 -*-
"""RAG/LLM 评测统一入口。

用法：
    python evals/run_eval.py retrieval [--limit N]
    python evals/run_eval.py generation [--limit N]
    python evals/run_eval.py judge [--limit N]
    python evals/run_eval.py public [--rgb-limit N] [--skip-multihop]
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = {
    "retrieval": ROOT / "evals" / "scripts" / "eval_retrieval.py",
    "generation": ROOT / "evals" / "scripts" / "eval_generation.py",
    "judge": ROOT / "evals" / "scripts" / "eval_judge.py",
    "public": ROOT / "evals" / "scripts" / "eval_public_benchmarks.py",
    "bfcl": ROOT / "evals" / "scripts" / "eval_bfcl.py",
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print(__doc__)
        print("可用命令：" + ", ".join(SCRIPTS))
        return
    command = sys.argv[1]
    try:
        script = SCRIPTS[command]
    except KeyError:
        print(f"未知命令：{command}（可用：{', '.join(SCRIPTS)}）")
        raise SystemExit(2)
    result = subprocess.run([sys.executable, str(script), *sys.argv[2:]], cwd=str(ROOT))
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
