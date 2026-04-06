# Code Style Rules

## File Organization
- Separate HTML, CSS, and JS into their own files — never inline styles or scripts
- Templates live in `agents/<agent>/templates/`, static assets in `static/js/` and `static/css/`
- Bump JS version query strings (e.g. `?v=40`) when editing JS files so browsers pick up changes

## Project Structure
- `agents/` — feature modules (auth, create, explore, itinerary, trips, pages, admin, common)
- `static/` — frontend assets (js, css)
- `tests/` — test scripts
- `scripts/` — one-off utility scripts
- Keep root clean — no new files at root unless essential (app.py, auth.py, database.py are intentional)

## Server
- Flask app with blueprint-per-feature structure (`agents/*/routes.py`)
- `app.py` — Flask factory, registers all blueprints, handles `before_request`
- Blueprint routes are thin wrappers; business logic lives in `agents/*/handler.py`
- Sessions: Flask signed cookie (`session["user_id"]`), requires `SECRET_KEY` env var
- Start locally: `AUTH_DISABLED=true SECRET_KEY=dev python3 app.py` or `./dev.sh start`
- Production: gunicorn via `render.yaml`

## LLM / Agent Design
- Keep LLM calls out of route handlers — they belong in agent handlers or mapper
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

## Naming
- Always write out "fiat-lux-agents" in full — in code, comments, docs, issues, and PR descriptions
- Never abbreviate it (e.g. "fla") in any written artifact

## Code Style
- Python style is enforced by **ruff** — run `ruff check .` and `ruff format .` before committing
- CI will fail if ruff violations exist (both lint and format checks run in GitHub Actions)
- To auto-fix: `ruff check --fix . && ruff format .`
- Config lives in `pyproject.toml` under `[tool.ruff]`

## Code Quality
- No hardcoded model names in logic — use named constants or comments marking the choice
- No hardcoded config values, URLs, paths, or magic strings — use environment variables or named constants
- Write comments explaining *why*, not just *what*
- Keep handlers small — blueprint routes thin, handler.py contains logic
- Keep files focused and short — if a file is getting long, split by responsibility
- Prefer reusable helpers over copy-pasted logic — if the same pattern appears twice, extract it
- No duplicate logic across handlers — shared behavior belongs in `agents/common/`
