---
description: Triage the board, surface risk, and recommend top next issues.
---

# Check Board

Review project `ETF-Predict` on team `Engineering`.

## 1. Group issues by state

Report counts and key issues for:

- `Backlog`
- `Todo`
- `In Progress`
- `In Review`
- `Done`

Include canceled states separately.

## 2. Milestone progress

For each milestone report total, done, blocked, and completion ratio.

## 3. Risk scan

Flag:

- stale `In Progress` issues (>=3 days)
- stale `In Review` issues (>=3 days)
- dependency deadlocks
- high-priority bugs not actively being addressed

## 4. Recommend top 3 next issues

Rank by:

1. unblocked first
2. urgent/high priority first
3. earlier milestone dependencies first
4. active-path bugs elevated

End with: `Use /work-task <ISSUE-ID> to start.`
