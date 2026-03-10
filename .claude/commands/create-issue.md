---
description: Create linked follow-up issues from newly discovered requirements or blockers.
---

# Create Issue: $ARGUMENTS

Default policy: auto-infer and confirm.

## 1. Gather context

Use current branch issue (if present), project progress, and related open issues.

## 2. Draft issue(s)

For each proposed issue include:

- title
- summary/problem statement
- in-scope and out-of-scope
- testable acceptance criteria
- labels
- priority
- milestone
- dependency links (`blockedBy`, `blocks`, `relatedTo`)

## 3. Confirm

Show draft(s) and ask for confirmation before creating.

## 4. Create and link

Create in team `Engineering`, project `ETF-Predict`, then link dependencies and post backlinks.

## 5. Report

Return created IDs, URLs, dependency summary, and recommended execution order.
