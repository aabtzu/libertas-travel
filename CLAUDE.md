# CLAUDE.md

Guidance for AI assistants (and humans) working in this repo. Read this before
touching code. The rules here are enforced by CI where possible.

---

# What This Project Is

Libertas is a travel itinerary web app: import or create trips, edit them in a
browser editor, view them as list / grid / calendar / map, and share them as
public pages. Flask backend, vanilla JS frontend, SQLite locally and PostgreSQL
on Render, Claude for parsing and chat via
[fiat-lux-agents](https://github.com/aabtzu/fiat-lux-agents).

Production: `https://libertas-travel.onrender.com`

---

# Repository Map

```
app.py                     Flask factory: registers blueprints, runs db.init_db(), before_request hook
dev.sh                     Local dev helper: start | bg | stop | logs | test
render.yaml                Render deploy config (gunicorn, 2 workers, 1GB disk at /var/data)
pyproject.toml             ruff + pytest config, project metadata
requirements.txt           Runtime deps (installed by Render's buildCommand)
.file_size_baseline.toml   Grandfathered oversized files (currently empty: nothing is over 800)

agents/                    One package per feature. routes.py is thin, handler.py has the logic.
  admin/                   Diagnostics, seeding, bulk regen, venue/user/trip admin (X-Admin-Key)
  auth/                    Blueprint shim over fiat_lux_agents.auth + credentials.py helpers
  common/                  Shared code: llm.py, categories.py, flask_utils.py, templates.py, venue_capture.py
  create/                  Trip editor backend: chat, file upload, URL import, save/publish
  email/                   SendGrid Inbound Parse webhook: forwarded booking emails to trip items
  explore/                 Venue search and explore chat (owns its own static/ and templates/)
  itinerary/               Parser, models, mapper, geocoder, geocoding worker, web views, CLI
  pages/                   HTML page routes, /app-config.js, profile and recommendation views
  trips/                   Trip CRUD, sharing, ICS export, write-up generation, link resolver

database/                  Package (not a module). Split by domain, __init__.py re-exports everything.
  connection.py            get_db/get_connection, init_db, DDL constants, Postgres vs SQLite switch
  users.py trips.py drafts.py sharing.py venues.py

static/                    Site-wide frontend assets
  js/  css/  images/  favicon.svg

tests/                     pytest suite (21 files, ~450 tests). conftest.py provides app/client fixtures.
  fixtures/                One .txt or .json per demo trip, also used by the seed endpoint

scripts/                   CI checks and one-off utilities
  check_file_size.py check_no_em_dashes.py check_marketing_copy.py
  import_venues.py geocode_venues.py check_users.sh launch-stats.sh test_parse.py

docs/                      fiat-lux-agents.md, recommendations.md, future-email-import.md
memory/                    Working notes. MEMORY.md predates the Flask rewrite and is largely stale:
                           trust the code and this file over it.
data/                      Gitignored by pattern but tracked by exception: venues_seed.csv,
                           airline_codes.csv, style_references/
```

Notes on things that surprise people:

- There is **no `auth.py`, `server.py`, `database.py`, or `geocoding_worker.py` at
  the root**. Those were the pre-Flask layout. Auth is `agents/auth/routes.py`,
  the DB is the `database/` package, the worker is
  `agents/itinerary/geocoding_worker.py`.
- `agents/explore/` is the one feature that keeps its own `static/` and
  `templates/` subdirectories. Everything else uses site-wide `static/` and its
  own `templates/` for HTML only.

---

# Running It

```bash
source ~/.profile && ./dev.sh start   # foreground on :8080
./dev.sh bg                           # background, logs at /tmp/libertas.log
./dev.sh stop
./dev.sh logs
./dev.sh test                         # pytest tests/ -x -q
```

The `source ~/.profile` step is required so `ANTHROPIC_API_KEY` and other
secrets are inherited: `.profile` is where they live, and the Bash sandbox does
not auto-load it.

`dev.sh` sets `AUTH_DISABLED=true`, `FLASK_DEBUG=true`, and a throwaway
`SECRET_KEY`. With auth disabled, `flask_utils.load_current_user` defaults
`g.user_id` to `1`, so user 1 must exist in the local DB.

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `SECRET_KEY` | Yes | Flask signed sessions. Also doubles as the `X-Admin-Key` admin secret. |
| `ANTHROPIC_API_KEY` | Yes for LLM features | Claude API key |
| `AUTH_DISABLED` | No | `true` skips login (dev only, set by `dev.sh`) |
| `DATABASE_URL` | No | PostgreSQL URL. Absent means SQLite. |
| `OUTPUT_DIR` | No | Where generated trip HTML lands (default `./output`, `/var/data/output` on Render) |
| `PORT` | No | Default 8080 |
| `SESSION_LIFETIME_DAYS` | No | Default 90 |
| `GOOGLE_MAPS_API_KEY` | No | Explore page map embed |
| `INVITE_CODE` | No | Gate on registration (consumed by the fiat-lux-agents auth blueprint) |
| `APP_URL`, `FROM_EMAIL` | No | Password-reset email links and sender |
| `FLASK_DEBUG` | No | `true` enables the reloader |

---

# Architecture

## Request flow

`app.py:create_app()` registers seven blueprints in this order: `pages`, `auth`,
`trips`, `create`, `explore`, `admin`, `email`. It then calls `db.init_db()`,
which is idempotent and doubles as the migration path (every schema change is an
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` style DDL constant in
`database/connection.py`). A `before_request` hook populates `g.user_id`,
`g.username`, and `g.auth_disabled`.

Blueprint routes are thin: parse the request, call a handler, wrap the result in
`json_ok` / `json_err`. Handlers return `(dict, status)` tuples and contain the
business logic. Never put an LLM call in a route.

## API surface

Trips (`agents/trips/routes.py`, all `@require_auth` unless noted):

```
GET  /api/trips/list                          POST /api/trips/create
GET  /api/trips/<link>/data                   POST /api/trips/<link>/save
GET  /api/trips/<link>/export                 POST /api/trips/<link>/publish
GET  /api/trips/<link>/calendar.ics  (public with ?token=)
GET  /api/trips/<link>/calendar-subscribe-url POST /api/trips/<link>/items
GET  /api/calendar/subscribe-url              POST /api/trips/clone-ideas
GET  /api/calendar/all.ics           (public with ?token=)
GET  /api/trip/<link>/can-edit                POST /api/delete-trip
GET  /api/map-status                          POST /api/copy-trip
GET  /api/trips/<link>/card-icon              POST /api/rename-trip
GET  /api/user/me                             POST /api/update-trip
GET  /api/user/profile                        POST /api/retry-geocoding
                                              POST /api/share-trip
                                              POST /api/toggle-public
                                              POST /api/toggle-archived
                                              POST /api/trips/<link>/writeup
                                              POST /api/trips/<link>/fill-links
                                              POST /api/user/extract-style
                                              POST /api/user/save-profile
```

Create: `POST /api/create/chat`, `/api/create/upload-plan`, `/api/upload`, `/api/import-url`
Explore: `GET /api/explore/venues`, `POST /api/explore/chat`, `POST /api/explore/save-venue`
Email: `POST /api/email/inbound` (SendGrid webhook, always returns 200 so SendGrid does not retry)

Pages (`agents/pages/routes.py`): `/`, `/how-it-works`, `/about`, `/explore`,
`/login`, `/register`, `/forgot-password`, `/reset-password`, `/profile`,
`/trips`, `/create`, `/admin`, `/app-config.js`, plus the three public share
formats: `/<trip>.html` (itinerary), `/r/<name>` (recommendation),
`/w/<name>` (write-up). See `docs/recommendations.md`.

Admin (`agents/admin/routes.py`), every one gated on `X-Admin-Key: $SECRET_KEY`:

```
GET  /api/debug
POST /api/admin/seed              (add ?force=true to overwrite)
POST /api/admin/retry-geocoding   POST /api/admin/add-trip
POST /api/admin/regen-stuck-trips POST /api/admin/add-venues
POST /api/admin/delete-venue      POST /api/admin/delete-trip
POST /api/admin/set-user-email    POST /api/admin/delete-user
POST /api/regenerate-all-trips
```

## Templating

There is no Jinja rendering of app pages. HTML files under
`agents/*/templates/` are read as text by `templates.py` helpers
(`get_template`, `get_static_css`, `get_static_js`) and filled with
`str.format()`, then returned via `Response(..., mimetype="text/html")`. That is
why literal braces in those files are doubled (`{{` / `}}`). Nav markup comes
from `agents/common/templates.py:get_nav_html(active_page)`.

## Data model

Two tables that matter: `users` and `trips`. A trip row carries `link` (the
public slug, always with a `.html` suffix in the DB), `title`, `dates`, `days`,
`map_status`, `map_error`, `itinerary_data` (JSON/JSONB, the whole itinerary
including cached `map_data`), and the flags `is_public`, `is_draft`,
`is_archived`, `trip_type` (`itinerary` or `recommendation`). Venues live in
their own table, seeded from `data/venues_seed.csv`.

Dataclasses for parsing live in `agents/itinerary/models.py`: `Location`,
`ItineraryItem`, `Itinerary`.

---

# Code Style Rules

## File Organization
- Separate HTML, CSS, and JS into their own files, never inline styles or scripts
- Templates live in `agents/<agent>/templates/`, static assets in `static/js/` and `static/css/`
- Bump JS version query strings (e.g. `?v=40`) when editing JS files so browsers pick up changes.
  Current versions: `main.js?v=7`, `create.js?v=59`, `trip.js?v=12`, `trips.js?v=10`,
  `upload.js?v=15`, `create-upload.js?v=8`, `calendar-export.js?v=5`. Grep the templates
  for the exact tag you are changing rather than trusting this list.

## CSS / Visual Style
- **No gradients**, use solid colors only. Gradients are not wanted anywhere in the UI.
- **No browser dialogs**, never use `alert()`, `confirm()`, or `prompt()`. Use
  `LibertasModal.confirm()` / `LibertasModal.alert()` from `static/js/main.js`:
  white card, rounded corners, `#667eea` accent buttons, Escape to dismiss.
- Color palette: `#1a1a2e` (dark navy, hero/dark sections), `#667eea` (purple accent,
  buttons, icons), `#f0c674` (gold highlight), white cards on `#f8f9fa` backgrounds
- Hover states: darken the solid color (e.g. `#667eea` to `#5a6fd6`), never add a gradient on hover

## Project Structure
- `agents/` feature modules (auth, create, explore, itinerary, trips, pages, admin, email, common)
- `static/` frontend assets (js, css, images)
- `tests/` pytest suite
- `scripts/` CI checks and one-off utilities
- Keep root clean: no new files at root unless essential. `app.py` is the only
  intentional root Python file; `database` is a package at `database/`.

## Deploy Discipline
- **Test locally before pushing to Render**, Render redeploys take several minutes
- Workflow: implement, test locally (`./dev.sh start`), get user approval, push, verify on Render
- **After every push, verify the change works on Render**: curl the affected API endpoint or open the page
- Production URL: `https://libertas-travel.onrender.com` (e.g. explore at `/explore.html`)
- Smoke-test the explore chat on Render:
  `curl -X POST https://libertas-travel.onrender.com/api/explore/chat -H "Content-Type: application/json" -d '{"message": "restaurants in Paris", "history": []}'`
- Batch related changes into one push rather than pushing after each individual fix
- Only push when: the user explicitly says to, or a coherent feature/fix is complete and locally verified

## No Manual Production Steps
- **Never require manual actions on the production server**: no SSH, no copy-pasting data into a console
- Any production data setup (demo trips, seed data, config) must be handled by a script or admin route
- Demo/seed trips are owned by the `demo` system user and seeded via
  `POST /api/admin/seed` (protected by `X-Admin-Key: $SECRET_KEY`)
- Calling the seed endpoint on Render:
  `curl -X POST https://<host>/api/admin/seed -H "X-Admin-Key: $SECRET_KEY"`
- Re-seed (overwrite existing): add `?force=true` to the above URL
- Fixtures live in `tests/fixtures/`, one file per demo trip

## Server
- Flask app with blueprint-per-feature structure (`agents/*/routes.py`)
- `app.py` is the Flask factory: registers all blueprints, runs migrations, handles `before_request`
- Blueprint routes are thin wrappers; business logic lives in `agents/*/handler.py`
- Handlers return `(result_dict, status_code)`; routes translate that to `json_ok` / `json_err`
- Sessions: Flask signed cookie (`session["user_id"]`), requires `SECRET_KEY` env var
- Auth decorator: `@require_auth` from `agents/common/flask_utils.py` (401 for `/api/`, redirect for pages)
- Start locally: `source ~/.profile && ./dev.sh start`
- Production: gunicorn via `render.yaml`

## LLM / Agent Design
- Keep LLM calls out of route handlers, they belong in agent handlers or mapper
- **`agents/common/llm.py` is the single source of truth for model IDs.** Import
  `SONNET` and `HAIKU` from there; never write a model string inline. Current values:
  - `SONNET = "claude-sonnet-4-6"` for quality tasks: parsing, chat, reasoning
  - `HAIKU = "claude-haiku-4-5-20251001"` for speed/cost tasks: classification, filtering, enrichment
- Construct clients with `make_llm()` / `make_summary_bot()`, both thin wrappers over
  fiat-lux-agents `LLMBase` / `SummaryBot`. See `docs/fiat-lux-agents.md`.
- Note: `memory/MEMORY.md` lists older model IDs and a pre-Flask file layout. It is
  stale. `agents/common/llm.py` wins.
- Cache LLM results where possible (see `_origin_check_cache` in `agents/itinerary/mapper.py`)

## Frontend
- Vanilla JS, no framework, no build step
- Page scripts load after `/app-config.js` and `static/js/main.js`, in that order.
  `main.js` defines the shared globals every other file depends on.
- `create.js` handles the trip editor and is split across `create-render.js`,
  `create-items.js`, `create-upload.js`, `create-save.js`, `create-chat.js`,
  `create-dragdrop.js`, `create-grid.js`, `create-map.js`. All versioned with `?v=N`.
- Use `novalidate` on forms where JS handles validation

## JS Shared Constants, Single Source of Truth
Every shared lookup table, config object, or utility must be defined **once** and
imported/referenced everywhere else. Defining the same data in two places is never
acceptable: it causes silent drift and wastes time chasing down which copy is stale.

**Python owns the shared data.** `/app-config.js` (served by
`agents/pages/routes.py:app_config_js`) serializes Python constants into globals
the frontend reads. There is no JS copy to keep in sync, and there must never be one.

Served from Python via `/app-config.js`:
- `window.CATEGORY_ICONS` from `agents/common/categories.py`
- `window.CATEGORY_COLORS` from `agents/common/categories.py`
- `window.LIBERTAS_ALLOWED_EXTENSIONS` from `agents/create/file_parsers.py:SUPPORTED_EXTENSIONS`

Defined in `static/js/main.js` (loaded on every page):
- `LibertasUpload` accept attribute and `isAllowed()`, built from `LIBERTAS_ALLOWED_EXTENSIONS`
- `LibertasChat` chat input history and cancel support
- `LibertasMap` Leaflet tile config
- `LibertasModal` custom confirm/alert dialogs
- `escapeHtml`, `formatTime12Hour`, `mdToHtml`, `initMobileNav`, `initMobileSidebar`

**Rules:**
- A new Python-to-JS constant goes in `/app-config.js`. A new JS-only helper goes in `main.js`.
- If a file has its own local copy of something already global, delete the local copy
- Leave a comment `// defined in main.js` (or `// from /app-config.js`) where the local copy was
- For Python: `CATEGORY_ICONS`, `CATEGORY_COLORS`, `CANONICAL_CATEGORIES`,
  `TRAVEL_CATEGORIES`, `normalize_category`, `get_trip_start_date`, and
  `get_trip_date_range` all live in `agents/common/categories.py`. Import from there,
  never redefine locally. File-type lists live in `agents/create/file_parsers.py`.

## Auth
- Controlled by `AUTH_DISABLED=true` env var (set automatically in `dev.sh`)
- `agents/auth/routes.py` is a shim: it calls `fiat_lux_agents.auth.make_auth_blueprint`
  with this app's DB connection, invite code, and mail settings. Login, register,
  logout, and password reset all live in the plugin, not here.
- `agents/auth/credentials.py` holds the local validation and registration helpers
- Never hardcode credentials

## Map / Geocoding
- Map data is cached in `itinerary_data["map_data"]` in the DB
- Geocoding runs on a background thread queue (`agents/itinerary/geocoding_worker.py`)
  using Nominatim; trips carry a `map_status` of pending / processing / complete / error
- Regenerate: `POST /api/retry-geocoding` with `{"link": "..."}` clears the cache and re-queues
- `is_home_location=True` on an item excludes it from the map
- Auto-regen triggers on save when `is_home_location` flags change
  (`agents/create/handler.py:_trigger_map_regen`)
- `MAX_GEOCODE_LOCATIONS = 50` caps work per trip

## Testing
- All tests live in `tests/` and use pytest, never write one-off scripts
- After any code change, run the relevant tests: `.venv/bin/python3 -m pytest tests/ -x -q` (or `./dev.sh test`)
- `conftest.py` gives you an `app` fixture (auth disabled, dummy API key, user 1 ensured)
  and a `client` Flask test client. A session-scoped autouse fixture sweeps stray test
  trips by title; if you add a new test trip title, add it to `_TEST_TRIP_TITLES`.
- Tests that need a live key are marked `@pytest.mark.integration` and are excluded in CI
  (`pytest tests/ -m "not integration" -q`)
- After adding a feature or fixing a bug, write or update a test that covers it
- Never claim a change is done without running tests and confirming they pass
- If no test exists for the changed code, create one before marking the task complete
- Tests must be repeatable: no hardcoded local paths, no reliance on live APIs unless marked integration
- If a change touches fiat-lux-agents (`~/repos/fiat-lux-agents`), also run its tests:
  `.venv/bin/python3 -m pytest ~/repos/fiat-lux-agents/tests/ -x -q`
- Whenever new tests are written, add a comment to issue #15 (test suite tracking), even if the issue is closed
- **Preserve coverage during refactors.** When splitting a file, renaming a module, or
  moving logic around, every conditional branch (especially `if/elif/else` chains for
  file types, error paths, or feature flags) must still be exercised by a test after the
  refactor. If you find a branch that has no test, write one *before* you refactor: that
  turns the branch into a tripwire. The PNG-upload regression in commit `1ef25bb`
  (2517-line handler split) silently dropped the vision-API call for weeks because no test
  covered image uploads. Don't repeat that.
- Refactor checklist: list the conditional branches in the old file, run `pytest -k <name>`
  against each, refactor, re-run. If a branch had no test, add one *first*.

## Naming
- Always write out "fiat-lux-agents" in full, in code, comments, docs, issues, and PR descriptions
- Never abbreviate it (e.g. "fla") in any written artifact

## Writing Style
- **No em dashes (—) anywhere.** Not in code, not in comments, not in docstrings, not in
  commit messages, not in PR descriptions, not in user-facing copy on the site, and not in
  chat replies to the user. Use a hyphen (-), a comma, a colon, parentheses, or split into
  two sentences.
- This rule exists because em dashes are the strongest "AI wrote this" tell. The codebase is
  meant to read as human-authored.
- En dashes (–) for numeric ranges are fine; em dashes (—) are not.
- The hyphen-minus character (-) is the only dash to use in prose.
- **Enforced by CI**: `scripts/check_no_em_dashes.py`. Any em dash outside the allowlist (the
  rule docs themselves and a couple of regex char classes that match user-typed dashes) fails
  the build. To run locally: `.venv/bin/python3 scripts/check_no_em_dashes.py`

## UX Copy Style (user-facing strings)
- **Concrete verbs only.** Describe what the feature *does*, not how it feels.
  "Search restaurants by city" beats "Discover amazing places."
- **No marketing puffery.** Banned phrases (CI-enforced): "AI-powered", "AI-driven",
  "agentic", "intelligent agents", "seamlessly", "effortlessly", "effortless",
  "discover amazing", "curated thousands", "powerful tools", "your journey", "unlock",
  "elevate your", "transform your", "we've got you covered", "natural language"
  (when used as a feature name).
- **No three-step marketing strips.** "Start Your Trip / Discover & Refine / View & Share"
  is the AI-blog template. Use a single sentence or a real walkthrough with screenshots.
- **One sentence per idea.** If a copy block runs to three sentences explaining the same
  feature, cut two of them.
- **No "AI" as a brand layer.** Mention the LLM only when it's load-bearing for the user's
  mental model (e.g. "Chat to adjust" implies it; "AI-powered chat assistant" doesn't add anything).
- **Don't praise the product.** "Libertas is a trip planner" beats "Libertas is your AI travel companion."
- **Enforced by CI**: `scripts/check_marketing_copy.py`. Allowlist via the script's
  ALLOWLIST_FILES. To run locally: `.venv/bin/python3 scripts/check_marketing_copy.py`

## Code Style
- Python style is enforced by **ruff**: run `ruff check .` and `ruff format .` before committing
- Rule set: `E`, `W`, `F`, `I` (isort), `B` (bugbear), `UP` (pyupgrade). Line length 100,
  `E501` ignored because the formatter owns wrapping. Config in `pyproject.toml`.
- CI will fail if ruff violations exist (both lint and format checks run in GitHub Actions)
- To auto-fix: `ruff check --fix . && ruff format .`

## Code Quality
- No hardcoded model names in logic, import `SONNET` / `HAIKU` from `agents/common/llm.py`
- No hardcoded config values, URLs, paths, or magic strings, use environment variables or named constants
- Write comments explaining *why*, not just *what*
- Keep handlers small: blueprint routes thin, `handler.py` contains logic
- Prefer reusable helpers over copy-pasted logic, if the same pattern appears twice, extract it
- No duplicate logic across handlers, shared behavior belongs in `agents/common/`

## Grep before you answer
- **When the user asks "do we already have X?", grep the codebase first, then answer.** A
  2-second `grep -rn` beats a confident wrong answer every time. The `.ics` export incident
  on 2026-05-05 is the cited cautionary tale: I claimed there was no export and started
  rebuilding it. There was already a working export shipped Dec 2025 (`agents/trips/ics.py`,
  route `/api/trips/<link>/calendar.ics`), and `git log --oneline | grep -i ics` would have
  surfaced it instantly.
- Same rule for "is there a library that does this?": check `requirements.txt` and search for
  known utilities before hand-rolling.
- Same rule when proposing a new file or function: grep for similar names first to avoid duplication.

## SQL Style
- SQL queries must be defined as module-level named constants, never inline inside functions
- Name them descriptively in SCREAMING_SNAKE_CASE, e.g. `_SQL_INSERT_TRIP`, `_SQL_GET_USER_BY_ID`
- Functions call the constant: `cursor.execute(_SQL_INSERT_TRIP, (...))`
- This applies to both PostgreSQL and SQLite variants, define separate constants when the SQL differs
- Placeholders differ by backend (`%s` on Postgres, `?` on SQLite). Branch on
  `database.connection.USE_POSTGRES` rather than assuming one.
- Schema DDL is also constants, in `database/connection.py`, applied by `init_db()`

## File Length
- Target: no file longer than 500 lines; hard limit 800 lines
- If a file exceeds 500 lines, split it by responsibility before adding more code
- Python: split by domain (e.g. `trips.py`, `users.py`); JS: split by feature area
  (e.g. `create-chat.js`, `create-map.js`)
- Prefer many small focused files over one large file
- **Enforced by CI**: `scripts/check_file_size.py`. New files over 800 lines fail the build.
- `.file_size_baseline.toml` is currently **empty**: every file in the repo is under the hard
  limit. Keep it that way. Do not add a baseline entry without a written justification in your PR.
- Files currently closest to the soft limit and worth splitting before growing:
  `static/css/create.css` (743), `static/css/main.css` (741), `static/js/main.js` (703),
  `static/css/create-views.css` (654), `static/js/create.js` (649),
  `agents/itinerary/templates.py` (620), `tests/test_calendar_export.py` (617),
  `agents/explore/static/css/explore-cards-panel.css` (602), `agents/trips/routes.py` (591),
  `static/js/create-chat.js` (579), `database/venues.py` (553)

---

# Pre-Push Checklist

CI (`.github/workflows/test.yml`) runs these on every push and PR to `main`, in order.
Run them locally first:

```bash
ruff check . && ruff format --check .
.venv/bin/python3 scripts/check_file_size.py
.venv/bin/python3 scripts/check_no_em_dashes.py
.venv/bin/python3 scripts/check_marketing_copy.py
.venv/bin/python3 -m pytest tests/ -m "not integration" -q
```

Then push, then verify the change on Render.
