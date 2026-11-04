# 分层抽样集（每类 5 条）

> 这里不是官方 benchmark 成绩，也不是用来替代现有评测集的。
> 它只解决“现有抽样覆盖不均”的问题：BFCL 只测两类、RGB 只有中文
> refine/int/fact、τ² 只有 retail。

## 文件

| 文件 | 内容 |
|---|---|
| `bfcl_5per_category.jsonl` | BFCL v4 的 19 个类别，每类 5 条 |
| `rgb_5per_category.jsonl` | RGB 中/英 × normal/integration/counterfactual，每类 5 条 |
| `tau2_5per_domain.jsonl` | τ² 的 airline / banking / retail / telecom，每域 5 条 |
| `multihop_5per_type.jsonl` | MultiHop 的 4 个 question_type，每类 5 条 |
| `selections.jsonl` | **逐条出处**：源文件、源 hash、源行号、源 id |
| `selections.md` | 按类别汇总的出处表 |
| `manifest.json` | seed、每类目标、各集合计数与源规模 |

> `*_5per_*.jsonl` 是从本地 benchmark 源生成的原始样本，**不随仓库分发**
> （RGB 源数据是 CC BY-NC-SA，不能直接塞进 MIT 仓库）。
> 仓库只保留 `selections.jsonl` / `selections.md` / `manifest.json` 作为出处记录；
> 在本地跑一次生成命令即可还原原始样本。

## 抽样规则

- seed = 42，每类 5 条；
- 先按源 id 排序，再用 `seed + category` 随机抽样，不是取前 5 条；
- BFCL 的 `format_sensitivity` 是索引文件，没有题目正文，跳过；
- RGB 没有独立的 rejection 源文件，不伪造该类别；
- MultiHop 的 null_query 保留；全量评测另见 `outputs/public/multihop_full.md`。

## 重新生成

```powershell
python -m core.quality.stratified --per-category 5 --seed 42
```

重新生成会覆盖本目录的 jsonl / selections / manifest，但不会动
`data/evals/datasets/public/` 下的现有抽样集。
