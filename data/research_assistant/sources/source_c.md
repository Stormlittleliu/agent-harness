# 资料 C：Multi-Agent Fan-out

Multi-agent fan-out is useful for independent, read-only research tasks: several subagents read different sources and the lead agent synthesizes their findings.

Write-heavy handoff is risky because subagents would need to exchange state and approvals. Use a single agent for sequential, stateful work.
