---
name: review
description: Review code changes before committing
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
---

Review the current git diff and provide feedback:

1. Run `git diff --staged` (or `git diff` if nothing is staged)

2. Check for:
   - Logic errors or bugs
   - Missing error handling
   - Security issues (especially around PII/privacy in broker/)
   - Style inconsistencies
   - Missing test coverage for new features
   - Broken imports or references

3. Verify tests pass: `python -m pytest tests/ -v --tb=short`

4. Summarize findings and suggest improvements.

5. If issues found, fix them directly.
