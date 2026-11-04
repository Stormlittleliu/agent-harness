# 范式采纳：门槛、版本与回退（M3）

> 对应 `core/quality/adoption.py`、`core/interfaces/dashboard/patterns.py`。
> 一句话：候选必须先有 shadow 证据、过门槛，才允许写 active；采纳只是新增版本，
> 回退只改指针，历史版本一个都不删。

## 1. 为什么需要“采纳”这一层

M1 产出 candidate，M2 编译出 candidate spec，但这两步都**不改变线上结构**。
如果直接把候选设为 active，就等于“挖到一条路径就上线”，会把相关当因果。
采纳层把最后一步变成显式动作，并留下审计记录：

```text
patterns.json → candidates/<pattern_id>.json → shadow.json → gate → adopt → rollback
```

## 2. 门槛

`evaluate_gate(shadow)` 逐项判断：

| 项 | 规则 | 缺数据时 |
|---|---|---|
| pass^k | candidate ≥ baseline | 用 `pass_rate` 兜底 |
| outcome | candidate ≥ baseline | 任一侧没有 outcome 数据 → 跳过 |
| token 成本 | candidate ≤ baseline × 1.25 | baseline 为 0 → 跳过 |
| 延迟 | candidate ≤ baseline × 1.5 | baseline 为 0 → 跳过 |
| 安全回归 | `safety_regressions` 为空 | 必须有该字段，缺省视为空 |

任一项不过 → `GateResult.passed=False`，`reasons` 逐条说明；`adopt_candidate`
会拒绝，active 不变。

## 3. 版本与记录

采纳时：

1. 读当前 `active.json`，记下 `baseline_version`（如 `v4`）；
2. 校验候选：场景名一致、`validate_spec` 通过；
3. 给候选的 `provenance` 补 `status=adopted`、`adopted_at`、`shadow_id`、
   `baseline_version`；
4. `save_spec(make_active=True)` 生成 `v5.json` 并切 active；
5. 写采纳记录 `outputs/adoptions/<scenario>/adopt-*.json`。

baseline 的 `v4.json` 不删、不改。记录里有 `gate` 快照，事后能回答
“当时凭什么采纳”。

回退：

1. 找最近一条 `action=adopted` 记录；
2. 把 `active.json` 原子写回 `baseline_version`；
3. 写一条 `action=rolled_back` 记录，不删除 `v5.json`。

所以回退是“切回去”，不是“撤销发布”；新版本还在，可以再次比较。

## 4. 质量页的「范式」视图

位置：质量 → 看资产 → 范式。

- 列表：名称 / 类型 / support / 成功率 / lift / 成本；
- 详情：步骤、证据（成功 run）、反例（失败 run）；
- 动作：
  - **编译成候选**：写 `data/specs/<scenario>/candidates/`，不碰 active；
  - **试运行 shadow**：真实调模型跑 baseline/candidate，写
    `outputs/shadow/<shadow_id>/shadow.json`；按钮上明确写了会计费；
  - **采纳**：只有 shadow 存在且 gate 通过才可点；
  - **回退**：有采纳记录才可点；
  - **拒绝**：在挖掘目录记一条 `rejected.json`，不改任何 spec。

页面不自动采纳，也不在打开时偷偷跑模型——所有耗时动作都绑在按钮上。

## 5. 为什么不在这一层做自动优化

- shadow 只是证据，不是因果证明；采纳仍要人确认；
- pass^k 需要多 trial，成本高；页面默认只跑 1 trial、最多 8 条 case，
  正式 A/B 应走 CLI / 评测 runner；
- 门槛只看“不下降”，不看“涨了多少”；涨了但成本翻倍也会被 token/延迟项拦住。

## 6. 命令与文件

```powershell
# 候选与 shadow 可由页面触发；也可以直接调用 Python API
python -m core.scenarios.pattern_to_spec --patterns outputs/patterns/<id>/patterns.json --dry-run
```

输出目录：

```text
data/specs/<scenario>/
  vN.json
  active.json
  candidates/<pattern_id>.json     # M2，不是 active
outputs/patterns/<mining_id>/      # M1
outputs/shadow/<shadow_id>/        # M2/M3
outputs/adoptions/<scenario>/      # M3
```

## 7. 边界

- 不自动采纳；不自动改 active；
- 不删除 baseline；回退只改指针；
- 不把 `decision=pending` 当成通过；采纳必须由页面按钮/API 显式调用；
- 安全回归只看 shadow 里标了 `safety` 的 case；完整安全评测仍在评测层。
