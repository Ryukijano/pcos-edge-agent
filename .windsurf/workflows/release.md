---
description: Create a new PCOS release with changelog and git tag
---

1. Run the full test suite and confirm all pass:
   ```bash
   python -m pytest tests/ -v --tb=short
   ```

2. Read the current version from `pyproject.toml` or determine the next version.

3. Review commits since last tag:
   ```bash
   git log $(git describe --tags --abbrev=0)..HEAD --oneline
   ```

4. Categorize changes:
   - **Features**: `feat:` commits
   - **Fixes**: `fix:` commits
   - **Docs**: `docs:` commits
   - **Breaking**: `BREAKING CHANGE` or `!:` commits

5. Update CHANGELOG.md with the new version and categorized changes.

6. Bump version in `pyproject.toml`.

7. Commit the release:
   ```bash
   git add -A && git commit -m "release: v<VERSION>"
   ```

8. Create and push the tag:
   ```bash
   git tag v<VERSION> && git push origin v<VERSION>
   ```

9. Push main:
   ```bash
   git push origin main
   ```

10. Report the release tag and summary.
