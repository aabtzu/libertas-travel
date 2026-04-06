# Code Style Rules

## File Organization
- Separate HTML, CSS, and JS into their own files — never inline styles or scripts
- Templates live in `agents/<agent>/templates/`, static assets in `static/js/` and `static/css/`
- Bump JS version query strings (e.g. `?v=40`) when editing JS files so browsers pick up changes

## Project Structure
- `agents/` — feature modules (create, itinerary, explore, common)
- `static/` — frontend assets (js, css)
- `tests/` — test scripts
- `scripts/` — one-off utility scripts
- Keep root clean — no new files at root unless essential (server.py, auth.py, database.py are intentional)

## Server
- Currently a raw Python `HTTPServer` — no framework
- All endpoints in `server.py`; business logic delegated to `agents/*/handler.py`
- Plan to migrate to Flask (#9) — avoid deepening coupling to raw HTTPServer patterns

## LLM / Agent Design
- Keep LLM calls out of `server.py` — they belong in agent handlers or mapper
- Model selection: Haiku for speed/cost tasks (classification, filtering), Sonnet for quality tasks (parsing, chat, reasoning)
- Always use current model IDs — check `memory/MEMORY.md` for confirmed working models
- Cache LLM results where possible (see `_origin_check_cache` in mapper.py)

## Frontend
- Vanilla JS, no framework
- `create.js` handles the trip editor — versioned with `?v=N` on script tag
- Use `novalidate` on forms where JS handles validation

## Auth
- Controlled by `AUTH_DISABLED=true` env var (set automatically in `dev.sh`)
- Never hardcode credentials

## Map / Geocoding
- Map data cached in DB — changes to itinerary require explicit or auto-triggered regen
- `is_home_location=True` on an item excludes it from map
- Auto-regen triggers when `is_home_location` flags change on save

## Testing
- All tests live in `tests/` and use pytest — never write one-off scripts
- After any code change, run the relevant tests: `.venv/bin/python3 -m pytest tests/ -x -q` (or `./dev.sh test`)
- After adding a feature or fixing a bug, write or update a test that covers it
- Never claim a change is done without running tests and confirming they pass
- If no test exists for the changed code, create one before marking the task complete
- Tests must be repeatable: no hardcoded local paths, no reliance on live APIs unless marked `@pytest.mark.integration`
- If a change touches fiat-lux-agents (`~/repos/fiat-lux-agents`), also run its tests: `.venv/bin/python3 -m pytest ~/repos/fiat-lux-agents/tests/ -x -q`
- Whenever new tests are written, add a comment to issue #15 (test suite tracking) — even if the issue is closed

## Code Quality
- No hardcoded model names in logic — use named constants or comments marking the choice
- Write comments explaining *why*, not just *what*
- Keep handlers small — server.py routes, handler.py logic
