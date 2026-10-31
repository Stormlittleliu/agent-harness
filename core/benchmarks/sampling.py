# -*- coding: utf-8 -*-
"""按来源 / 类别分层抽样，固定 seed，保证可复现。"""
from __future__ import annotations

import random
from collections import defaultdict

from core.benchmarks.schema import BenchTask

PREFERRED_SPLITS = {"test", "validation", "zh_refine"}


def stratified_sample(tasks: list[BenchTask], per_source: int = 12, seed: int = 42) -> list[BenchTask]:
    rng = random.Random(seed)
    by_source = defaultdict(list)
    for task in tasks:
        by_source[task.source].append(task)

    sampled = []
    for source in sorted(by_source):
        group = by_source[source]
        preferred = [task for task in group if task.split in PREFERRED_SPLITS]
        pool = preferred or group

        by_category = defaultdict(list)
        for task in pool:
            by_category[task.category].append(task)

        categories = sorted(by_category)
        if not categories:
            continue
        base, remainder = divmod(per_source, len(categories))
        quotas = {
            category: base + (1 if index < remainder else 0)
            for index, category in enumerate(categories)
        }
        # 类别样本不足时，把剩余名额转给其他类别
        selected = {
            category: min(quotas[category], len(by_category[category]))
            for category in categories
        }
        remaining = per_source - sum(selected.values())
        while remaining > 0:
            progressed = False
            for category in categories:
                if remaining == 0:
                    break
                if selected[category] < len(by_category[category]):
                    selected[category] += 1
                    remaining -= 1
                    progressed = True
            if not progressed:
                break

        for category in categories:
            items = list(by_category[category])
            rng.shuffle(items)
            for rank, task in enumerate(items[:selected[category]]):
                task.metadata["sample_seed"] = seed
                task.metadata["sample_rank"] = rank
                sampled.append(task)
    return sampled
