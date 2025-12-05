"""Libertas Web Server - Serves the app and handles file uploads."""

import json
import os
import re
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import tempfile
import shutil
import urllib.request
import ssl

# Add agents to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from agents.itinerary.parser import ItineraryParser
from agents.itinerary.web_view import ItineraryWebView
from agents.itinerary.templates import generate_trips_page
from agents.common.templates import generate_about_page, generate_home_page, generate_login_page, generate_register_page, get_nav_html
from agents.explore.templates import generate_explore_page
from agents.create import handler as create_handler
import csv

# Import authentication and database
import auth
import database as db

# Import geocoding worker for async map generation
import geocoding_worker

# Allow OUTPUT_DIR to be configured via environment variable (for Render persistent disk)
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", Path(__file__).parent / "output"))
TRIPS_DATA_FILE = OUTPUT_DIR / "trips_data.json"

# Travel recommendations data (from travel_recs project)
TRAVEL_RECS_CSV = Path(os.environ.get("TRAVEL_RECS_CSV", Path.home() / "repos" / "travel_recs" / "data" / "restaurants_master.csv"))

# Cache for venues data
_venues_cache = None


def convert_google_drive_url(url: str) -> tuple[str, str]:
    """Convert Google Drive sharing URL to direct download URL.

    Returns (download_url, filename) tuple.
    """
    # Handle various Google Drive URL formats:
    # https://drive.google.com/file/d/FILE_ID/view?usp=sharing
    # https://drive.google.com/open?id=FILE_ID
    # https://docs.google.com/spreadsheets/d/FILE_ID/edit

    file_id = None
    filename = "downloaded_file"

    # Extract file ID from URL
    if "/file/d/" in url:
        match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
        if match:
            file_id = match.group(1)
    elif "id=" in url:
        match = re.search(r'id=([a-zA-Z0-9_-]+)', url)
        if match:
            file_id = match.group(1)
    elif "/spreadsheets/d/" in url:
        # Google Sheets - export as xlsx
        match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', url)
        if match:
            file_id = match.group(1)
            # Use export URL for sheets
            return (
                f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx",
                "spreadsheet.xlsx"
            )

    if file_id:
        # Use the confirm=1 parameter to bypass virus scan warning for large files
        return (
            f"https://drive.google.com/uc?export=download&id={file_id}&confirm=1",
            filename
        )

    return url, filename


def download_from_url(url: str) -> tuple[bytes, str, str]:
    """Download content from URL and return (content, filename, content_type).

    Handles Google Drive links, file downloads, and HTML pages.
    """
    filename = "downloaded_file"

    # Check if it's a Google Drive URL
    parsed = urlparse(url)
    if "google.com" in parsed.netloc or "drive.google.com" in parsed.netloc:
        url, filename = convert_google_drive_url(url)

    # Create SSL context that doesn't verify certificates (for simplicity)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # Set up request with full browser-like headers (required for sites like TripIt)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'identity',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
    }

    req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, context=ctx, timeout=60) as response:
        content_type = response.headers.get('Content-Type', '').lower()

        # Try to get filename from Content-Disposition header
        content_disp = response.headers.get('Content-Disposition', '')
        if 'filename=' in content_disp:
            match = re.search(r'filename[*]?=["\']?([^"\';]+)', content_disp)
            if match:
                filename = match.group(1).strip('"\'')

        # Determine file extension from content type if needed
        if '.' not in filename:
            if 'spreadsheet' in content_type or 'excel' in content_type:
                filename += '.xlsx'
            elif 'pdf' in content_type:
                filename += '.pdf'
            elif 'html' in content_type:
                filename += '.html'

        content = response.read()

    return content, filename, content_type


def extract_text_from_html(html_content: bytes) -> str:
    """Extract readable text from HTML content for itinerary parsing."""
    import html.parser

    class TextExtractor(html.parser.HTMLParser):
        def __init__(self):
            super().__init__()
            self.text_parts = []
            self.skip_tags = {'script', 'style', 'meta', 'link', 'noscript'}
            self.current_skip = False

        def handle_starttag(self, tag, attrs):
            if tag in self.skip_tags:
                self.current_skip = True
            elif tag in ('br', 'p', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                self.text_parts.append('\n')

        def handle_endtag(self, tag):
            if tag in self.skip_tags:
                self.current_skip = False
            elif tag in ('p', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                self.text_parts.append('\n')

        def handle_data(self, data):
            if not self.current_skip:
                text = data.strip()
                if text:
                    self.text_parts.append(text + ' ')

    # Decode HTML content
    try:
        html_str = html_content.decode('utf-8')
    except UnicodeDecodeError:
        html_str = html_content.decode('latin-1')

    extractor = TextExtractor()
    extractor.feed(html_str)

    # Clean up the extracted text
    text = ''.join(extractor.text_parts)
    # Remove excessive whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)

    return text.strip()


def load_trips_data() -> list[dict]:
    """Load trips data from JSON file."""
    if TRIPS_DATA_FILE.exists():
        with open(TRIPS_DATA_FILE) as f:
            return json.load(f)
    return []


def save_trips_data(trips: list[dict]) -> None:
    """Save trips data to JSON file."""
    with open(TRIPS_DATA_FILE, "w") as f:
        json.dump(trips, f, indent=2)


def load_venues() -> list[dict]:
    """Load venues from travel_recs CSV file."""
    global _venues_cache
    if _venues_cache is not None:
        return _venues_cache

    if not TRAVEL_RECS_CSV.exists():
        print(f"Warning: Travel recs CSV not found at {TRAVEL_RECS_CSV}")
        return []

    venues = []
    with open(TRAVEL_RECS_CSV, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert empty strings to None for consistency
            venue = {
                "name": row.get("name", ""),
                "city": row.get("city", ""),
                "state": row.get("state", ""),
                "country": row.get("country", ""),
                "address": row.get("address", ""),
                "latitude": row.get("latitude", ""),
                "longitude": row.get("longitude", ""),
                "venue_type": row.get("venue_type", ""),
                "cuisine_type": row.get("cuisine_type", ""),
                "michelin_stars": int(row.get("michelin_stars", 0) or 0),
                "google_maps_link": row.get("google_maps_link", ""),
                "website": row.get("website", ""),
                "description": row.get("description", ""),
                "collection": row.get("collection", ""),
                "notes": row.get("notes", ""),
            }
            venues.append(venue)

    _venues_cache = venues
    print(f"Loaded {len(venues)} venues from {TRAVEL_RECS_CSV}")
    return venues


def regenerate_trips_page(user_id: int = None) -> None:
    """Regenerate the trips.html page with current trips data.

    If user_id is provided, uses database. Otherwise uses JSON file (legacy).
    """
    try:
        if user_id is not None:
            trips = db.get_user_trips(user_id)
        else:
            trips = load_trips_data()
        html = generate_trips_page(trips)
        (OUTPUT_DIR / "trips.html").write_text(html)
    except Exception as e:
        print(f"Error regenerating trips page: {e}")
        import traceback
        traceback.print_exc()


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '_', text)
    return text.strip('_')


class LibertasHandler(SimpleHTTPRequestHandler):
    """HTTP request handler with upload support."""

    def __init__(self, *args, **kwargs):
        # Serve files from output directory
        super().__init__(*args, directory=str(OUTPUT_DIR), **kwargs)

    def get_session_token(self):
        """Extract session token from cookies."""
        cookie_header = self.headers.get('Cookie', '')
        cookies = auth.parse_cookies(cookie_header)
        return cookies.get(auth.SESSION_COOKIE_NAME)

    def is_authenticated(self) -> bool:
        """Check if the current request is authenticated."""
        if not auth.is_auth_enabled():
            return True
        token = self.get_session_token()
        return auth.validate_session(token) is not None

    def get_current_user_id(self) -> int:
        """Get the current user's ID from session. Returns 1 (default) if auth is disabled."""
        if not auth.is_auth_enabled():
            return 1  # Default user
        token = self.get_session_token()
        user_id = auth.get_session_user_id(token)
        return user_id if user_id else 1

    def require_auth(self) -> bool:
        """Check authentication and redirect to login if needed. Returns True if authenticated."""
        if self.is_authenticated():
            return True

        # Redirect to login page with original URL
        parsed = urlparse(self.path)
        redirect_path = parsed.path
        if parsed.query:
            redirect_path += f"?{parsed.query}"

        self.send_response(302)
        self.send_header('Location', f'/login.html?redirect={redirect_path}')
        self.end_headers()
        return False

    def do_GET(self):
        """Handle GET requests - add debug endpoint and auth."""
        # Parse URL path
        parsed = urlparse(self.path)
        path = parsed.path

        # Public routes (no auth required)
        if path == "/login.html" or path == "/login":
            self.serve_login_page()
            return

        if path == "/register.html" or path == "/register":
            self.serve_register_page()
            return

        # Serve static files (CSS, JS) - public, no auth required
        if path.startswith("/static/"):
            self.serve_static_file(path)
            return

        # Home page and About page - public, no auth required
        if path == "/" or path == "/index.html":
            self.serve_home_page()
            return

        if path == "/about.html" or path == "/about":
            self.serve_about_page()
            return

        # Explore page - public, no auth required
        if path == "/explore.html" or path == "/explore":
            self.serve_explore_page()
            return

        # Create page - requires auth
        if path == "/create.html" or path == "/create":
            if not self.require_auth():
                return
            self.serve_create_page()
            return

        # API debug endpoint
        if path == "/api/debug":
            self.handle_debug()
            return

        # API map status endpoint (check if map is ready)
        if path.startswith("/api/map-status"):
            self.handle_map_status()
            return

        # Check authentication for all other routes
        if not self.require_auth():
            return

        # Serve trips.html dynamically (user-specific)
        if path == "/trips.html" or path == "/trips":
            self.serve_trips_page()
            return

        # API endpoint for explore venues
        if path == "/api/explore/venues":
            self.handle_explore_venues()
            return

        # API endpoint for trip data (for create/edit)
        if path.startswith("/api/trips/") and path.endswith("/data"):
            link = path[len("/api/trips/"):-len("/data")]
            self.handle_get_trip_data(link)
            return

        # Serve trip HTML files from output folder with updated navigation
        if path.endswith(".html") and not path.startswith("/api/"):
            self.serve_trip_html(path)
            return

        # Let parent class handle static files
        super().do_GET()

    def serve_trips_page(self):
        """Serve the trips page dynamically for the current user."""
        user_id = self.get_current_user_id()
        trips = db.get_user_trips(user_id)
        public_trips = db.get_public_trips(exclude_user_id=user_id)
        html = generate_trips_page(trips, public_trips)
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', len(html.encode()))
        self.end_headers()
        self.wfile.write(html.encode())

    def serve_login_page(self):
        """Serve the login page."""
        # If already authenticated, redirect to home
        if self.is_authenticated():
            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()
            return

        html = generate_login_page()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', len(html.encode()))
        self.end_headers()
        self.wfile.write(html.encode())

    def serve_register_page(self):
        """Serve the registration page."""
        # If already authenticated, redirect to home
        if self.is_authenticated():
            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()
            return

        html = generate_register_page()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', len(html.encode()))
        self.end_headers()
        self.wfile.write(html.encode())

    def serve_home_page(self):
        """Serve the home page (public - no auth required)."""
        html = generate_home_page()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', len(html.encode()))
        self.end_headers()
        self.wfile.write(html.encode())

    def serve_about_page(self):
        """Serve the about page (public - no auth required)."""
        html = generate_about_page()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', len(html.encode()))
        self.end_headers()
        self.wfile.write(html.encode())

    def serve_explore_page(self):
        """Serve the explore page."""
        # Get Google Maps API key from environment
        google_maps_api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
        html = generate_explore_page(google_maps_api_key)
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', len(html.encode()))
        self.end_headers()
        self.wfile.write(html.encode())

    def serve_create_page(self):
        """Serve the create trip page."""
        # Read the template
        template_path = Path(__file__).parent / "agents" / "create" / "templates" / "create.html"
        if not template_path.exists():
            self.send_error(404, "Create page template not found")
            return

        html = template_path.read_text()
        html = html.format(nav_html=get_nav_html(""))

        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', len(html.encode()))
        self.end_headers()
        self.wfile.write(html.encode())

    def handle_get_trip_data(self, link: str):
        """Get trip data for the create/edit page."""
        user_id = self.get_current_user_id()
        result, status = create_handler.get_trip_data_handler(user_id, link)
        if status == 200:
            self.send_json_response(result)
        else:
            self.send_json_error(result.get('error', 'Unknown error'), status=status)

    def serve_trip_html(self, path: str):
        """Serve trip HTML files with updated navigation injected."""
        # Security: prevent directory traversal
        if ".." in path:
            self.send_error(403, "Forbidden")
            return

        # Remove leading slash and look in output folder
        filename = path.lstrip("/")
        file_path = OUTPUT_DIR / filename

        # Check if file exists
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "File not found")
            return

        # Read the HTML content
        html = file_path.read_text()

        # Inject current navigation by replacing the old nav
        # Match the nav element and its contents
        nav_pattern = r'<nav class="libertas-nav">.*?</nav>\s*<script>\s*function logout\(\).*?</script>'
        new_nav = get_nav_html("")
        html = re.sub(nav_pattern, new_nav, html, flags=re.DOTALL)

        # Send the response
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', len(html.encode()))
        self.end_headers()
        self.wfile.write(html.encode())

    def serve_static_file(self, path: str):
        """Serve static files (CSS, JS) from the static directory."""
        # Security: only allow files within static directory
        # Remove /static/ prefix
        relative_path = path[8:]  # len("/static/") = 8

        # Prevent directory traversal attacks
        if ".." in relative_path:
            self.send_error(403, "Forbidden")
            return

        # Build full path to static file
        static_dir = Path(__file__).parent / "static"
        file_path = static_dir / relative_path

        # Check if file exists
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "File not found")
            return

        # Determine content type
        suffix = file_path.suffix.lower()
        content_types = {
            ".css": "text/css",
            ".js": "application/javascript",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
        }
        content_type = content_types.get(suffix, "application/octet-stream")

        # Read and serve file
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        except IOError:
            self.send_error(500, "Error reading file")

    def handle_explore_venues(self):
        """Return all venues from travel_recs."""
        venues = load_venues()
        self.send_json_response(venues)

    def handle_explore_chat(self):
        """Handle chat messages for explore feature with Claude LLM."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_json_error("Invalid JSON in request body")
            return

        message = data.get('message', '').strip()
        history = data.get('history', [])

        if not message:
            self.send_json_error("No message provided")
            return

        # Load venues
        venues = load_venues()

        # Build venue summary for context
        venue_types = {}
        cities = {}
        states = {}
        countries = {}
        for v in venues:
            vt = v.get('venue_type', 'Other')
            venue_types[vt] = venue_types.get(vt, 0) + 1
            if v.get('city'):
                cities[v['city']] = cities.get(v['city'], 0) + 1
            if v.get('state'):
                states[v['state']] = states.get(v['state'], 0) + 1
            if v.get('country'):
                countries[v['country']] = countries.get(v['country'], 0) + 1

        # Call Claude API to process the message
        import anthropic

        try:
            client = anthropic.Anthropic()

            system_prompt = f"""You are a helpful travel assistant for Libertas, a travel planning app.
You have access to a curated database of {len(venues)} venues across {len(countries)} countries.

Available venue types: {', '.join(f"{k} ({v})" for k, v in sorted(venue_types.items(), key=lambda x: -x[1])[:10])}

Top cities: {', '.join(f"{k} ({v})" for k, v in sorted(cities.items(), key=lambda x: -x[1])[:15])}

States/Regions (for US trips): {', '.join(f"{k} ({v})" for k, v in sorted(states.items(), key=lambda x: -x[1])[:20] if k)}

Countries: {', '.join(sorted(countries.keys()))}

When the user asks about places, restaurants, bars, hotels, or other venues:
1. Analyze their request to understand what they're looking for
2. Search through the venues to find relevant matches
3. Return a helpful response with your recommendations

IMPORTANT - Route/Trip Queries:
When users ask about "trips from X to Y" or "road trip from X to Y" or similar route-based queries:
- Think about the geographic route between those locations
- Include venues from intermediate stops along the way, not just the endpoints
- For example, "SF to Alaska" should include places in Oregon, Washington, Vancouver, etc.
- For example, "NYC to Miami" should include places in DC, the Carolinas, Georgia, etc.
- Organize the results geographically from start to finish when possible

To return venue results to display on the map, include a JSON block in your response like this:
```json
{{"venues": ["venue_name_1", "venue_name_2", ...]}}
```

The venue names must match exactly from the database. Include up to 30 venues maximum for route queries, 20 for regular searches.

If the user is just chatting or asking general questions (not searching for venues), respond conversationally without the JSON block.

Keep responses concise and direct. Avoid flowery language, clichés, or poetic phrases like "the journey becomes the destination". Just give practical info about the places."""

            # Build messages from history
            messages = []
            for h in history[-10:]:  # Last 10 messages
                role = h.get('role', 'user')
                if role in ['user', 'assistant']:
                    messages.append({"role": role, "content": h.get('content', '')})

            messages.append({"role": "user", "content": message})

            # Also pass venue data in the current message context for searching
            venue_context = "Here are all venues in the database:\n\n"
            for v in venues:
                venue_context += f"- {v['name']}"
                if v.get('city'):
                    venue_context += f", {v['city']}"
                if v.get('state'):
                    venue_context += f", {v['state']}"
                if v.get('country'):
                    venue_context += f", {v['country']}"
                if v.get('venue_type'):
                    venue_context += f" ({v['venue_type']})"
                if v.get('cuisine_type'):
                    venue_context += f" - {v['cuisine_type']}"
                if v.get('michelin_stars'):
                    venue_context += f" ⭐{v['michelin_stars']} Michelin"
                venue_context += "\n"

            # Add venue list to the user message
            messages[-1]["content"] = f"{message}\n\n---\n{venue_context}"

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                system=system_prompt,
                messages=messages
            )

            assistant_response = response.content[0].text

            # Extract venue names from JSON block if present
            matched_venues = []
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', assistant_response, re.DOTALL)
            if json_match:
                try:
                    venue_data = json.loads(json_match.group(1))
                    venue_names = venue_data.get('venues', [])

                    # Match venue names to actual venue objects
                    for name in venue_names:
                        for v in venues:
                            if v['name'].lower() == name.lower():
                                matched_venues.append(v)
                                break

                    # Remove JSON block from response text
                    assistant_response = re.sub(r'```json\s*\{.*?\}\s*```', '', assistant_response, flags=re.DOTALL).strip()
                except json.JSONDecodeError:
                    pass

            self.send_json_response({
                "response": assistant_response,
                "venues": matched_venues,
            })

        except anthropic.APIError as e:
            # Fallback to simple search if Claude API fails
            print(f"Claude API error: {e}")
            matched_venues = self.simple_venue_search(message, venues)

            if matched_venues:
                response_text = f"I found {len(matched_venues)} places matching your search:"
            else:
                response_text = "I couldn't find any places matching your search. Try being more specific about the location or type of venue."

            self.send_json_response({
                "response": response_text,
                "venues": matched_venues,
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json_error(str(e))

    def simple_venue_search(self, query: str, venues: list) -> list:
        """Simple keyword-based venue search as fallback."""
        query_lower = query.lower()
        words = query_lower.split()

        matches = []
        for v in venues:
            score = 0
            searchable = f"{v.get('name', '')} {v.get('city', '')} {v.get('country', '')} {v.get('venue_type', '')} {v.get('cuisine_type', '')}".lower()

            for word in words:
                if len(word) > 2 and word in searchable:
                    score += 1

            if score > 0:
                matches.append((score, v))

        matches.sort(key=lambda x: -x[0])
        return [v for _, v in matches[:20]]

    def handle_debug(self):
        """Return debug info about disk and environment."""
        import subprocess
        debug_info = {
            "output_dir": str(OUTPUT_DIR),
            "output_dir_exists": OUTPUT_DIR.exists(),
            "output_dir_is_dir": OUTPUT_DIR.is_dir() if OUTPUT_DIR.exists() else False,
            "trips_data_file": str(TRIPS_DATA_FILE),
            "trips_data_exists": TRIPS_DATA_FILE.exists(),
            "env_output_dir": os.environ.get("OUTPUT_DIR", "NOT SET"),
            "env_port": os.environ.get("PORT", "NOT SET"),
            "cwd": os.getcwd(),
        }

        # List files in output dir
        if OUTPUT_DIR.exists():
            try:
                files = list(OUTPUT_DIR.iterdir())
                debug_info["output_files"] = [f.name for f in files if f.is_file()]
                debug_info["output_file_count"] = len([f for f in files if f.is_file()])
            except Exception as e:
                debug_info["output_files_error"] = str(e)

        # List uploaded files
        uploads_dir = OUTPUT_DIR / "uploads"
        if uploads_dir.exists():
            try:
                uploads = list(uploads_dir.iterdir())
                debug_info["uploaded_files"] = [f.name for f in uploads]
                debug_info["uploaded_file_count"] = len(uploads)
            except Exception as e:
                debug_info["uploaded_files_error"] = str(e)

        # Check disk space
        try:
            result = subprocess.run(["df", "-h", str(OUTPUT_DIR)], capture_output=True, text=True, timeout=5)
            debug_info["disk_space"] = result.stdout
        except Exception as e:
            debug_info["disk_space_error"] = str(e)

        # Check trips data content
        if TRIPS_DATA_FILE.exists():
            try:
                trips = load_trips_data()
                debug_info["trips_count"] = len(trips)
                debug_info["trips_titles"] = [t.get("title", "?") for t in trips[:5]]
            except Exception as e:
                debug_info["trips_data_error"] = str(e)

        self.send_json_response(debug_info)

    def handle_map_status(self):
        """Return map status for a trip."""
        # Get link from query string
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        link = params.get('link', [''])[0]

        if not link:
            self.send_json_error("Missing 'link' parameter")
            return

        # Find the trip for current user
        user_id = self.get_current_user_id()
        trip = db.get_trip_by_link(user_id, link)

        if not trip:
            self.send_json_error("Trip not found", status=404)
            return

        self.send_json_response({
            "link": link,
            "map_status": trip.get("map_status", "ready"),  # Default to ready for old trips
            "map_error": trip.get("map_error"),
            "queue_size": geocoding_worker.get_queue_size(),
        })

    def do_POST(self):
        """Handle POST requests (file uploads, URL imports, and auth)."""
        # Auth endpoints (no auth required)
        if self.path == "/api/login":
            self.handle_login()
            return

        if self.path == "/api/register":
            self.handle_register()
            return
        elif self.path == "/api/logout":
            self.handle_logout()
            return

        # Check authentication for all other POST endpoints
        if not self.is_authenticated():
            self.send_json_error("Authentication required", status=401)
            return

        if self.path == "/api/upload":
            self.handle_upload()
        elif self.path == "/api/import-url":
            self.handle_url_import()
        elif self.path == "/api/delete-trip":
            self.handle_delete_trip()
        elif self.path == "/api/copy-trip":
            self.handle_copy_trip()
        elif self.path == "/api/rename-trip":
            self.handle_rename_trip()
        elif self.path == "/api/update-trip":
            self.handle_update_trip()
        elif self.path == "/api/retry-geocoding":
            self.handle_retry_geocoding()
        elif self.path == "/api/share-trip":
            self.handle_share_trip()
        elif self.path == "/api/toggle-public":
            self.handle_toggle_public()
        elif self.path == "/api/users":
            self.handle_get_users()
        elif self.path == "/api/explore/chat":
            self.handle_explore_chat()
        elif self.path == "/api/trips/create":
            self.handle_create_trip()
        elif self.path == "/api/create/chat":
            self.handle_create_chat()
        elif self.path == "/api/create/upload-plan":
            self.handle_upload_plan()
        elif self.path.startswith("/api/trips/") and self.path.endswith("/save"):
            link = self.path[len("/api/trips/"):-len("/save")]
            self.handle_save_trip(link)
        elif self.path.startswith("/api/trips/") and self.path.endswith("/publish"):
            link = self.path[len("/api/trips/"):-len("/publish")]
            self.handle_publish_trip(link)
        elif self.path.startswith("/api/trips/") and self.path.endswith("/items"):
            link = self.path[len("/api/trips/"):-len("/items")]
            self.handle_add_trip_item(link)
        else:
            self.send_error(404, "Not Found")

    def handle_login(self):
        """Handle login request."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_json_error("Invalid JSON in request body")
            return

        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if not username or not password:
            self.send_json_error("Username and password required")
            return

        user = auth.verify_credentials(username, password)
        if user:
            # Create session and set cookie
            token = auth.create_session(user)

            # Determine if we should use Secure cookie (when on HTTPS)
            # For local dev, don't use Secure flag
            is_secure = self.headers.get('X-Forwarded-Proto') == 'https'

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Set-Cookie', auth.get_session_cookie_header(token, secure=is_secure))
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "username": user["username"]}).encode())
        else:
            self.send_json_error("Invalid username or password", status=401)

    def handle_register(self):
        """Handle user registration."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_json_error("Invalid JSON in request body")
            return

        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()

        success, error = auth.register_user(username, email, password)

        if success:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode())
        else:
            self.send_json_error(error, status=400)

    def handle_logout(self):
        """Handle logout request."""
        token = self.get_session_token()
        if token:
            auth.destroy_session(token)

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Set-Cookie', auth.get_logout_cookie_header())
        self.end_headers()
        self.wfile.write(json.dumps({"success": True}).encode())

    def handle_retry_geocoding(self):
        """Retry geocoding for a trip that failed."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_json_error("Invalid JSON in request body")
            return

        link = data.get('link', '').strip()
        if not link:
            self.send_json_error("No trip link provided")
            return

        # Find the trip for current user
        user_id = self.get_current_user_id()
        trip = db.get_trip_by_link(user_id, link)

        if not trip:
            self.send_json_error("Trip not found")
            return

        # Read the existing HTML file and extract itinerary data to re-geocode
        html_path = OUTPUT_DIR / link
        if not html_path.exists():
            self.send_json_error("Trip HTML file not found")
            return

        # Reset status to pending
        db.update_trip_map_status(user_id, link, "pending", None)

        # For now, just regenerate the map from scratch using the existing page content
        # This requires parsing the summary HTML back to an itinerary - complex
        # Instead, we'll set to pending and let the user re-upload if needed
        self.send_json_response({
            "success": True,
            "message": "Map status reset to pending. Please re-import the trip to regenerate the map.",
        })

    def handle_get_users(self):
        """Get list of all users for sharing."""
        # Consume any request body
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            self.rfile.read(content_length)

        try:
            users = db.get_all_users()
            current_user_id = self.get_current_user_id()
            # Filter out current user from the list
            users = [u for u in users if u["id"] != current_user_id]
            self.send_json_response({"success": True, "users": users})
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json_error(str(e))

    def handle_share_trip(self):
        """Share a trip with another user or all users."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_json_error("Invalid JSON in request body")
            return

        try:
            link = data.get('link', '').strip()
            target_user_id = data.get('targetUserId')
            share_with_all = data.get('shareWithAll', False)

            if not link:
                self.send_json_error("No trip link provided")
                return

            user_id = self.get_current_user_id()

            if share_with_all:
                # Share with all users
                shared_count = db.share_trip_with_all(user_id, link)
                self.send_json_response({
                    "success": True,
                    "message": f"Trip shared with {shared_count} users",
                    "sharedCount": shared_count,
                })
            elif target_user_id:
                # Share with specific user
                result = db.copy_trip_to_user(user_id, link, target_user_id)
                if result:
                    self.send_json_response({
                        "success": True,
                        "message": "Trip shared successfully",
                    })
                else:
                    self.send_json_error("Failed to share trip")
            else:
                self.send_json_error("No target user specified")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json_error(str(e))

    def handle_toggle_public(self):
        """Toggle a trip's public visibility."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_json_error("Invalid JSON in request body")
            return

        try:
            link = data.get('link', '').strip()
            is_public = data.get('isPublic', False)

            if not link:
                self.send_json_error("No trip link provided")
                return

            user_id = self.get_current_user_id()
            updated = db.set_trip_public(user_id, link, is_public)

            if updated:
                self.send_json_response({
                    "success": True,
                    "message": f"Trip {'made public' if is_public else 'made private'}",
                    "isPublic": is_public,
                })
            else:
                self.send_json_error("Trip not found")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json_error(str(e))

    def handle_create_trip(self):
        """Handle creating a new draft trip."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_json_error("Invalid JSON in request body")
            return

        user_id = self.get_current_user_id()
        result, status = create_handler.create_trip_handler(user_id, data)
        if status == 200:
            self.send_json_response(result)
        else:
            self.send_json_error(result.get('error', 'Unknown error'), status=status)

    def handle_save_trip(self, link: str):
        """Handle auto-saving trip itinerary data."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_json_error("Invalid JSON in request body")
            return

        user_id = self.get_current_user_id()
        result, status = create_handler.save_trip_handler(user_id, link, data)
        if status == 200:
            self.send_json_response(result)
        else:
            self.send_json_error(result.get('error', 'Unknown error'), status=status)

    def handle_publish_trip(self, link: str):
        """Handle publishing a draft trip."""
        # Consume any request body
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            self.rfile.read(content_length)

        user_id = self.get_current_user_id()
        result, status = create_handler.publish_trip_handler(user_id, link)
        if status == 200:
            self.send_json_response(result)
        else:
            self.send_json_error(result.get('error', 'Unknown error'), status=status)

    def handle_add_trip_item(self, link: str):
        """Handle adding an item to a trip's ideas pile."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_json_error("Invalid JSON in request body")
            return

        user_id = self.get_current_user_id()
        result, status = create_handler.add_item_to_trip_handler(user_id, link, data)
        if status == 200:
            self.send_json_response(result)
        else:
            self.send_json_error(result.get('error', 'Unknown error'), status=status)

    def handle_create_chat(self):
        """Handle LLM chat for create trip page."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_json_error("Invalid JSON in request body")
            return

        user_id = self.get_current_user_id()
        result, status = create_handler.create_chat_handler(user_id, data)
        if status == 200:
            self.send_json_response(result)
        else:
            self.send_json_error(result.get('error', 'Unknown error'), status=status)

    def handle_upload_plan(self):
        """Handle file upload for plan/reservation parsing."""
        try:
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('multipart/form-data'):
                self.send_json_error("Expected multipart/form-data")
                return

            # Get boundary from content type
            if 'boundary=' not in content_type:
                self.send_json_error("Missing boundary in multipart/form-data")
                return
            boundary = content_type.split('boundary=')[1]

            # Read content
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            # Parse multipart data using existing method
            file_data, filename = self.parse_multipart(body, boundary)

            if not file_data or not filename:
                self.send_json_error("No file provided")
                return

            # Get file extension
            ext = filename.lower().split('.')[-1] if '.' in filename else ''

            user_id = self.get_current_user_id()
            result, status = create_handler.upload_plan_handler(user_id, filename, file_data, ext)

            if status == 200:
                self.send_json_response(result)
            else:
                self.send_json_error(result.get('error', 'Unknown error'), status=status)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json_error(f"Upload error: {str(e)}")

    def handle_delete_trip(self):
        """Delete a trip by its link."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_json_error("Invalid JSON in request body")
            return

        try:
            link = data.get('link', '').strip()
            if not link:
                self.send_json_error("No trip link provided")
                return

            # Delete from database for current user
            user_id = self.get_current_user_id()
            deleted = db.delete_trip(user_id, link)

            if not deleted:
                self.send_json_error("Trip not found")
                return

            # Delete the HTML file
            html_file = OUTPUT_DIR / link
            if html_file.exists():
                os.unlink(html_file)

            self.send_json_response({
                "success": True,
                "message": "Trip deleted successfully",
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json_error(str(e))

    def handle_copy_trip(self):
        """Copy a trip for editing (placeholder for future new trip feature)."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_json_error("Invalid JSON in request body")
            return

        try:
            link = data.get('link', '').strip()
            if not link:
                self.send_json_error("No trip link provided")
                return

            # Find the trip for current user
            user_id = self.get_current_user_id()
            trip = db.get_trip_by_link(user_id, link)

            if not trip:
                self.send_json_error("Trip not found")
                return

            # For now, just return success with trip data
            # Future: This will open the trip editor with the trip data pre-filled
            self.send_json_response({
                "success": True,
                "message": "Trip copied - editor coming soon!",
                "trip": trip,
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json_error(str(e))

    def handle_rename_trip(self):
        """Rename a trip."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_json_error("Invalid JSON in request body")
            return

        try:
            link = data.get('link', '').strip()
            new_title = data.get('newTitle', '').strip()

            if not link:
                self.send_json_error("No trip link provided")
                return
            if not new_title:
                self.send_json_error("No new title provided")
                return

            # Update trip in database for current user
            user_id = self.get_current_user_id()
            updated = db.update_trip(user_id, link, {"title": new_title})

            if not updated:
                self.send_json_error("Trip not found")
                return

            self.send_json_response({
                "success": True,
                "message": f"Trip renamed to '{new_title}'",
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json_error(str(e))

    def handle_update_trip(self):
        """Update a trip's details (title, dates, days, locations, activities)."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_json_error("Invalid JSON in request body")
            return

        try:
            link = data.get('link', '').strip()
            if not link:
                self.send_json_error("No trip link provided")
                return

            # Build updates dict
            updates = {}
            if 'title' in data and data['title']:
                updates["title"] = data['title']
            if 'dates' in data and data['dates']:
                updates["dates"] = data['dates']
            if 'days' in data:
                updates["days"] = int(data['days'])
            if 'locations' in data:
                updates["locations"] = int(data['locations'])
            if 'activities' in data:
                updates["activities"] = int(data['activities'])

            if not updates:
                self.send_json_error("No fields to update")
                return

            # Update trip in database for current user
            user_id = self.get_current_user_id()
            updated = db.update_trip(user_id, link, updates)

            if not updated:
                self.send_json_error("Trip not found")
                return

            self.send_json_response({
                "success": True,
                "message": "Trip updated successfully",
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json_error(str(e))

    def handle_upload(self):
        """Process uploaded itinerary file."""
        try:
            # Parse multipart form data
            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in content_type:
                self.send_json_error("Invalid content type")
                return

            # Get boundary
            boundary = content_type.split('boundary=')[1]

            # Read content
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            # Parse multipart data to extract file
            file_data, filename = self.parse_multipart(body, boundary)

            if not file_data or not filename:
                self.send_json_error("No file uploaded")
                return

            # Check for valid file extension
            suffix = Path(filename).suffix.lower()
            valid_extensions = ['.pdf', '.xlsx', '.xls', '.html', '.htm']
            if suffix not in valid_extensions:
                self.send_json_error(f"Invalid file type '{suffix}'. Supported: PDF, Excel, HTML")
                return

            # Save to temp file
            suffix = Path(filename).suffix
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(file_data)
                tmp_path = tmp.name

            # Also save a copy for debugging (in uploads folder)
            uploads_dir = OUTPUT_DIR / "uploads"
            uploads_dir.mkdir(exist_ok=True)
            saved_upload = uploads_dir / filename
            try:
                saved_upload.write_bytes(file_data)
                print(f"Saved upload to: {saved_upload}")
            except Exception as e:
                print(f"Warning: Could not save upload copy: {e}")

            try:
                import time
                start_time = time.time()

                # Check if it's an HTML file - parse differently
                is_html_file = suffix.lower() in ['.html', '.htm']

                # Parse the itinerary
                print(f"[UPLOAD] Step 1: Parsing file...")
                parser = ItineraryParser()

                if is_html_file:
                    # Extract text from HTML and parse
                    html_text = extract_text_from_html(file_data)
                    if len(html_text) < 100:
                        self.send_json_error("Could not extract meaningful content from the HTML file.")
                        return
                    itinerary = parser.parse_text(html_text, source_url=filename)
                else:
                    itinerary = parser.parse_file(tmp_path)
                print(f"[UPLOAD] Step 1 done: {time.time() - start_time:.1f}s - Found {len(itinerary.items)} items")

                # Generate web view (skip geocoding to avoid timeout - map shows placeholder)
                print(f"[UPLOAD] Step 2: Generating web view (no geocoding)...")
                slug = slugify(itinerary.title)
                output_file = f"{slug}.html"
                web_view = ItineraryWebView()
                web_view.generate(itinerary, OUTPUT_DIR / output_file, use_ai_summary=False, skip_geocoding=True)
                print(f"[UPLOAD] Step 2 done: {time.time() - start_time:.1f}s - Generated {output_file}")

                # Count unique locations
                locations = set()
                for item in itinerary.items:
                    if item.location.name and not item.is_home_location:
                        locations.add(item.location.name.split(',')[0])

                # Build trip data
                trip_data = {
                    "title": itinerary.title,
                    "link": output_file,
                    "dates": self.format_dates(itinerary),
                    "days": itinerary.duration_days or len(set(item.day_number for item in itinerary.items if item.day_number)),
                    "locations": len(locations),
                    "activities": len(itinerary.items),
                    "map_status": "pending",  # Map will be generated async
                }

                # Add trip to database for current user
                print(f"[UPLOAD] Step 3: Saving trip data...")
                user_id = self.get_current_user_id()
                db.add_trip(user_id, trip_data)
                print(f"[UPLOAD] Step 3 done: {time.time() - start_time:.1f}s - Saved trip for user {user_id}")

                # Queue async geocoding for map generation
                print(f"[UPLOAD] Step 3b: Queueing background geocoding...")
                geocoding_worker.queue_geocoding(output_file, itinerary)

                print(f"[UPLOAD] SUCCESS - Total time: {time.time() - start_time:.1f}s")

                # Send success response
                self.send_json_response({
                    "success": True,
                    "title": itinerary.title,
                    "link": output_file,
                })

            finally:
                # Clean up temp file
                os.unlink(tmp_path)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json_error(str(e))

    def handle_url_import(self):
        """Process itinerary import from URL (Google Drive, TripIt, etc.)."""
        # Parse JSON request body separately to give proper error
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_json_error("Invalid JSON in request body")
            return

        try:
            url = data.get('url', '').strip()
            if not url:
                self.send_json_error("No URL provided")
                return

            # Download content from URL
            try:
                file_data, filename, content_type = download_from_url(url)
            except Exception as e:
                self.send_json_error(f"Failed to download from URL: {str(e)}")
                return

            # Determine how to handle the content based on type
            is_html = 'html' in content_type or file_data[:15].lower().startswith((b'<!doctype', b'<html'))

            # Check for file magic bytes
            is_pdf = file_data[:4] == b'%PDF'
            is_xlsx = file_data[:4] == b'PK\x03\x04'  # ZIP/XLSX magic bytes

            if is_html and not is_pdf and not is_xlsx:
                # Handle HTML content (e.g., TripIt pages)
                try:
                    html_text = extract_text_from_html(file_data)
                    if len(html_text) < 100:
                        self.send_json_error("Could not extract meaningful content from the page. The page might require login or have restricted access.")
                        return

                    # Parse the HTML text with Claude
                    parser = ItineraryParser()
                    itinerary = parser.parse_text(html_text, source_url=url)
                except Exception as e:
                    self.send_json_error(f"Failed to parse itinerary from page: {str(e)}")
                    return
                tmp_path = None  # No temp file for HTML
            else:
                # Handle file downloads (PDF, Excel)
                suffix = Path(filename).suffix.lower()
                if not suffix or suffix not in ['.pdf', '.xlsx', '.xls']:
                    if is_xlsx:
                        suffix = '.xlsx'
                    elif is_pdf:
                        suffix = '.pdf'
                    else:
                        self.send_json_error("Could not determine file type. Please use PDF, Excel files, or HTML itinerary pages.")
                        return

                # Save to temp file
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(file_data)
                    tmp_path = tmp.name

                # Also save a copy for debugging (in uploads folder)
                uploads_dir = OUTPUT_DIR / "uploads"
                uploads_dir.mkdir(exist_ok=True)
                import hashlib
                url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                saved_upload = uploads_dir / f"url_import_{url_hash}{suffix}"
                try:
                    saved_upload.write_bytes(file_data)
                    print(f"Saved URL import to: {saved_upload}")
                except Exception as e:
                    print(f"Warning: Could not save upload copy: {e}")

                try:
                    # Parse the itinerary from file
                    parser = ItineraryParser()
                    itinerary = parser.parse_file(tmp_path)
                except Exception as e:
                    if tmp_path:
                        os.unlink(tmp_path)
                    self.send_json_error(f"Failed to parse itinerary: {str(e)}")
                    return

            # Generate web view (skip geocoding to avoid timeout - map shows placeholder)
            slug = slugify(itinerary.title)
            output_file = f"{slug}.html"
            web_view = ItineraryWebView()
            web_view.generate(itinerary, OUTPUT_DIR / output_file, use_ai_summary=False, skip_geocoding=True)

            # Count unique locations
            locations = set()
            for item in itinerary.items:
                if item.location.name and not item.is_home_location:
                    locations.add(item.location.name.split(',')[0])

            # Build trip data
            trip_data = {
                "title": itinerary.title,
                "link": output_file,
                "dates": self.format_dates(itinerary),
                "days": itinerary.duration_days or len(set(item.day_number for item in itinerary.items if item.day_number)),
                "locations": len(locations),
                "activities": len(itinerary.items),
                "map_status": "pending",  # Map will be generated async
            }

            # Add trip to database for current user
            user_id = self.get_current_user_id()
            db.add_trip(user_id, trip_data)

            # Queue async geocoding for map generation
            geocoding_worker.queue_geocoding(output_file, itinerary)

            # Clean up temp file if it exists
            if tmp_path:
                os.unlink(tmp_path)

            # Send success response
            self.send_json_response({
                "success": True,
                "title": itinerary.title,
                "link": output_file,
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json_error(str(e))

    def parse_multipart(self, body: bytes, boundary: str) -> tuple:
        """Parse multipart form data to extract file."""
        boundary_bytes = f"--{boundary}".encode()
        parts = body.split(boundary_bytes)

        for part in parts:
            if b'filename="' in part:
                # Extract filename
                header_end = part.find(b'\r\n\r\n')
                if header_end == -1:
                    continue

                header = part[:header_end].decode('utf-8', errors='ignore')
                filename_match = re.search(r'filename="([^"]+)"', header)
                if not filename_match:
                    continue

                filename = filename_match.group(1)

                # Extract file data (skip headers and trailing boundary markers)
                file_data = part[header_end + 4:]
                # Remove trailing \r\n-- if present
                if file_data.endswith(b'\r\n'):
                    file_data = file_data[:-2]
                if file_data.endswith(b'--'):
                    file_data = file_data[:-2]
                if file_data.endswith(b'\r\n'):
                    file_data = file_data[:-2]

                return file_data, filename

        return None, None

    def format_dates(self, itinerary) -> str:
        """Format itinerary dates for display."""
        if itinerary.start_date and itinerary.end_date:
            if itinerary.start_date.year == itinerary.end_date.year:
                if itinerary.start_date.month == itinerary.end_date.month:
                    return f"{itinerary.start_date.strftime('%B')} {itinerary.start_date.year}"
                return f"{itinerary.start_date.strftime('%b')} - {itinerary.end_date.strftime('%b %Y')}"
            return f"{itinerary.start_date.strftime('%b %Y')} - {itinerary.end_date.strftime('%b %Y')}"
        elif itinerary.start_date:
            return itinerary.start_date.strftime('%B %Y')
        return "Date unknown"

    def send_json_response(self, data: dict):
        """Send JSON response."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def send_json_error(self, message: str, status: int = 400):
        """Send JSON error response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"success": False, "error": message}).encode())


def initialize_trips_data():
    """Initialize trips data file with existing trips if needed."""
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create output directory: {e}")

    if not TRIPS_DATA_FILE.exists():
        # Check for existing trip files and create initial data
        trips = []

        if (OUTPUT_DIR / "alaska_trip.html").exists():
            trips.append({
                "title": "Alaska Adventure Trip",
                "link": "alaska_trip.html",
                "dates": "August 2018",
                "days": 10,
                "locations": 5,
                "activities": 25,
            })

        if (OUTPUT_DIR / "seasia_trip.html").exists():
            trips.append({
                "title": "Vietnam, Cambodia & Singapore",
                "link": "seasia_trip.html",
                "dates": "December 2024",
                "days": 14,
                "locations": 6,
                "activities": 25,
            })

        save_trips_data(trips)

    # Regenerate trips page with upload area
    regenerate_trips_page()

    # Regenerate about page
    (OUTPUT_DIR / "about.html").write_text(generate_about_page())

    # Generate home page
    (OUTPUT_DIR / "index.html").write_text(generate_home_page())


def run_server(port: int = 8000):
    """Run the Libertas web server."""
    initialize_trips_data()

    # Ensure default admin user exists
    auth.ensure_default_user()

    # Bind to 0.0.0.0 for cloud deployment (Render, etc.)
    server = HTTPServer(('0.0.0.0', port), LibertasHandler)

    # Get auth info
    if auth.is_auth_enabled():
        auth_info = """
║   Authentication: ENABLED (database-backed)               ║
║   Default user: admin (set AUTH_USERNAME/AUTH_PASSWORD)   ║
║   Registration: /register.html                            ║
║   Set AUTH_DISABLED=true to disable authentication        ║"""
    else:
        auth_info = """
║   Authentication: DISABLED                                ║
║   Set AUTH_DISABLED=false to enable authentication        ║"""

    print(f"""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   LIBERTAS - Travel Freely                                ║
║                                                           ║
║   Server running at: http://localhost:{port:<5}              ║
║                                                           ║{auth_info}
║                                                           ║
║   Press Ctrl+C to stop                                    ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
""")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.shutdown()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the Libertas web server")
    parser.add_argument("-p", "--port", type=int, default=None, help="Port to run on (default: 8000)")
    args = parser.parse_args()

    # Use PORT env var (for Render), then --port arg, then default 8000
    port = args.port or int(os.environ.get("PORT", 8000))
    run_server(port)
