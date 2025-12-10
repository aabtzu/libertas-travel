# Libertas

A modern travel itinerary web application for planning, organizing, and visualizing your trips.

Named after the Roman goddess of liberty, alongside Abeona (goddess of outward journeys) and Adeona (goddess of safe returns), Libertas helps you travel freely.

## Features

### Trip Management
- **Import trips** from PDF files, Excel spreadsheets, Google Drive, TripIt, or web pages
- **Create trips** from scratch with an AI-powered chat assistant
- **Export/Import** trips as JSON for backup and sharing between environments
- **Multiple views**: List, Grid, Calendar, and interactive Map
- **Edit trips** inline with drag-and-drop reordering
- **Share trips** with other users or make them public

### AI-Powered Features
- **Smart parsing** - AI extracts dates, locations, activities from uploaded documents
- **Trip assistant** - Chat-based help for building itineraries on the Create page
- **Explore destinations** - Discover restaurants, hotels, attractions with the Explore chat

### Maps & Visualization
- **Interactive maps** with Leaflet showing all trip locations
- **Day-by-day routes** with colored markers by category
- **Background geocoding** - locations are geocoded asynchronously
- **Calendar view** - see your trip laid out on a monthly calendar

### Mobile Responsive
- **Hamburger navigation** on all pages
- **Slide-in chat trays** on Create and Explore pages
- **Touch-friendly** buttons and controls
- **Responsive layouts** - cards stack on mobile, tables scroll horizontally

## Quick Start

```bash
# Install dependencies
pip install -e .

# Set up environment variables
export ANTHROPIC_API_KEY=your_api_key
export GOOGLE_MAPS_API_KEY=your_maps_key  # Optional, for maps

# Start the server
python server.py --port 8000
```

Then open http://localhost:8000 in your browser.

## Project Structure

```
libertas/
├── server.py                 # HTTP server with API endpoints
├── database.py               # SQLite database operations
├── geocoding_worker.py       # Background geocoding service
├── agents/
│   ├── common/               # Shared templates and components
│   │   ├── templates.py      # Navigation, page templates
│   │   └── templates/        # HTML templates (home, about, login)
│   ├── itinerary/            # Trip viewing and management
│   │   ├── parser.py         # PDF/Excel/HTML parsing with AI
│   │   ├── mapper.py         # Geocoding and map generation
│   │   ├── templates.py      # Trip HTML generation
│   │   └── web_view.py       # Trip page rendering
│   ├── create/               # Trip creation with AI assistant
│   │   └── handler.py        # Chat and itinerary building
│   └── explore/              # Venue discovery
│       ├── handler.py        # Search and chat logic
│       └── templates.py      # Explore page generation
├── static/
│   ├── css/                  # Global stylesheets
│   └── js/                   # Global JavaScript
├── data/
│   └── venues.json           # Curated venue database
└── output/                   # Generated trip HTML files
```

## Pages

| Page | Description |
|------|-------------|
| `/` | Home page with feature overview |
| `/trips.html` | My Trips - view, import, manage trips |
| `/create.html` | Create Trip - build itineraries with AI chat |
| `/explore.html` | Explore - discover venues and destinations |
| `/about.html` | About page with project background |
| `/{trip}.html` | Individual trip view with map |

## API Endpoints

### Trip Management
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload` | POST | Upload PDF/Excel/HTML file |
| `/api/import-url` | POST | Import from URL (Drive, TripIt) |
| `/api/trips` | GET | List user's trips |
| `/api/trip/{link}` | GET | Get trip details |
| `/api/update-trip` | POST | Update trip metadata |
| `/api/delete-trip` | POST | Delete a trip |
| `/api/copy-trip` | POST | Duplicate a trip |
| `/api/export-trip/{link}` | GET | Export trip as JSON |

### Create Trip
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/create/new` | POST | Create new empty trip |
| `/api/create/chat` | POST | Chat with trip assistant |
| `/api/create/save` | POST | Save trip itinerary |
| `/api/create/publish` | POST | Publish trip to view |

### Explore
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/explore/chat` | POST | Chat to search venues |
| `/api/explore/venues` | GET | Get all venues |

### Maps
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/regenerate-map/{link}` | POST | Regenerate trip map |
| `/api/geocoding/status` | GET | Check geocoding queue |

## Supported Import Sources

- **PDF files** - Travel agency itineraries, booking confirmations
- **Excel files** (.xlsx, .xls) - Spreadsheet itineraries
- **Word documents** (.docx) - Text itineraries
- **HTML files** - Web page exports
- **ICS files** - Calendar exports
- **JSON files** - Libertas export files
- **Email files** (.eml) - Booking confirmation emails
- **Google Drive** - Shared PDF/Excel links
- **TripIt** - Public trip links

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for AI features |
| `GOOGLE_MAPS_API_KEY` | No | Google Maps for geocoding and maps |
| `SESSION_SECRET` | No | Secret for session cookies |

## Tech Stack

- **Backend**: Python with http.server
- **Database**: SQLite
- **AI**: Claude (Anthropic) for parsing and chat
- **Maps**: Leaflet.js with OpenStreetMap tiles
- **Frontend**: Vanilla JavaScript, CSS3
- **Deployment**: Render.com

## License

MIT
