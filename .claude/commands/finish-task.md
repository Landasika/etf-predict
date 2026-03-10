---
description: Finish current issue with validation, self-review, PR creation, and Linear handoff.
---

# Finish Task

Resolve issue ID from current branch (`feature|fix|cleanup/<issue-id>-...`).

## 1. Validate current issue context

Fetch issue title, milestone, state, and acceptance criteria.

## 2. Run required checks

Run and report:

```bash
pytest tests/ -v
mypy core/ strategies/ api/ optimization/ --strict
ruff check .
ruff format --check .
```

If any fail, fix and re-run all checks.

## 3. Summarize diff

Run:

```bash
git diff main --stat
git diff --name-only main
```

## 4. Self-review via sub-agent

Review diff for bugs, security risks, dead code, over-engineering, and missing tests.

## 5. Create PR

Use:

```bash
gh pr create \
  --title "ENG-{N}: <concise summary>" \
  --body "Closes ENG-{N}

## Summary
- <what changed>

## Verification
- pytest tests/ -v
- mypy core/ strategies/ api/ optimization/ --strict
- ruff check .
- ruff format --check .

## Files Changed
- <key files/modules>

## Milestone
- <milestone name>"
```

## 6. Move to review state

Transition issue to `In Review`. If this state is missing, stop and report.

## 7. Post issue comment

Comment with PR URL, test results, and any remaining risks.
