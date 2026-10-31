# -*- coding: utf-8 -*-
"""下载 GAIA validation 集到本地（需要 HF token + 接受数据集条款）。

用法：
    set HF_TOKEN=hf_xxx
    python -m core.benchmarks.download_gaia --proxy http://127.0.0.1:7897
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path

from core.benchmarks.paths import GAIA_ROOT

CONFIGS = ["2023_level1", "2023_level2", "2023_level3"]
BASE = "https://datasets-server.huggingface.co/rows"


def read_token() -> str | None:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
    if token:
        return token
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith(("HF_TOKEN=", "HUGGINGFACE_HUB_TOKEN=")):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def fetch(config: str, offset: int, length: int, token: str, proxy: str | None):
    url = (
        f"{BASE}?dataset=gaia-benchmark%2FGAIA&config={config}"
        f"&split=validation&offset={offset}&length={length}"
    )
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    with opener.open(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="下载 GAIA validation 集")
    parser.add_argument("--proxy", default=None, help="例如 http://127.0.0.1:7897")
    parser.add_argument("--out", default=str(GAIA_ROOT / "gaia_validation.jsonl"))
    args = parser.parse_args(argv)

    token = read_token()
    if not token:
        raise SystemExit(
            "未找到 HF_TOKEN。请先到 https://huggingface.co/datasets/gaia-benchmark/GAIA "
            "接受条款并创建 read token，然后设置 HF_TOKEN。"
        )

    rows = []
    for config in CONFIGS:
        offset = 0
        total = None
        while total is None or offset < total:
            payload = fetch(config, offset, 100, token, args.proxy)
            total = payload.get("num_rows_total", 0)
            rows.extend(item["row"] for item in payload.get("rows", []))
            offset += 100
            print(f"[{config}] {min(offset, total)}/{total}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
