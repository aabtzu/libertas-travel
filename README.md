# Libertas

A travel itinerary web application for managing and viewing your trips.

Named after the Roman goddess of liberty, Libertas helps you organize your travel adventures with ease.

## Features

- **Import trips** from PDF files, Excel spreadsheets, Google Drive, TripIt, or web pages
- **View trips** in grid or list layout
- **Edit trip details** including name, dates, and statistics
- **Copy and delete** trips
- **Interactive maps** with day-by-day itinerary views

## Quick Start

```bash
# Install dependencies
pip install -e .

# Start the server
python server.py --port 8000
```

Then open http://localhost:8000 in your browser.

## Project Structure

```
libertas/
├── server.py                 # HTTP server with API endpoints
├── agents/itinerary/
│   ├── parser.py            # PDF/Excel parsing
│   ├── mapper.py            # Google Maps integration
│   ├── summarizer.py        # Trip summarization
│   ├── templates.py         # HTML generation
│   ├── web_view.py          # Trip page rendering
│   ├── static/
│   │   ├── css/             # Stylesheets
│   │   └── js/              # JavaScript
│   └── templates/           # HTML templates
├── data/old_trips/          # Sample trip files
└── output/                  # Generated HTML files
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload` | POST | Upload PDF/Excel file |
| `/api/import-url` | POST | Import from URL |
| `/api/rename-trip` | POST | Rename a trip |
| `/api/update-trip` | POST | Update trip details |
| `/api/delete-trip` | POST | Delete a trip |
| `/api/copy-trip` | POST | Copy a trip |

## Supported Import Sources

- **PDF files** - Travel agency itineraries
- **Excel files** (.xlsx, .xls) - Spreadsheet itineraries
- **Google Drive** - Shared PDF/Excel links
- **TripIt** - Public trip links
- **Web pages** - HTML itinerary pages

## License

MIT
