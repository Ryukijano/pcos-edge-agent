---
description: Create a pull request from current branch with auto-generated description
---

1. Check current branch and status:
   ```bash
   git branch --show-current
   git status --short
   ```

2. Review all commits on this branch vs main:
   ```bash
   git log main..HEAD --oneline
   ```

3. Review the full diff:
   ```bash
   git diff main...HEAD --stat
   ```

4. Generate a PR title from the commit messages (use the first `feat:` or `fix:` commit).

5. Generate a PR body:
   - Summary of changes (from commit messages)
   - Files changed count
   - Lines added/removed
   - Test results: `python -m pytest tests/ -v --tb=short`
   - Breaking changes (if any)

6. Push the branch:
   ```bash
   git push -u origin HEAD
   ```

7. Create the PR:
   ```bash
   gh pr create --title "<TITLE>" --body "<BODY>"
   ```

8. Report the PR URL.
