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
- **Explore destinations** — discover restaurants, hotels, and attractions via AI chat
- **Background geocoding** — locations geocoded asynchronously with Nominatim

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set required environment variables
export ANTHROPIC_API_KEY=your_api_key
export SECRET_KEY=your_secret_key

# Start the server (dev mode — auth disabled)
./dev.sh start
```

Then open http://localhost:5555 in your browser.

## Project Structure

```
libertas/
├── app.py                    # Flask app factory, blueprint registration
├── auth.py                   # User credentials and registration
├── database.py               # SQLite / PostgreSQL operations
├── geocoding_worker.py       # Background geocoding service
├── agents/
│   ├── auth/                 # Login, register, logout routes
│   ├── trips/                # Trip CRUD, export, ICS, geocoding routes
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
- **AI**: Claude via fiat-lux-agents
- **Maps**: Leaflet.js with OpenStreetMap tiles
- **Frontend**: Vanilla JavaScript, CSS3
- **Deployment**: Render.com (gunicorn)

## Running Tests

```bash
./dev.sh test
# or
.venv/bin/python3 -m pytest tests/ -x -q
```

## License

MIT
