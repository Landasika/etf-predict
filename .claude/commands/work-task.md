---
description: Start a Linear issue with strict readiness gates, dependency checks, and planning.
---

# Work Task: $ARGUMENTS

You are starting work on issue `$ARGUMENTS` for team `Engineering` project `ETF-Predict`.

## 1. Fetch issue context

Retrieve issue, parent issue, labels, milestone, priority, dependencies, and unresolved comments.

## 2. Enforce blocker gate

If any `blockedBy` issue is not `Done`, report blockers, suggest unblocked alternatives, and stop.

## 3. Enforce ticket quality gate

Before coding, require:

- clear summary and scope boundaries
- testable acceptance criteria
- referenced specs loaded

If missing, comment with required clarifications and stop.

## 4. Move to In Progress

Transition issue to `In Progress`.

## 5. Create branch

Branch format:

`<prefix>/<issue-id-lowercase>-<slug>`

Prefix mapping:

- Bug -> `fix/`
- Improvement/refactor -> `cleanup/`
- otherwise -> `feature/`

## 6. Load architecture context

Read referenced design/spec docs before planning.

## 7. Post implementation plan

Comment a numbered plan including changed files, acceptance-criteria mapping, tests, and risk notes.

## 8. Present plan and wait

Show the plan and wait for explicit approval before coding.
