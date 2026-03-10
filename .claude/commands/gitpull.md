---
description: Commit current changes and push to GitHub. Use -s flag to select from suggested commit messages.
---

# Git Pull: $ARGUMENTS

Commit and push current changes to GitHub repository.

## 1. Check git status

First, check the current git status to see what files have changed:

```bash
git status
```

## 2. Review changes

Show a summary of changes:

```bash
git diff --stat
```

## 3. Determine commit message mode

Check if `$ARGUMENTS` contains the `-s` flag:

### Mode A: Selection mode (if `-s` is present in `$ARGUMENTS`)

When user provides `-s` flag, analyze the changes and provide 3-5 suggested commit message options. Present them in a numbered list (1, 2, 3, 4, 5) with brief explanations of what each message covers. Then ask the user to select one by number.

Example format:
```
Based on the changes, here are suggested commit messages:

1. chore: 清理过时文档和策略代码
   - 删除 DEPLOYMENT.md, QUICKSTART.md 等过时文档
   - 移除废弃的策略实现文件
   - 添加代码质量配置文件

2. refactor: 简化项目结构并移除未使用代码
   - 清理 strategies/ 目录下的旧策略文件
   - 删除 examples/ 和 optimization/ 中的过时脚本
   - 更新 CLAUDE.md 和 requirements.txt

3. cleanup: 项目结构优化和代码质量改进
   - 移除 10,000+ 行废弃代码
   - 添加 mypy.ini 和 ruff.toml 配置
   - 更新核心 API 和自动更新脚本

Please select a commit message (1-3) or provide your own:
```

Wait for user selection, then proceed to step 4 with the selected message.

### Mode B: Auto mode (default, no `-s` flag)

When no `-s` flag is present, automatically generate the most appropriate commit message based on the changes analysis. Consider:

- For mostly deletions: use `chore:` or `cleanup:` prefix
- For new features: use `feat:` prefix
- For bug fixes: use `fix:` prefix
- For refactoring: use `refactor:` prefix
- For documentation: use `docs:` prefix

Keep it concise but descriptive (ideally under 50 chars for the summary).

Skip to step 4 with the generated commit message.

### Mode C: Custom message (if `$ARGUMENTS` is provided without `-s`)

If user provides a custom commit message as `$ARGUMENTS` (and it doesn't contain `-s`), use that message directly. Skip to step 4.

## 4. Stage and commit

Stage all changed files and create commit:

```bash
git add -A
git commit -m "<commit_message_from_step_3>"
```

IMPORTANT: Before executing the commit, show what will be committed and the commit message that will be used. Then proceed with the commit.

## 5. Push to remote

Push changes to the remote repository:

```bash
git push
```

If the current branch has no upstream tracking branch, use:

```bash
git push -u origin $(git branch --show-current)
```

If push fails due to remote changes, run `git pull --rebase` first, then push again.

## 6. Confirm success

Show the final status:

```bash
git status
git log -1 --oneline
```

## Notes

- This command will stage ALL changes (including deletions)
- The `-s` flag triggers selection mode where user chooses from suggestions
- Without `-s`, the command automatically generates and uses the best commit message
- If there are merge conflicts after pull, stop and ask user how to handle
- Always show what will be committed before executing the commit
