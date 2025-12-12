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
from html.parser import HTMLParser

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

# Travel recommendations data - seed CSV for initial import (in repo for deployment)
VENUES_SEED_CSV = Path(__file__).parent / "data" / "venues_seed.csv"

# Cache for venues data
_venues_cache = None


def itinerary_to_data(itinerary) -> dict:
    """Convert a parsed Itinerary object to itinerary_data format for database storage.

    This format groups items by day number and is used for export/import.
    """
    from collections import defaultdict

    # Group items by day number
    days_dict = defaultdict(list)
    ideas = []

    for item in itinerary.items:
        if item.is_home_location:
            continue  # Skip home locations

        item_data = {
            'title': item.title,
            'category': item.category or 'activity',
            'location': item.location.name if item.location else '',
            'time': item.start_time.strftime('%H:%M') if item.start_time else None,
            'notes': item.notes or item.description,
        }

        if item.day_number:
            days_dict[item.day_number].append({
                **item_data,
                'date': item.date.isoformat() if item.date else None,
            })
        else:
            ideas.append(item_data)

    # Build days array
    days = []
    for day_num in sorted(days_dict.keys()):
        day_items = days_dict[day_num]
        day_date = None
        # Get date from first item with a date
        for di in day_items:
            if di.get('date'):
                day_date = di['date']
                break

        days.append({
            'day_number': day_num,
            'date': day_date,
            'items': day_items,
        })

    return {
        'title': itinerary.title,
        'start_date': itinerary.start_date.isoformat() if itinerary.start_date else None,
        'end_date': itinerary.end_date.isoformat() if itinerary.end_date else None,
        'travelers': itinerary.travelers or [],
        'days': days,
        'ideas': ideas,
    }


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


def fetch_webpage_for_chat(url: str) -> dict:
    """Fetch a web page and extract text for chat handlers.

    Returns dict with:
        success: bool
        text: str (extracted text content)
        title: str (page title if found)
        error: str (if failed)
    """
    try:
        content, filename, content_type = download_from_url(url)

        # Extract text from HTML
        if 'html' in content_type or filename.endswith('.html'):
            text = extract_text_from_html(content)
        else:
            # Try to decode as text
            try:
                text = content.decode('utf-8')
            except UnicodeDecodeError:
                text = content.decode('latin-1')

        # Try to extract page title from HTML
        title = None
        try:
            html_str = content.decode('utf-8', errors='ignore')
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html_str, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()
        except:
            pass

        # Limit text length for LLM context
        if len(text) > 15000:
            text = text[:15000] + "\n\n[Content truncated...]"

        return {
            'success': True,
            'text': text,
            'title': title or url,
            'url': url
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'url': url
        }


def cross_reference_venues(names: list[str], venues: list[dict]) -> list[dict]:
    """Cross-reference venue names against curated database.

    Returns list of dicts with source field indicating if found in curated DB.
    """
    results = []
    venues_lower = {v['name'].lower(): v for v in venues}

    for name in names:
        name_clean = name.strip()
        name_lower = name_clean.lower()

        # Try exact match first
        if name_lower in venues_lower:
            venue = venues_lower[name_lower].copy()
            venue['source'] = 'CURATED'
            results.append(venue)
        else:
            # Try fuzzy match (name contains or is contained)
            matched = False
            for v_name_lower, v in venues_lower.items():
                if name_lower in v_name_lower or v_name_lower in name_lower:
                    venue = v.copy()
                    venue['source'] = 'CURATED'
                    results.append(venue)
                    matched = True
                    break

            if not matched:
                # Not in curated DB - mark as AI_PICK
                results.append({
                    'name': name_clean,
                    'source': 'AI_PICK',
                    'venue_type': 'Restaurant',  # Default guess
                    'city': None,
                    'country': None
                })

    return results


def load_venues() -> list[dict]:
    """Load venues from database. Auto-imports from CSV if database is empty."""
    global _venues_cache
    if _venues_cache is not None:
        return _venues_cache

    # Check if venues exist in database
    venue_count = db.get_venue_count()

    if venue_count == 0:
        # Auto-import from seed CSV if database is empty
        if VENUES_SEED_CSV.exists():
            print(f"[Server] No venues in database, importing from {VENUES_SEED_CSV}...")
            imported = db.import_venues_from_csv(str(VENUES_SEED_CSV), source="curated")
            print(f"[Server] Imported {imported} venues from seed CSV")
        else:
            print(f"[Server] Warning: No venues in database and seed CSV not found at {VENUES_SEED_CSV}")
            return []

    # Load from database
    venues = db.get_all_venues()

    # Convert to expected format (ensure string fields are not None for frontend)
    formatted_venues = []
    for v in venues:
        formatted_venues.append({
            "id": v.get("id"),
            "name": v.get("name") or "",
            "city": v.get("city") or "",
            "state": v.get("state") or "",
            "country": v.get("country") or "",
            "address": v.get("address") or "",
            "latitude": v.get("latitude") or "",
            "longitude": v.get("longitude") or "",
            "venue_type": v.get("venue_type") or "",
            "cuisine_type": v.get("cuisine_type") or "",
            "michelin_stars": v.get("michelin_stars") or 0,
            "google_maps_link": v.get("google_maps_link") or "",
            "website": v.get("website") or "",
            "description": v.get("description") or "",
            "collection": v.get("collection") or "",
            "notes": v.get("notes") or "",
            "source": v.get("source") or "curated",
        })

    _venues_cache = formatted_venues
    print(f"[Server] Loaded {len(formatted_venues)} venues from database")
    return formatted_venues


def regenerate_trips_page(user_id: int) -> None:
    """Regenerate the trips.html page with current trips data from database."""
    try:
        trips = db.get_user_trips(user_id)
        html = generate_trips_page(trips)
        (OUTPUT_DIR / "trips.html").write_text(html)
    except Exception as e:
        print(f"Error regenerating trips page: {e}")
        import traceback
        traceback.print_exc()


def regenerate_all_trip_html(user_id: int = None) -> dict:
    """Regenerate HTML for all trips from their itinerary_data.

    Also fixes dates and days columns in the database.
    Returns dict with success count and errors.
    """
    from agents.create.handler import _convert_to_itinerary
    from agents.itinerary.templates import format_trip_date, get_trip_start_date

    results = {"regenerated": 0, "errors": [], "skipped": 0, "db_updated": 0}

    try:
        if user_id is not None:
            trips = db.get_user_trips(user_id)
        else:
            # Get all trips
            trips = db.get_user_trips(1)  # Default user

        for trip in trips:
            link = trip.get('link', '')
            title = trip.get('title', 'Unknown')
            itinerary_data_raw = trip.get('itinerary_data')
            current_dates = trip.get('dates', '')
            current_days = trip.get('days', 0)

            if not itinerary_data_raw or not link:
                results["skipped"] += 1
                print(f"[REGEN] Skipped {title}: no itinerary_data or link")
                continue

            try:
                # Parse itinerary_data if string
                if isinstance(itinerary_data_raw, str):
                    itinerary_data = json.loads(itinerary_data_raw)
                else:
                    itinerary_data = itinerary_data_raw

                # Convert to Itinerary object
                trip_for_convert = {'itinerary_data': itinerary_data, 'title': title}
                itinerary = _convert_to_itinerary(trip_for_convert)

                if not itinerary or not itinerary.items:
                    results["skipped"] += 1
                    print(f"[REGEN] Skipped {title}: could not convert to itinerary")
                    continue

                # Regenerate HTML
                web_view = ItineraryWebView()
                web_view.generate(itinerary, OUTPUT_DIR / link, use_ai_summary=False, skip_geocoding=True)
                results["regenerated"] += 1
                print(f"[REGEN] Regenerated {link}")

                # Fix dates and days in database if needed
                needs_update = False
                update_data = {}

                # Fix dates if missing, invalid, or in wrong format (date range like "2025-12-09 - 2025-12-09")
                needs_date_fix = (
                    not current_dates or
                    current_dates in ('Date unknown', 'None', '') or
                    ' - ' in current_dates  # Date range format needs reformatting
                )
                if needs_date_fix:
                    start_date = get_trip_start_date(itinerary_data)
                    if start_date:
                        formatted_date = format_trip_date(start_date)
                        if formatted_date != 'Date unknown':
                            update_data['dates'] = formatted_date
                            needs_update = True

                # Fix days count if missing
                if not current_days or current_days == 0:
                    days_count = (
                        itinerary.duration_days or
                        len(set(item.day_number for item in itinerary.items if item.day_number)) or
                        len(itinerary_data.get('days', []))
                    )
                    if days_count > 0:
                        update_data['days'] = days_count
                        needs_update = True

                # Update database if needed
                if needs_update and user_id:
                    db.update_trip(user_id, link, update_data)
                    results["db_updated"] += 1
                    print(f"[REGEN] Updated DB for {title}: {update_data}")

            except Exception as e:
                results["errors"].append(f"{title}: {str(e)}")
                print(f"[REGEN] Error regenerating {title}: {e}")

        # Also regenerate trips list page
        regenerate_trips_page(user_id)

    except Exception as e:
        results["errors"].append(f"Fatal error: {str(e)}")
        print(f"[REGEN] Fatal error: {e}")
        import traceback
        traceback.print_exc()

    return results


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

        # Explore API endpoints - public, no auth required
        if path == "/api/explore/venues":
            self.handle_explore_venues()
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

        # API endpoint for trip data (for create/edit)
        if path.startswith("/api/trips/") and path.endswith("/data"):
            link = path[len("/api/trips/"):-len("/data")]
            self.handle_get_trip_data(link)
            return

        # API endpoint for trip export (download JSON)
        if path.startswith("/api/trips/") and path.endswith("/export"):
            link = path[len("/api/trips/"):-len("/export")]
            self.handle_export_trip(link)
            return

        # API endpoint to check if user can edit a trip (owns it)
        if path.startswith("/api/trip/") and path.endswith("/can-edit"):
            link = path[len("/api/trip/"):-len("/can-edit")]
            self.handle_can_edit_trip(link)
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

    def handle_export_trip(self, link: str):
        """Export trip data as downloadable JSON."""
        user_id = self.get_current_user_id()
        result, status = create_handler.export_trip_handler(user_id, link)
        if status == 200:
            export_data = result.get('export', {})
            title = export_data.get('title', 'trip')
            # Sanitize filename
            safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
            filename = f"{safe_title}_export.json"

            json_bytes = json.dumps(export_data, indent=2).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Content-Length', len(json_bytes))
            self.end_headers()
            self.wfile.write(json_bytes)
        else:
            self.send_json_error(result.get('error', 'Unknown error'), status=status)

    def handle_can_edit_trip(self, link: str):
        """Check if current user can edit a trip (i.e., owns it)."""
        user_id = self.get_current_user_id()
        owner_id = db.get_trip_owner(link)

        if owner_id is None:
            self.send_json_error("Trip not found", status=404)
            return

        can_edit = (owner_id == user_id)
        self.send_json_response({"canEdit": can_edit})

    def serve_trip_html(self, path: str):
        """Serve trip HTML files with updated navigation injected."""
        # Security: prevent directory traversal
        if ".." in path:
            self.send_error(403, "Forbidden")
            return

        # Remove leading slash and /trip/ prefix, look in output folder
        filename = path.lstrip("/")
        if filename.startswith("trip/"):
            filename = filename[5:]  # Remove "trip/" prefix
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
        """Handle chat messages for explore feature with Claude LLM.

        Supports:
        - Curated venue search from database
        - Web page fetching for external lists (Eater, etc.)
        - AI suggestions beyond curated database
        - Source tagging (CURATED vs AI_PICK)
        """
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

Top cities: {', '.join(f"{k} ({v})" for k, v in sorted(cities.items(), key=lambda x: -x[1])[:20])}

States/Regions: {', '.join(f"{k} ({v})" for k, v in sorted(states.items(), key=lambda x: -x[1])[:30] if k)}

Countries: {', '.join(sorted(countries.keys()))}

## CAPABILITIES

1. **Curated Database Search**: Search the venue list below for trusted, vetted recommendations
2. **Web Fetch**: Use the fetch_web_page tool to read external lists (Eater, Infatuation, blogs, etc.)
3. **AI Suggestions**: Recommend places not in the database (will be marked as AI picks)

## WHEN TO USE WEB FETCH

Use the fetch_web_page tool when users mention:
- External lists: "Eater 38", "Infatuation", "Michelin Guide website", blog posts
- Specific URLs they want to check
- "Check this page for recommendations"

## RESPONSE FORMAT

Return venues in a JSON block with source tags:
```json
{{"venues": [
    {{"name": "Roscioli", "source": "CURATED"}},
    {{"name": "Some AI Pick", "source": "AI_PICK", "city": "Rome", "venue_type": "Restaurant", "notes": "Brief description"}}
]}}
```

- Use "CURATED" for venues from the database (name must match exactly)
- Use "AI_PICK" for recommendations not in the database (include city, venue_type, notes)
- Include collection field if relevant (e.g., "Eater 38 Rome" for web-fetched venues)

## IMPORTANT RULES

- Route queries: Include intermediate stops (SF to Alaska = Oregon, Washington, Vancouver, etc.)
- Up to 30 venues for route queries, 20 for regular searches
- Curated venues should appear first in the list
- Be concise and practical, no flowery language"""

            # Define tools
            tools = [
                {
                    "name": "fetch_web_page",
                    "description": "Fetch a web page to extract venue recommendations. Use this when users mention external lists like Eater, Infatuation, blog posts, or provide URLs.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "The URL to fetch. For 'Eater 38 Rome', construct URL like 'https://www.eater.com/maps/best-restaurants-rome'"
                            }
                        },
                        "required": ["url"]
                    }
                }
            ]

            # Build messages from history
            messages = []
            for h in history[-10:]:  # Last 10 messages
                role = h.get('role', 'user')
                if role in ['user', 'assistant']:
                    messages.append({"role": role, "content": h.get('content', '')})

            # Organize venues by state/region for better route query support
            venues_by_region = {}
            for v in venues:
                region = v.get('state') or v.get('country') or 'Other'
                if region not in venues_by_region:
                    venues_by_region[region] = []
                venues_by_region[region].append(v)

            # Build venue context organized by region with rich details
            venue_context = "Here are all venues in the database, organized by state/region:\n\n"
            for region in sorted(venues_by_region.keys()):
                region_venues = venues_by_region[region]
                venue_context += f"=== {region} ({len(region_venues)} venues) ===\n"
                for v in region_venues:
                    venue_context += f"- {v['name']}"
                    if v.get('city'):
                        venue_context += f", {v['city']}"
                    if v.get('venue_type'):
                        venue_context += f" ({v['venue_type']})"
                    if v.get('cuisine_type'):
                        venue_context += f" [{v['cuisine_type']}]"
                    if v.get('michelin_stars'):
                        venue_context += f" ⭐{v['michelin_stars']} Michelin"
                    if v.get('collection') and v['collection'] not in ('Saved', None):
                        venue_context += f" #{v['collection']}"
                    # Add description for smarter recommendations
                    if v.get('description'):
                        desc = v['description'][:150].replace('\n', ' ')
                        venue_context += f" | {desc}"
                    elif v.get('notes'):
                        notes = v['notes'][:100].replace('\n', ' ')
                        venue_context += f" | {notes}"
                    venue_context += "\n"
                venue_context += "\n"

            # Add venue list to the user message
            messages.append({"role": "user", "content": f"{message}\n\n---\n{venue_context}"})

            # Tool use loop - handle multiple rounds if Claude calls tools
            max_iterations = 3
            web_fetch_context = None

            for iteration in range(max_iterations):
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2000,
                    system=system_prompt,
                    messages=messages,
                    tools=tools
                )

                # Check if Claude wants to use a tool
                tool_use_block = None
                text_block = None

                for block in response.content:
                    if block.type == "tool_use":
                        tool_use_block = block
                    elif block.type == "text":
                        text_block = block

                if tool_use_block and tool_use_block.name == "fetch_web_page":
                    # Execute the web fetch
                    url = tool_use_block.input.get("url", "")
                    print(f"[EXPLORE] Fetching web page: {url}")

                    fetch_result = fetch_webpage_for_chat(url)

                    if fetch_result['success']:
                        web_fetch_context = {
                            'url': url,
                            'title': fetch_result.get('title', url)
                        }
                        tool_result_content = f"Successfully fetched page: {fetch_result['title']}\n\nContent:\n{fetch_result['text']}"
                    else:
                        tool_result_content = f"Failed to fetch page: {fetch_result.get('error', 'Unknown error')}"

                    # Add assistant message with tool use and tool result
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": tool_use_block.id,
                            "content": tool_result_content
                        }]
                    })
                    # Continue loop for Claude to process the result
                    continue

                # No more tool calls - we have the final response
                break

            # Extract final response text
            assistant_response = ""
            for block in response.content:
                if block.type == "text":
                    assistant_response = block.text
                    break

            # Extract venue data from JSON block
            matched_venues = []
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', assistant_response, re.DOTALL)

            if json_match:
                try:
                    venue_data = json.loads(json_match.group(1))
                    venue_list = venue_data.get('venues', [])

                    for item in venue_list:
                        # Handle both string names (old format) and dict format (new)
                        if isinstance(item, str):
                            name = item
                            source = "CURATED"
                            extra = {}
                        else:
                            name = item.get('name', '')
                            source = item.get('source', 'CURATED')
                            extra = {k: v for k, v in item.items() if k not in ('name', 'source')}

                        # Try to match against curated database
                        matched = False
                        name_lower = name.lower().strip()
                        print(f"[EXPLORE] Matching venue: '{name}'")

                        # First try exact match
                        for v in venues:
                            if v['name'].lower() == name_lower:
                                venue_copy = v.copy()
                                venue_copy['source'] = 'CURATED'
                                if web_fetch_context and not venue_copy.get('collection'):
                                    venue_copy['collection'] = web_fetch_context.get('title', '')[:50]
                                matched_venues.append(venue_copy)
                                matched = True
                                has_coords = bool(venue_copy.get('latitude') and venue_copy.get('longitude'))
                                print(f"[EXPLORE]   -> EXACT match: {v['name']} (coords: {has_coords})")
                                break

                        # If no exact match, try partial match (name contains or is contained)
                        if not matched:
                            for v in venues:
                                v_name_lower = v['name'].lower()
                                if name_lower in v_name_lower or v_name_lower in name_lower:
                                    venue_copy = v.copy()
                                    venue_copy['source'] = 'CURATED'
                                    if web_fetch_context and not venue_copy.get('collection'):
                                        venue_copy['collection'] = web_fetch_context.get('title', '')[:50]
                                    matched_venues.append(venue_copy)
                                    matched = True
                                    has_coords = bool(venue_copy.get('latitude') and venue_copy.get('longitude'))
                                    print(f"[EXPLORE]   -> PARTIAL match: {v['name']} (coords: {has_coords})")
                                    break

                        if not matched:
                            # Not found in database - add as AI_PICK
                            ai_venue = {
                                'name': name,
                                'source': 'AI_PICK',
                                'venue_type': extra.get('venue_type', 'Restaurant'),
                                'city': extra.get('city', ''),
                                'country': extra.get('country', ''),
                                'notes': extra.get('notes', ''),
                                'collection': web_fetch_context.get('title', '')[:50] if web_fetch_context else ''
                            }
                            matched_venues.append(ai_venue)
                            print(f"[EXPLORE]   -> NO MATCH, added as AI_PICK")

                    # Remove JSON block from response text
                    assistant_response = re.sub(r'```json\s*\{.*?\}\s*```', '', assistant_response, flags=re.DOTALL).strip()
                except json.JSONDecodeError:
                    pass

            # Sort: CURATED first, then AI_PICK
            matched_venues.sort(key=lambda v: (0 if v.get('source') == 'CURATED' else 1, v.get('name', '')))

            self.send_json_response({
                "response": assistant_response,
                "venues": matched_venues,
            })

        except anthropic.APIError as e:
            # Fallback to simple search if Claude API fails
            print(f"Claude API error: {e}")
            matched_venues = self.simple_venue_search(message, venues)

            # Add source field to fallback results
            for v in matched_venues:
                v['source'] = 'CURATED'

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

        # Check trips and users from database
        try:
            with db.get_db() as conn:
                cursor = conn.cursor()

                # User count
                cursor.execute("SELECT COUNT(*) FROM users")
                debug_info["users_count"] = cursor.fetchone()[0]

                # Trip count and details
                cursor.execute("SELECT COUNT(*) FROM trips")
                debug_info["trips_count"] = cursor.fetchone()[0]

                cursor.execute("SELECT id, user_id, title, link FROM trips ORDER BY created_at DESC LIMIT 10")
                debug_info["trips"] = [
                    {"id": row[0], "user_id": row[1], "title": row[2], "link": row[3]}
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            debug_info["trips_error"] = str(e)

        # Venue database info
        try:
            # Check for reimport request
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            if params.get('reimport_venues'):
                global _venues_cache
                _venues_cache = None  # Clear cache
                if VENUES_SEED_CSV.exists():
                    imported = db.import_venues_from_csv(str(VENUES_SEED_CSV), source="curated")
                    debug_info["reimport_result"] = f"Imported {imported} venues"
                else:
                    debug_info["reimport_result"] = "CSV not found"

            # Geocode missing venues
            if params.get('geocode_missing'):
                from geocode_venues import geocode_address
                venues = load_venues()
                missing = [v for v in venues if not v.get('latitude') or not v.get('longitude')]
                debug_info["geocode_total_missing"] = len(missing)

                geocoded = 0
                failed = 0
                results = []
                for v in missing[:50]:  # Limit to 50 at a time to avoid timeout
                    name = v.get('name', '')
                    city = v.get('city', '')
                    country = v.get('country', '')
                    lat, lng = geocode_address(name, city, country)
                    if lat and lng:
                        db.update_venue_coordinates(v['id'], lat, lng)
                        geocoded += 1
                        results.append(f"✓ {name}: {lat:.4f}, {lng:.4f}")
                    else:
                        # Try city-level fallback
                        lat, lng = geocode_address("", city, country)
                        if lat and lng:
                            db.update_venue_coordinates(v['id'], lat, lng)
                            geocoded += 1
                            results.append(f"✓ {name} (city-level): {lat:.4f}, {lng:.4f}")
                        else:
                            failed += 1
                            results.append(f"✗ {name}: NOT FOUND")
                    import time
                    time.sleep(1.1)  # Nominatim rate limit

                _venues_cache = None  # Clear cache
                debug_info["geocode_result"] = f"Geocoded {geocoded}, failed {failed}"
                debug_info["geocode_details"] = results

            venue_count = db.get_venue_count()
            debug_info["venue_count"] = venue_count
            debug_info["venues_seed_csv"] = str(VENUES_SEED_CSV)
            debug_info["venues_seed_exists"] = VENUES_SEED_CSV.exists()

            # Show venue distribution by state
            if venue_count > 0:
                stats = db.get_venue_stats()
                debug_info["venues_by_state"] = dict(list(stats.get("by_state", {}).items())[:15])
                debug_info["venues_by_country"] = stats.get("by_country", {})
        except Exception as e:
            debug_info["venue_error"] = str(e)

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

        # Explore chat - public, no auth required
        if self.path == "/api/explore/chat":
            self.handle_explore_chat()
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
        elif self.path == "/api/trips/create":
            self.handle_create_trip()
        elif self.path == "/api/create/chat":
            self.handle_create_chat()
        elif self.path == "/api/create/upload-plan":
            self.handle_upload_plan()
        elif self.path.startswith("/api/trips/") and self.path.endswith("/save"):
            link = self.path[len("/api/trips/"):-len("/save")].rstrip('/')
            self.handle_save_trip(link)
        elif self.path.startswith("/api/trips/") and self.path.endswith("/publish"):
            link = self.path[len("/api/trips/"):-len("/publish")].rstrip('/')
            self.handle_publish_trip(link)
        elif self.path.startswith("/api/trips/") and self.path.endswith("/items"):
            link = self.path[len("/api/trips/"):-len("/items")].rstrip('/')
            self.handle_add_trip_item(link)
        elif self.path == "/api/regenerate-all-trips":
            self.handle_regenerate_all_trips()
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

    def handle_regenerate_all_trips(self):
        """Regenerate HTML for all trips from their itinerary_data."""
        if not self.require_auth():
            return

        user_id = self.get_current_user_id()
        results = regenerate_all_trip_html(user_id)

        self.send_json_response({
            "success": True,
            "regenerated": results["regenerated"],
            "skipped": results["skipped"],
            "errors": results["errors"]
        })

    def handle_retry_geocoding(self):
        """Retry geocoding for a trip - regenerate map with fresh geocoding."""
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

        # Get itinerary_data from database
        itinerary_data = trip.get('itinerary_data')
        if not itinerary_data:
            self.send_json_error("No itinerary data available for this trip")
            return

        # Parse itinerary_data if it's a string
        if isinstance(itinerary_data, str):
            try:
                itinerary_data = json.loads(itinerary_data)
            except:
                self.send_json_error("Invalid itinerary data format")
                return

        # Convert to Itinerary object
        from agents.create.handler import _convert_to_itinerary
        trip_for_convert = {'itinerary_data': itinerary_data, 'title': trip.get('title', 'Trip')}
        itinerary = _convert_to_itinerary(trip_for_convert)

        if not itinerary:
            self.send_json_error("Could not parse itinerary data")
            return

        # Reset status to pending and queue for geocoding
        db.update_trip_map_status(user_id, link, "pending", None)
        geocoding_worker.queue_geocoding(link, itinerary)

        self.send_json_response({
            "success": True,
            "message": "Map regeneration queued. Please refresh the page in a few moments.",
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
        """Copy a trip to current user (for editing shared/public trips)."""
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

            user_id = self.get_current_user_id()

            # Copy the trip to current user
            result = db.copy_trip_by_link(link, user_id)

            if not result:
                self.send_json_error("Trip not found")
                return

            new_link = result.get('new_link')
            was_copied = result.get('was_copied', True)

            # If it was actually copied (not owned by user), generate HTML
            if was_copied and new_link:
                # Get the new trip and generate HTML
                new_trip = db.get_trip_by_link(user_id, new_link)
                if new_trip and new_trip.get('itinerary_data'):
                    from agents.create.handler import _convert_to_itinerary
                    trip_for_html = {'itinerary_data': new_trip['itinerary_data'], 'title': new_trip['title']}
                    itinerary = _convert_to_itinerary(trip_for_html)
                    if itinerary and itinerary.items:
                        web_view = ItineraryWebView()
                        web_view.generate(itinerary, OUTPUT_DIR / new_link, use_ai_summary=False, skip_geocoding=True)
                        print(f"[COPY] Generated HTML for copied trip: {new_link}")

            self.send_json_response({
                "success": True,
                "new_link": new_link,
                "was_copied": was_copied,
                "message": "Trip copied to your trips" if was_copied else "You already own this trip",
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
            valid_extensions = ['.pdf', '.xlsx', '.xls', '.html', '.htm', '.json']
            if suffix not in valid_extensions:
                self.send_json_error(f"Invalid file type '{suffix}'. Supported: PDF, Excel, HTML, JSON")
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

                # Check file type
                is_html_file = suffix.lower() in ['.html', '.htm']
                is_json_file = suffix.lower() == '.json'

                # Handle JSON import (exported trip data)
                if is_json_file:
                    print(f"[UPLOAD] Importing JSON trip data...")
                    try:
                        import_data = json.loads(file_data.decode('utf-8'))
                    except json.JSONDecodeError as e:
                        self.send_json_error(f"Invalid JSON file: {e}")
                        return

                    # Check if it's an exported trip format
                    if 'itinerary_data' not in import_data and 'days' not in import_data:
                        self.send_json_error("JSON file is not a valid trip export")
                        return

                    # Get itinerary_data (either directly or from export wrapper)
                    itinerary_data = import_data.get('itinerary_data') or import_data
                    title = itinerary_data.get('title') or import_data.get('title', 'Imported Trip')

                    # Generate HTML from itinerary_data
                    slug = slugify(title)
                    output_file = f"{slug}.html"

                    # Convert itinerary_data to Itinerary object for HTML generation
                    trip_for_html = {'itinerary_data': itinerary_data, 'title': title}
                    from agents.create.handler import _convert_to_itinerary
                    itinerary = _convert_to_itinerary(trip_for_html)

                    if not itinerary or not itinerary.items:
                        self.send_json_error("Could not parse trip data from JSON")
                        return

                    web_view = ItineraryWebView()
                    web_view.generate(itinerary, OUTPUT_DIR / output_file, use_ai_summary=False, skip_geocoding=True)
                    print(f"[UPLOAD] Generated HTML: {output_file}")

                    # Count stats
                    locations = set()
                    for item in itinerary.items:
                        if item.location.name and not item.is_home_location:
                            locations.add(item.location.name.split(',')[0])

                    # Build trip data
                    # Calculate days - try multiple sources
                    days_count = (
                        itinerary.duration_days or
                        len(set(item.day_number for item in itinerary.items if item.day_number)) or
                        len(itinerary_data.get('days', []))
                    )
                    trip_data = {
                        "title": title,
                        "link": output_file,
                        "dates": self.format_dates(itinerary),
                        "days": days_count,
                        "locations": len(locations),
                        "activities": len(itinerary.items),
                        "map_status": "pending",
                        "is_public": import_data.get('is_public', False),
                    }

                    # Add trip to database (itinerary_data passed separately)
                    user_id = self.get_current_user_id()
                    db.add_trip(user_id, trip_data, itinerary_data)
                    print(f"[UPLOAD] Saved trip for user {user_id}")

                    # Queue geocoding
                    geocoding_worker.queue_geocoding(output_file, itinerary)

                    # Clean up and respond
                    os.unlink(tmp_path)
                    self.send_json_response({
                        "success": True,
                        "title": title,
                        "link": output_file,
                    })
                    return

                # Parse the itinerary (PDF, Excel, HTML)
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

                # Build trip data with full itinerary for export
                trip_data = {
                    "title": itinerary.title,
                    "link": output_file,
                    "dates": self.format_dates(itinerary),
                    "days": itinerary.duration_days or len(set(item.day_number for item in itinerary.items if item.day_number)),
                    "locations": len(locations),
                    "activities": len(itinerary.items),
                    "map_status": "pending",  # Map will be generated async
                    "itinerary_data": itinerary_to_data(itinerary),  # Full data for export
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
                # Clean up temp file if it still exists
                if os.path.exists(tmp_path):
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

            # Build trip data with full itinerary for export
            trip_data = {
                "title": itinerary.title,
                "link": output_file,
                "dates": self.format_dates(itinerary),
                "days": itinerary.duration_days or len(set(item.day_number for item in itinerary.items if item.day_number)),
                "locations": len(locations),
                "activities": len(itinerary.items),
                "map_status": "pending",  # Map will be generated async
                "itinerary_data": itinerary_to_data(itinerary),  # Full data for export
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


def initialize_server():
    """Initialize server directories and static pages."""
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create output directory: {e}")

    # Generate static pages
    (OUTPUT_DIR / "about.html").write_text(generate_about_page())
    (OUTPUT_DIR / "index.html").write_text(generate_home_page())


def run_server(port: int = 8000):
    """Run the Libertas web server."""
    initialize_server()

    # Ensure default admin user exists
    auth.ensure_default_user()

    # Start geocoding worker (also recovers stale pending tasks from database)
    geocoding_worker.start_worker()

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
