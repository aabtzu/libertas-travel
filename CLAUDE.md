# Code Style Rules

## File Organization
- Separate HTML, CSS, and JS into their own files — never inline styles or scripts
- Templates live in `agents/<agent>/templates/`, static assets in `static/js/` and `static/css/`
- Bump JS version query strings (e.g. `?v=40`) when editing JS files so browsers pick up changes

## CSS / Visual Style
- **No gradients** — use solid colors only. Gradients are not wanted anywhere in the UI.
- Color palette: `#1a1a2e` (dark navy, hero/dark sections), `#667eea` (purple accent, buttons, icons), `#f0c674` (gold highlight), white cards on `#f8f9fa` backgrounds
- Hover states: darken the solid color (e.g. `#667eea` → `#5a6fd6`), never add a gradient on hover

## Project Structure
- `agents/` — feature modules (auth, create, explore, itinerary, trips, pages, admin, common)
- `static/` — frontend assets (js, css)
- `tests/` — test scripts
- `scripts/` — one-off utility scripts
- Keep root clean — no new files at root unless essential (app.py, auth.py are intentional; database is a package at `database/`)

## Deploy Discipline
- **Test locally before pushing to Render** — Render redeploys take several minutes; don't push for every small change
- Workflow: implement → test locally (`./dev.sh start`) → get user approval → then push
- Batch related changes into one push rather than pushing after each individual fix
- Only push when: the user explicitly says to, or a coherent feature/fix is complete and locally verified

## No Manual Production Steps
- **Never require manual actions on the production server** — no SSH, no copy-pasting data into a console
- Any production data setup (demo trips, seed data, config) must be handled by a script or admin route
- Demo/seed trips are owned by the `demo` system user and seeded via `POST /api/admin/seed` (protected by `X-Admin-Key: $SECRET_KEY`)
- Calling the seed endpoint on Render: `curl -X POST https://<host>/api/admin/seed -H "X-Admin-Key: $SECRET_KEY"`
- Re-seed (overwrite existing): add `?force=true` to the above URL
- Fixtures live in `tests/fixtures/` — one `.txt` file per demo trip

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

## JS Shared Constants — Single Source of Truth
Every shared lookup table, config object, or utility must be defined **once** and imported/referenced everywhere else. Defining the same data in two places is never acceptable — it causes silent drift and wastes time chasing down which copy is stale.

**Current canonical locations — do not redefine these anywhere:**
- `CATEGORY_ICONS` — defined in `static/js/main.js`; maps category → FontAwesome class
- `CATEGORY_COLORS` — defined in `static/js/main.js`; maps category → hex color
- `LibertasUpload` — defined in `static/js/main.js`; allowed file extensions, accept attr, isAllowed()
- `LibertasChat` — defined in `static/js/main.js`; chat input history + cancel support
- `LibertasMap` — defined in `static/js/main.js`; Leaflet tile config

**Rules:**
- If you need a new shared constant, add it to `main.js` (loaded on every page) and reference the global
- If a file has its own local copy of something already in `main.js`, delete the local copy — the global wins
- Leave a comment `// defined in main.js` where the local copy was, so the next reader knows it's intentional
- For Python: `CATEGORY_ICONS` and `CATEGORY_COLORS` live in `agents/common/categories.py`; import from there — never redefine locally. File-type lists live in `agents/create/file_parsers.py`

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
- Prefer reusable helpers over copy-pasted logic — if the same pattern appears twice, extract it
- No duplicate logic across handlers — shared behavior belongs in `agents/common/`

## SQL Style
- SQL queries must be defined as module-level named constants, never inline inside functions
- Name them descriptively in SCREAMING_SNAKE_CASE, e.g. `_SQL_INSERT_TRIP`, `_SQL_GET_USER_BY_ID`
- Functions call the constant: `cursor.execute(_SQL_INSERT_TRIP, (...))`
- This applies to both PostgreSQL and SQLite variants — define separate constants when the SQL differs

## File Length
- Target: no file longer than 500 lines; hard limit 800 lines
- If a file exceeds 500 lines, split it by responsibility before adding more code
- Python: split by domain (e.g. `trips.py`, `users.py`); JS: split by feature area (e.g. `create-chat.js`, `create-map.js`)
- Prefer many small focused files over one large file
