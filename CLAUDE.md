# CLAUDE.md

本仓库的编码约定、环境说明和**场景归属规则**都写在 [AGENTS.md](AGENTS.md) 里，先读它。

最短版本：改 `core/scenarios/<name>/` 下的代码前，先跑

```powershell
python -m core.scenarios.eject <name> --reason "..."
```

否则构建会抛 `OwnershipError`。
