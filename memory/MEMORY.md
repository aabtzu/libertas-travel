# Libertas Memory

## Project Overview
Travel itinerary app. Python HTTP server (no framework), SQLite DB, vanilla JS frontend, Leaflet maps.
Plan: migrate server to Flask (#9) and LLM layer to fiat-lux-agents (#8).

## Dev Setup
- Run locally: `PORT=8008 AUTH_DISABLED=true python3 server.py` or `PORT=8008 bash dev.sh bg`
- Logs: `tail -f /tmp/libertas.log`
- `dev.sh` sets `AUTH_DISABLED=true` automatically — no login needed locally
- Default port in dev.sh is 5555; override with `PORT=`

## Key Files
- `server.py` — monolithic HTTP handler, all API endpoints
- `agents/create/handler.py` — trip create/save/publish logic
- `agents/create/templates/create.html` — trip editor UI
- `static/js/create.js` — trip editor JS (versioned, currently v40)
- `agents/itinerary/mapper.py` — map generation and filtering
- `agents/itinerary/models.py` — ItineraryItem, Location, Itinerary dataclasses
- `geocoding_worker.py` — async background map geocoding queue
- `auth.py` — auth with `AUTH_DISABLED` env var support
- `database.py` — SQLite via raw SQL

## Architecture Notes
- Map data is cached in `itinerary_data['map_data']` in DB
- Map regen: POST `/api/retry-geocoding` with `{link: "..."}` clears cache and re-queues
- `is_home_location=True` on an ItineraryItem skips it from map display
- Auto-regen triggers on save when `is_home_location` flags change (handler.py `save_trip_handler`)
- LLM transport filter uses `claude-haiku-4-5-20251001` (fixed from dead model `claude-3-5-haiku-20241022`)

## Recent Changes (2026-03-09)
- Added "Exclude from map" checkbox to item edit modal → sets `is_home_location`
- Fixed `_create_itinerary_item` hardcoding `is_home_location=False` (now reads from item data)
- Fixed dead LLM model in mapper.py (`claude-3-5-haiku-20241022` → `claude-haiku-4-5-20251001`)
- Auto-trigger map regen on save when `is_home_location` changes
- Time input: added `novalidate` to item form so typed times (e.g. 8:01) are accepted; `step="900"` kept for spinner

## Model Usage
- Haiku (`claude-haiku-4-5-20251001`) — fast/cheap tasks: LLM location checks in mapper
- Sonnet (`claude-sonnet-4-20250514`) — quality tasks: itinerary parsing, chat

## Active Project Notes
- [project_document_parser.md](project_document_parser.md) — DocumentParserBot: use fla `feature/document-model` + matching libertas branch when doing this work

## Behavior Rules
- [feedback_testing.md](feedback_testing.md) — always run pytest before claiming a change is done

## Shorthands
- "fla" = fiat-lux-agents (use in conversation, not in docs/issues/code)

## Open Issues
- [shorthand_fla.md](shorthand_fla.md) — "fla" = fiat-lux-agents shorthand
- #9 Flask rewrite, #8 fiat-lux-agents integration, #7 ICS feed, #6 Codespaces, #5 Render geocoding, #3 email import, #2 photo discovery, #1 hybrid recs
