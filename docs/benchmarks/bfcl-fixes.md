# BFCL 针对性优化：语法提示与重复调用

> 2026-10-31，BFCL 60 条（45 simple + 15 irrelevance），每个 case 3 trial
> 仅跑 BFCL，RAG 不变；输出 `outputs/demo_bfcl/`

## 1. 结果

| 配置 | 改动 | BFCL pass^k | mean | 修复 | 回归 |
|:---|:---|:---:|:---:|:---:|:---:|
| hybrid | 基线 | 55/60 | 92.8% | — | — |
| python_syntax | 提示乘方用 `**` | **59/60** | 98.3% | 4 | 0 |
| bfcl_fixes | 语法提示 + 重复调用抑制 | **60/60** | 100% | 1 | 0 |
| hybrid_validation | 只加参数校验 | 56/60 | 93.3% | 0 | 4 |

## 2. 归因

### 稳定有效：Python 语法提示

`simple_python_13/15/16` 在 hybrid 下 3/3 trial 全错，错误都是 `^`：

```text
2x^2、x^3、x^2
```

加提示后变成：

```text
2*x**2、x**3、x**2
```

评分侧把 `2*x**2` 与 `2x**2` 视为等价，因此 3 条全部通过，且没有回归。

### 不稳定：`simple_python_377`

hybrid 下 3 trial 中有 1 次重复调用：

```text
第一次：get_current_time(city, country)
第二次：get_current_time(city, country, format)
```

`python_syntax` 配置（没有重复抑制）把它修好了；`bfcl_fixes` 也通过。说明这条更可能是 **模型方差**，不能归因于抑制中间件。

### 不稳定：`irrelevance_236`

`bfcl_fixes` 下 3/3 trial 都是 **0 次调用**，直接通过；但 `python_syntax` 下 3/3 trial 都是 3 次调用。

重复调用抑制不可能让第一次调用消失，所以这条也是 **模型方差**，不能归因于中间件。

### 参数校验隔离

`hybrid_validation` 只加参数校验，BFCL 56/60，且相对 bfcl_fixes 回归 4 条（就是语法 3 条 + irrelevance 1 条）。说明参数校验没有解决这些问题。

## 3. 复跑结果

`outputs/demo_bfcl_rep` 第二轮 bfcl_fixes（3 trial）：

```text
BFCL 60/60，mean 100%
simple 45/45，irrelevance 15/15，0 失败
```

两轮独立的 3-trial 都是 60/60，说明 **组合配置在这 60 条样本上稳定**。

## 4. RAG 确认

`outputs/demo_rag_confirm`（45 条 × 3 trial）：

| 配置 | RAG pass^k | mean | 失败 |
|:---|:---:|:---:|:---|
| hybrid | 44/45 | 97.8% | `comparison_query-4` |
| bfcl_fixes | 44/45 | 97.8% | `comparison_query-4` |

两者完全一致，0 修复、0 回归。说明 BFCL 侧的语法提示和重复抑制没有影响 RAG。

## 5. 最终组合

```text
bfcl_fixes:
  BFCL 60/60（两轮独立 3-trial 复跑）
  RAG  44/45（与 hybrid 完全一致）
```

## 6. 结论

- **Python 语法提示是真实收益**：稳定修复 3 条 `wrong_args`；
- **组合配置稳定 60/60**：语法提示 + 重复调用抑制，两轮复跑无失败；
- **RAG 无回归**：确认 44/45，唯一失败仍是 `comparison_query-4`；
- **抑制中间件的独立贡献仍未被证明**：377/236 的修复更像方差；但组合配置无回归，可以暂时保留；
- 当前仍是简化评分 + 60 条抽样，不能声称“BFCL 官方 100%”。

## 4. 下一步

1. 复跑 bfcl_fixes，确认 60/60 是否稳定；
2. 用官方 BFCL scorer 复核语法修复；
3. 若抑制确实无效，删掉中间件或只在 fault-injection 中保留；
4. 对 `irrelevance` 加“是否需要工具”的二分类/规则，而不是靠 prompt；
5. RAG 侧继续做 `comparison_query-4` 的 rerank。
