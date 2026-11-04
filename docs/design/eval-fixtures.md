# 任务级评测夹具（eval fixtures）

> 目标：按任务配工具，不再拿 `robot_vacuum` 或 `workspace_assistant` 去装所有评测任务。
>
> 代码：`core/quality/fixtures.py`；这是评测夹具，不是产品场景。

## 为什么单独一层

产品场景（`core/scenarios/<name>/`）回答的是“这个产品能不能用”：

- 有完整 prompt、业务工具、意图路由、发布配置；
- 有 5–13 条业务 case；
- 会被控制台读取、被 `entry.yml` 发布。

任务级评测回答的是“这条任务，在合适工具下能不能做对”：

- 一条 instruction；
- 只配这条任务需要的工具（外加可控的干扰项）；
- 断言是任务级的：调了哪个工具、参数对不对、该不该拒答；
- 不注册到控制台，不写 `data/specs/`，不发布。

把两者混在一起，测出来的失败分不清是“任务难”还是“产品场景不匹配”。

## 结构

```python
TaskFixture(
    id="bfcl-simple_python_0-clean",
    family="bfcl",
    variant="clean",
    instruction="...",
    tools=[ToolStub(...)],
    expected={"calls": [{"name": "...", "args": {...}}]},
)
```

`ToolStub` 做三件事：

- 把 benchmark 的 JSON function schema 变成可调用的 LangChain tool；
- 记录实际调用 `(name, args)`；
- 按配置返回 `result` 或抛 `error`。

`run_fixture` 用 `FrameworkAgent(Scenario(...))` 跑一条，判分看 **stub 的实际调用**，
不看 AIMessage 里的 `tool_calls`——审批被拒绝时，模型仍会“提议”调用，但工具没执行，
这两者必须分开。

## 五个变体

| variant | 工具集 | 期望 | 抓什么 |
|---|---|---|---|
| `clean` | 只给必需工具 | 正常调用 | 工具适配/prompt 是否成立 |
| `distractor` | 必需 + 2–5 个同域干扰 | 不误调干扰项 | 工具选择 |
| `missing` | 删掉必需工具 | 说明做不到/追问 | 幻觉调用、硬编答案 |
| `failure` | 必需工具返回错误 | 重试/降级/说明失败 | 错误恢复 |
| `permission` | 高风险工具 | approve 执行 / reject 不执行 | HITL 与副作用隔离 |

`permission` 用真实的 `HumanInTheLoopMiddleware`，不是伪造一个“审批通过”的标记：

- approve：`invoke` 中断 → `resume({"type": "approve"})` → stub 记录调用；
- reject：`resume({"type": "reject"})` → stub 没有调用记录，回答说明未执行。

## 怎么跑

```powershell
# 只打印夹具，不调模型
python -m core.quality.fixtures --family bfcl --limit 3 --dry-run

# 跑 BFCL simple：clean / distractor / missing / failure
python -m core.quality.fixtures --family bfcl --limit 3

# 只跑 permission：approve / reject
python -m core.quality.fixtures --family permission

# 只跑某几个变体
python -m core.quality.fixtures --family bfcl --limit 3 --variants clean,distractor
```

报告写到 `outputs/fixtures/`；不是官方 benchmark 分数。

## POC 结果（2026-11-04）

BFCL `simple_python_0`，4 条：

- clean ✅：调用 `calculate_triangle_area(base=10, height=5)`；
- distractor ✅：没有碰 `db_fetch_records` / `generate_circle_image` / `calculate_magnetic_field`；
- missing ❌：没有工具，模型直接心算了 25，没有说明“工具不可用”——这是要抓的幻觉；
- failure ✅：工具报错后，回答说明失败，没有假装成功。

permission：

- approve ✅：HITL 中断 → 批准 → `reset_device` 执行；
- reject ✅：HITL 中断 → 拒绝 → stub 无调用记录，回答说明未执行。

扩到 10 条 BFCL simple 任务 × 4 变体（40 条）：**32/40**。

| variant | 通过 |
|---|---:|
| clean | 10/10 |
| distractor | 10/10 |
| failure | 10/10 |
| missing | 2/10 |

失败的 8 条全是 `missing`：没有工具时模型直接心算，不提“工具不可用”。
这不是 fixture 坏了，是它抓到了一个稳定的行为缺陷——缺工具时倾向于编答案，
而不是说明能力边界。clean/distractor/failure 全过，说明这个差异不是 prompt 噪声。

这两个结果说明变体不是“换个 prompt 重跑”，而是真的改变了工具集和断言。

## 边界

- **这是行为探针，不是官方榜**：BFCL 的官方分仍走官方 AST/harness；fixture 只回答“工具选择/参数/恢复”这一层。
- **工具是 stub**：clean 过不代表真实 API 通；报告里标 `simulated`。
- **目前只覆盖 BFCL + permission**：τ²/SWE/WebArena/OSWorld 需要环境适配，不在这一版。
- **不是产品场景**：不要把它注册进 `data/specs/`，也不要让控制台读到它。

## 下一步

1. 把 `missing` 的“直接心算”失败模式固化成断言，扩到 10 条 BFCL；
2. τ² retail 的 `clean / policy_conflict / tool_failure`；
3. 逐步把 `selfbuilt` 的 26 条从产品场景迁到 fixture；产品场景保留做端到端回归。
