---
description: Lint and format the PCOS codebase
---

1. Run Python linting:
   ```bash
   python -m ruff check broker/ memory/ models/ tests/ hf_space/ tools/ --fix
   ```

2. Run Python formatting:
   ```bash
   python -m ruff format broker/ memory/ models/ tests/ hf_space/ tools/
   ```

3. Run type checking (if mypy is available):
   ```bash
   python -m mypy broker/ memory/ models/ --ignore-missing-imports
   ```

4. Check for common issues:
   - Unused imports
   - Missing type hints
   - Docstring coverage

5. If any issues remain, fix them manually.

6. Run tests to verify nothing broke:
   ```bash
   python -m pytest tests/ -v --tb=short
   ```

7. Report the lint results summary.
