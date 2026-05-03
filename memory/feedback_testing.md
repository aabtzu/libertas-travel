---
name: Always run tests before claiming done
description: After any code change, run pytest and confirm passing, never just say it's done
type: feedback
---

After making any code change or fix, run `pytest tests/ -x -q` and confirm tests pass before saying the task is complete. If no test covers the changed code, write one first.

**Why:** Amit explicitly asked for this, changes that "work" without test confirmation are not done.

**How to apply:** Every time. No exceptions. If tests don't exist yet, create them. Use `@pytest.mark.integration` for tests that need live APIs so they can be skipped in CI. If the change touches fiat-lux-agents, also run `.venv/bin/python3 -m pytest ~/repos/fiat-lux-agents/tests/ -x -q`. When new tests are written, post a comment on issue #15 (test suite tracking), even if it's closed.
