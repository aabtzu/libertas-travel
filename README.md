# Libertas

A modern travel itinerary web application for planning, organizing, and visualizing your trips.

Named after the Roman goddess of liberty, alongside Abeona (goddess of outward journeys) and Adeona (goddess of safe returns), Libertas helps you travel freely.

## Features

- **Import trips** from PDF, Excel, Google Drive, TripIt, or any web page
- **Create trips** from scratch with an AI-powered chat assistant
- **Export/Import** trips as JSON for backup and sharing
- **Multiple views**: List, Grid, Calendar, and interactive Map
- **Edit trips** inline with drag-and-drop reordering
- **Share trips** with other users or make them public
- **Recommend places** — build sharable recommendation collections from Explore, share as structured view or AI-generated narrative
- **AI write-ups** — generate a readable narrative from your trip ideas, with links and maps
- **Explore destinations** — discover restaurants, hotels, and attractions via AI chat
- **Background geocoding** — locations geocoded asynchronously with Nominatim

## Live demo

Try it: [https://libertas-travel.onrender.com](https://libertas-travel.onrender.com)

## Quick Start

```bash
# Set up a virtualenv (one-time)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set required environment variables
export ANTHROPIC_API_KEY=your_api_key
export SECRET_KEY=any-string-for-session-signing

# Start the dev server (auth disabled, port 8080)
./dev.sh start
```

Then open [http://localhost:8080](http://localhost:8080).

To stop or run in background:

```bash
./dev.sh stop      # kill any server on the port
./dev.sh bg        # start in background, logs at /tmp/libertas.log
./dev.sh test      # run the test suite
```

## Project Structure

```
libertas/
├── app.py                    # Flask app factory, blueprint registration
├── auth.py                   # User credentials and registration
├── database/                 # SQLite / PostgreSQL operations (connection, users, trips, venues…)
├── geocoding_worker.py       # Background geocoding service
├── agents/
│   ├── auth/                 # Login, register, logout routes
│   ├── trips/                # Trip CRUD, export, ICS, geocoding, write-up, link resolver
│   ├── create/               # Trip creation chat, file upload routes
│   ├── explore/              # Venue discovery routes and handler
│   ├── pages/                # HTML page routes (home, trips, create, etc.)
│   ├── admin/                # Debug and admin utility routes
│   ├── itinerary/            # Parser, mapper, models, web view
│   └── common/               # Shared Flask utils, templates
├── static/
│   ├── css/
│   └── js/
└── data/
    ├── venues_seed.csv       # Curated venue database
    └── airline_codes.csv     # Airline display names for flight parsing
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for AI features |
| `SECRET_KEY` | Yes | Flask session signing key |
| `AUTH_DISABLED` | No | Set to `true` to skip login in dev |
| `OUTPUT_DIR` | No | Path for generated HTML files (default: `./output`) |
| `DATABASE_URL` | No | PostgreSQL URL (defaults to SQLite) |
| `GOOGLE_MAPS_API_KEY` | No | Used in explore page map embed |

## Tech Stack

- **Backend**: Python / Flask with blueprint-per-feature structure
- **Database**: SQLite (dev) / PostgreSQL (production)
- **AI**: Claude via [fiat-lux-agents](https://github.com/aabtzu/fiat-lux-agents) — `LLMBase` for direct API calls, `SummaryBot` for natural language Q&A
- **Maps**: Leaflet.js with OpenStreetMap tiles
- **Frontend**: Vanilla JavaScript, CSS3
- **Deployment**: Render.com (gunicorn)

See [`docs/fiat-lux-agents.md`](docs/fiat-lux-agents.md) for how the AI layer is structured, and [`docs/recommendations.md`](docs/recommendations.md) for the trip recommendations and sharing system.

## Running Tests

```bash
./dev.sh test
# or
.venv/bin/python3 -m pytest tests/ -x -q
```

## License

MIT
