---
name: add-surface
description: Add a new routing surface to the PCOS broker
allowed-tools:
  - read
  - grep
  - glob
  - edit
  - exec
triggers:
  - user
  - model
---

Add a new routing surface to the PCOS edge agent broker:

1. Read `broker/router/router.py` to understand the existing `Surface` enum and routing logic.

2. Add the new surface to the `Surface` enum.

3. Add a system prompt for the new surface in `broker/planner/planner.py` under `SYSTEM_PROMPTS`.

4. Add the surface description to `hf_space/app.py` in `SURFACE_DESCRIPTIONS`.

5. If the surface needs a new endpoint, add it to `broker/routers/route_router.py`.

6. Update `broker/context/context_schema.py` if new context fields are needed.

7. Add tests in `tests/test_router.py` for the new surface.

8. Run tests: `python -m pytest tests/ -v --tb=short`

9. Update README.md with the new surface in the routing table.
