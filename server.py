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
from agents.itinerary.templates import generate_trips_page, generate_about_page, generate_home_page, generate_login_page

# Import authentication
import auth

# Allow OUTPUT_DIR to be configured via environment variable (for Render persistent disk)
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", Path(__file__).parent / "output"))
TRIPS_DATA_FILE = OUTPUT_DIR / "trips_data.json"


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


def regenerate_trips_page() -> None:
    """Regenerate the trips.html page with current trips data."""
    try:
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

        # API debug endpoint
        if path == "/api/debug":
            self.handle_debug()
            return

        # Check authentication for all other routes
        if not self.require_auth():
            return

        # Let parent class handle static files
        super().do_GET()

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

    def do_POST(self):
        """Handle POST requests (file uploads, URL imports, and auth)."""
        # Auth endpoints (no auth required)
        if self.path == "/api/login":
            self.handle_login()
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

        if auth.verify_credentials(username, password):
            # Create session and set cookie
            token = auth.create_session(username)

            # Determine if we should use Secure cookie (when on HTTPS)
            # For local dev, don't use Secure flag
            is_secure = self.headers.get('X-Forwarded-Proto') == 'https'

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Set-Cookie', auth.get_session_cookie_header(token, secure=is_secure))
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode())
        else:
            self.send_json_error("Invalid username or password", status=401)

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

            # Remove from trips data
            trips = load_trips_data()
            original_count = len(trips)
            trips = [t for t in trips if t.get("link") != link]

            if len(trips) == original_count:
                self.send_json_error("Trip not found")
                return

            save_trips_data(trips)

            # Delete the HTML file
            html_file = OUTPUT_DIR / link
            if html_file.exists():
                os.unlink(html_file)

            # Regenerate trips page
            regenerate_trips_page()

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

            # Find the trip
            trips = load_trips_data()
            trip = next((t for t in trips if t.get("link") == link), None)

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

            # Update trips data
            trips = load_trips_data()
            trip = next((t for t in trips if t.get("link") == link), None)

            if not trip:
                self.send_json_error("Trip not found")
                return

            # Update the title
            trip["title"] = new_title
            save_trips_data(trips)

            # Regenerate trips page
            regenerate_trips_page()

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

            # Update trips data
            trips = load_trips_data()
            trip = next((t for t in trips if t.get("link") == link), None)

            if not trip:
                self.send_json_error("Trip not found")
                return

            # Update fields if provided
            if 'title' in data and data['title']:
                trip["title"] = data['title']
            if 'dates' in data and data['dates']:
                trip["dates"] = data['dates']
            if 'days' in data:
                trip["days"] = int(data['days'])
            if 'locations' in data:
                trip["locations"] = int(data['locations'])
            if 'activities' in data:
                trip["activities"] = int(data['activities'])

            save_trips_data(trips)

            # Regenerate trips page
            regenerate_trips_page()

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

                # Parse the itinerary
                print(f"[UPLOAD] Step 1: Parsing file...")
                parser = ItineraryParser()
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
                }

                # Add to trips data (avoid duplicates by link)
                print(f"[UPLOAD] Step 3: Saving trip data...")
                trips = load_trips_data()
                trips = [t for t in trips if t.get("link") != output_file]
                trips.insert(0, trip_data)  # Add new trip at beginning
                save_trips_data(trips)
                print(f"[UPLOAD] Step 3 done: {time.time() - start_time:.1f}s - Saved {len(trips)} trips")

                # Regenerate trips page
                print(f"[UPLOAD] Step 4: Regenerating trips page...")
                regenerate_trips_page()
                print(f"[UPLOAD] Step 4 done: {time.time() - start_time:.1f}s")

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
            }

            # Add to trips data (avoid duplicates by link)
            trips = load_trips_data()
            trips = [t for t in trips if t.get("link") != output_file]
            trips.insert(0, trip_data)
            save_trips_data(trips)

            # Regenerate trips page
            regenerate_trips_page()

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

    # Bind to 0.0.0.0 for cloud deployment (Render, etc.)
    server = HTTPServer(('0.0.0.0', port), LibertasHandler)

    # Get auth info
    if auth.is_auth_enabled():
        username, password = auth.get_credentials()
        auth_info = f"""
║   Authentication: ENABLED                                 ║
║   Username: {username:<20}                        ║
║   Password: {password:<20}                        ║
║                                                           ║
║   Set AUTH_USERNAME and AUTH_PASSWORD env vars to change  ║
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
