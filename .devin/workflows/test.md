---
description: Run the PCOS test suite and report results
---

1. Run the full test suite:
   ```bash
   python -m pytest tests/ -v --tb=short
   ```

2. If any tests fail:
   - Read the failure output
   - Identify the root cause
   - Fix the failing test or the code it tests
   - Re-run only the failing tests: `python -m pytest tests/<failing_test> -v`

3. If all tests pass, report the count and runtime.

4. If coverage is available, run:
   ```bash
   python -m pytest tests/ --cov=broker --cov=memory --cov=models --report=term-missing
   ```
