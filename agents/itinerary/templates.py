"""Shared HTML templates and components for Libertas."""

from pathlib import Path

# Path to static files and templates
STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"


def get_static_css(filename: str) -> str:
    """Read a CSS file from the static directory."""
    css_path = STATIC_DIR / "css" / filename
    if css_path.exists():
        return css_path.read_text()
    return ""


def get_static_js(filename: str) -> str:
    """Read a JS file from the static directory."""
    js_path = STATIC_DIR / "js" / filename
    if js_path.exists():
        return js_path.read_text()
    return ""


def get_template(filename: str) -> str:
    """Read an HTML template file."""
    template_path = TEMPLATES_DIR / filename
    if template_path.exists():
        return template_path.read_text()
    return ""


def get_nav_html(active_page: str = "") -> str:
    """Get navigation HTML with the specified page marked as active."""
    return NAV_HTML.format(
        home_active="active" if active_page == "home" else "",
        trips_active="active" if active_page == "trips" else "",
        about_active="active" if active_page == "about" else "",
    )


NAV_HTML = """
<nav class="libertas-nav">
    <a href="index.html" class="brand">
        <i class="fas fa-feather-alt brand-icon"></i>
        <div>
            <div class="brand-name">LIBERTAS</div>
            <div class="brand-tagline">Travel freely</div>
        </div>
    </a>
    <div class="nav-links">
        <a href="index.html" class="nav-link {home_active}"><i class="fas fa-home"></i> Home</a>
        <a href="trips.html" class="nav-link {trips_active}"><i class="fas fa-route"></i> My Trips</a>
        <a href="about.html" class="nav-link {about_active}"><i class="fas fa-scroll"></i> About</a>
        <a href="#" class="nav-link logout-link" onclick="logout(); return false;"><i class="fas fa-sign-out-alt"></i> Logout</a>
    </div>
</nav>
<script>
function logout() {{
    fetch('/api/logout', {{ method: 'POST' }})
        .then(function() {{ window.location.href = '/login.html'; }})
        .catch(function() {{ window.location.href = '/login.html'; }});
}}
</script>
"""


ABOUT_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>About - Libertas</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <style>
{main_css}

{about_css}
    </style>
</head>
<body>
    {nav_html}

    <div class="about-hero">
        <h1>LIBERTAS</h1>
        <p class="subtitle">An agentic travel companion inspired by the Roman gods</p>
    </div>

    <div class="about-content">
        <div class="about-section">
            <h2><i class="fas fa-scroll"></i> The Inspiration</h2>
            <p>
                In ancient Rome, travelers would invoke the protection of <span class="latin">Abeona</span> and
                <span class="latin">Adeona</span> — twin goddesses who watched over journeys. Abeona
                (from <span class="latin">abeo</span>, "I depart") guarded those setting out, while Adeona
                (from <span class="latin">adeo</span>, "I return") ensured their safe homecoming.
            </p>
            <p>
                According to the Roman author Varro, statues of these goddesses stood alongside
                <span class="latin">Libertas</span>, the goddess of freedom, on the Aventine Hill — signifying
                that true liberty includes the freedom to journey forth and return as one wishes.
            </p>

            <div class="deity-cards">
                <div class="deity-card abeona">
                    <div class="icon"><i class="fas fa-plane-departure"></i></div>
                    <h3>Abeona</h3>
                    <div class="latin-name">"She who goes forth"</div>
                    <p>Goddess of outward journeys, protecting travelers as they depart and children taking their first steps into the world.</p>
                </div>
                <div class="deity-card adeona">
                    <div class="icon"><i class="fas fa-plane-arrival"></i></div>
                    <h3>Adeona</h3>
                    <div class="latin-name">"She who returns"</div>
                    <p>Goddess of safe returns, watching over travelers as they journey home and ensuring reunions with loved ones.</p>
                </div>
                <div class="deity-card libertas">
                    <div class="icon"><i class="fas fa-feather-alt"></i></div>
                    <h3>Libertas</h3>
                    <div class="latin-name">"Freedom"</div>
                    <p>Goddess of liberty, whose presence with Abeona and Adeona symbolizes the freedom to travel as one pleases.</p>
                </div>
            </div>
        </div>

        <div class="quote-box">
            <blockquote>
                "The statues of Abeona and Adeona accompanied the statue of Libertas,
                signifying that freedom could go and return as she wished."
            </blockquote>
            <cite>— Marcus Terentius Varro, Antiquitates rerum divinarum</cite>
        </div>

        <div class="about-section">
            <h2><i class="fas fa-robot"></i> What is Libertas?</h2>
            <p>
                Libertas is an agentic travel solution — a collection of intelligent agents that help you
                plan, organize, and visualize your journeys. Like the Roman deities who watched over
                travelers, our agents work together to ensure smooth travels.
            </p>

            <div class="features-grid">
                <div class="feature">
                    <i class="fas fa-file-import"></i>
                    <div class="feature-text">
                        <h4>Import Itineraries</h4>
                        <p>Parse existing trip plans from PDFs and spreadsheets</p>
                    </div>
                </div>
                <div class="feature">
                    <i class="fas fa-brain"></i>
                    <div class="feature-text">
                        <h4>AI-Powered</h4>
                        <p>Intelligent extraction of dates, locations, and activities</p>
                    </div>
                </div>
                <div class="feature">
                    <i class="fas fa-map-marked-alt"></i>
                    <div class="feature-text">
                        <h4>Visual Maps</h4>
                        <p>Interactive maps showing your complete journey</p>
                    </div>
                </div>
                <div class="feature">
                    <i class="fas fa-list-alt"></i>
                    <div class="feature-text">
                        <h4>Smart Summaries</h4>
                        <p>Clear, organized views of your travel plans</p>
                    </div>
                </div>
            </div>
        </div>

        <div class="about-section">
            <h2><i class="fas fa-code"></i> Open Source</h2>
            <p>
                Libertas is built with Python and uses Claude AI for intelligent document parsing.
                The project is designed to be modular, with specialized agents for different aspects
                of travel planning — itineraries, maps, and more to come.
            </p>
        </div>
    </div>

    <script>
{main_js}
    </script>
</body>
</html>
"""


def generate_about_page() -> str:
    """Generate the About page HTML with embedded CSS/JS."""
    template = get_template("about.html")
    return template.format(
        main_css=get_static_css("main.css"),
        about_css=get_static_css("about.css"),
        nav_html=get_nav_html("about"),
        main_js=get_static_js("main.js"),
    )


TRIPS_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Trips - Libertas</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <style>
{main_css}

{trips_css}
    </style>
</head>
<body>
    {nav_html}

    <div class="trips-header">
        <h1><i class="fas fa-route"></i> My Trips</h1>
        <p>Your travel adventures, organized and visualized</p>
    </div>

    <div class="trips-container">
        <div class="upload-section">
            <div class="upload-area" id="upload-area">
                <i class="fas fa-cloud-upload-alt"></i>
                <h3>Import a Trip</h3>
                <p>Drag and drop your itinerary file here, or click to browse</p>
                <button class="upload-btn">
                    <i class="fas fa-folder-open"></i> Choose File
                </button>
                <p class="supported-formats">Supported formats: PDF, Excel (.xlsx, .xls)</p>
                <input type="file" id="upload-input" class="upload-input" accept=".pdf,.xlsx,.xls">
            </div>

            <div class="url-import-section">
                <div class="url-divider">
                    <span>or import from URL</span>
                </div>
                <div class="url-input-wrapper">
                    <input type="text" id="url-input" class="url-input" placeholder="Paste Google Drive or TripIt link...">
                    <button id="url-submit" class="url-submit-btn">
                        <i class="fas fa-link"></i> Import
                    </button>
                </div>
                <p class="url-hint">Supports Google Drive, TripIt, and other itinerary pages or direct file links</p>
            </div>

            <div id="upload-status" class="upload-status"></div>
        </div>

        <div class="trips-grid">
{trip_cards}
        </div>
    </div>

    <script>
{main_js}

{upload_js}
    </script>
</body>
</html>
"""

TRIP_CARD_TEMPLATE = """
            <div class="trip-card-wrapper" data-link="{link}">
                <a href="{link}" class="trip-card">
                    <div class="trip-card-image" style="background: {gradient};">
                        <i class="fas fa-{icon}"></i>
                        <span class="trip-card-region">{region}</span>
                    </div>
                    <div class="trip-card-content">
                        <div class="trip-card-title">{title}</div>
                        <div class="trip-card-meta">
                            <span><i class="fas fa-calendar"></i> {dates}</span>
                        </div>
                        <div class="trip-card-stats">
                            <div class="trip-stat">
                                <div class="trip-stat-value">{days}</div>
                                <div class="trip-stat-label">Days</div>
                            </div>
                            <div class="trip-stat">
                                <div class="trip-stat-value">{locations}</div>
                                <div class="trip-stat-label">Locations</div>
                            </div>
                            <div class="trip-stat">
                                <div class="trip-stat-value">{activities}</div>
                                <div class="trip-stat-label">Activities</div>
                            </div>
                        </div>
                    </div>
                </a>
                <div class="trip-card-actions">
                    <button class="trip-action-btn edit-btn" title="Edit trip" data-link="{link}" data-title="{title}" data-dates="{dates}" data-days="{days}" data-locations="{locations}" data-activities="{activities}">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="trip-action-btn copy-btn" title="Copy to new trip" data-link="{link}">
                        <i class="fas fa-copy"></i>
                    </button>
                    <button class="trip-action-btn delete-btn" title="Delete trip" data-link="{link}">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
"""

# Destination-specific background images (using Unsplash for free images)
DESTINATION_IMAGES = {
    "india": "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=600&q=80",  # Taj Mahal
    "rajasthan": "https://images.unsplash.com/photo-1477587458883-47145ed94245?w=600&q=80",  # Jaipur Palace
    "delhi": "https://images.unsplash.com/photo-1587474260584-136574528ed5?w=600&q=80",  # India Gate
    "jaipur": "https://images.unsplash.com/photo-1599661046289-e31897846e41?w=600&q=80",  # Hawa Mahal
    "agra": "https://images.unsplash.com/photo-1564507592333-c60657eea523?w=600&q=80",  # Taj Mahal
    "jaisalmer": "https://images.unsplash.com/photo-1477587458883-47145ed94245?w=600&q=80",  # Desert fort
    "alaska": "https://images.unsplash.com/photo-1531176175280-33e139f1fbb3?w=600&q=80",  # Alaska mountains
    "vietnam": "https://images.unsplash.com/photo-1528127269322-539801943592?w=600&q=80",  # Ha Long Bay
    "cambodia": "https://images.unsplash.com/photo-1539650116574-8efeb43e2750?w=600&q=80",  # Angkor Wat
    "singapore": "https://images.unsplash.com/photo-1525625293386-3f8f99389edd?w=600&q=80",  # Marina Bay
    "japan": "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?w=600&q=80",  # Mt Fuji
    "thailand": "https://images.unsplash.com/photo-1528181304800-259b08848526?w=600&q=80",  # Thai temple
    "europe": "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?w=600&q=80",  # Paris
    "france": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=600&q=80",  # Eiffel Tower
    "italy": "https://images.unsplash.com/photo-1523906834658-6e24ef2386f9?w=600&q=80",  # Venice
    "africa": "https://images.unsplash.com/photo-1516426122078-c23e76319801?w=600&q=80",  # Safari
    "hawaii": "https://images.unsplash.com/photo-1507876466758-bc54f384809c?w=600&q=80",  # Beach
    "caribbean": "https://images.unsplash.com/photo-1548574505-5e239809ee19?w=600&q=80",  # Tropical beach
}

# Fallback gradient colors for trip cards (when no image matches)
TRIP_GRADIENTS = [
    "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
    "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
    "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)",
    "linear-gradient(135deg, #fa709a 0%, #fee140 100%)",
    "linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)",
]

# Icons for different regions
REGION_ICONS = {
    "india": "om",
    "rajasthan": "gopuram",
    "alaska": "mountain",
    "asia": "torii-gate",
    "europe": "landmark",
    "africa": "globe-africa",
    "americas": "globe-americas",
    "oceania": "umbrella-beach",
    "default": "plane",
}


def get_destination_image(title: str):
    """Get a destination-specific image URL based on trip title."""
    title_lower = title.lower()
    for destination, url in DESTINATION_IMAGES.items():
        if destination in title_lower:
            return url
    return None


def get_region_icon(title: str) -> str:
    """Get an appropriate icon based on trip title/region."""
    title_lower = title.lower()
    if any(x in title_lower for x in ["india", "delhi", "agra", "jaipur", "jaisalmer", "rajasthan"]):
        return "om"
    elif "alaska" in title_lower:
        return "mountain"
    elif any(x in title_lower for x in ["asia", "vietnam", "cambodia", "thailand", "japan", "china", "singapore"]):
        return "torii-gate"
    elif any(x in title_lower for x in ["europe", "france", "italy", "spain", "germany", "uk"]):
        return "landmark"
    elif any(x in title_lower for x in ["africa", "safari", "kenya", "tanzania"]):
        return "globe-africa"
    elif any(x in title_lower for x in ["beach", "island", "hawaii", "caribbean"]):
        return "umbrella-beach"
    return "plane"


def get_region_name(title: str) -> str:
    """Extract region name from trip title."""
    title_lower = title.lower()
    if any(x in title_lower for x in ["rajasthan", "jaipur", "jaisalmer"]):
        return "Rajasthan"
    elif any(x in title_lower for x in ["india", "delhi", "agra"]):
        return "India"
    elif "alaska" in title_lower:
        return "Alaska"
    elif "vietnam" in title_lower or "cambodia" in title_lower:
        return "Southeast Asia"
    elif "europe" in title_lower:
        return "Europe"
    # Default: use first part of title
    return title.split()[0] if title else "Trip"


def generate_trip_card(
    title: str,
    link: str,
    dates: str,
    days: int,
    locations: int,
    activities: int,
    index: int = 0
) -> str:
    """Generate HTML for a single trip card."""
    # Use gradient colors (light colors with icon look good)
    gradient = TRIP_GRADIENTS[index % len(TRIP_GRADIENTS)]
    icon = get_region_icon(title)
    region = get_region_name(title)

    return TRIP_CARD_TEMPLATE.format(
        link=link,
        gradient=gradient,
        icon=icon,
        region=region,
        title=title,
        dates=dates,
        days=days,
        locations=locations,
        activities=activities,
    )


def generate_trips_page(trips: list[dict]) -> str:
    """Generate the My Trips page HTML.

    Args:
        trips: List of trip dicts with keys: title, link, dates, days, locations, activities
    """
    trip_cards_list = []
    for i, trip in enumerate(trips):
        try:
            # Ensure all required fields have defaults
            card = generate_trip_card(
                title=trip.get("title", "Untitled Trip"),
                link=trip.get("link", "#"),
                dates=trip.get("dates", "Date unknown"),
                days=trip.get("days", 0) or 0,
                locations=trip.get("locations", 0) or 0,
                activities=trip.get("activities", 0) or 0,
                index=i,
            )
            trip_cards_list.append(card)
        except Exception as e:
            print(f"Warning: Could not generate card for trip {trip}: {e}")
            continue
    trip_cards = "\n".join(trip_cards_list)

    template = get_template("trips.html")
    return template.format(
        main_css=get_static_css("main.css"),
        trips_css=get_static_css("trips.css"),
        nav_html=get_nav_html("trips"),
        main_js=get_static_js("main.js"),
        upload_js=get_static_js("upload.js"),
        trip_cards=trip_cards,
    )


HOME_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Libertas - Travel Freely</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <style>
{main_css}

{home_css}
    </style>
</head>
<body>
    {nav_html}

    <div class="home-hero">
        <div class="home-hero-content">
            <i class="fas fa-feather-alt brand-icon"></i>
            <h1>LIBERTAS</h1>
            <p class="tagline">Travel Freely</p>
            <p class="subtitle">An agentic travel companion inspired by the Roman gods</p>
        </div>
    </div>

    <div class="home-content">
        <div class="features-heading">
            <h2>Your Journey Starts Here</h2>
            <p>Powerful tools to plan, organize, and visualize your travels</p>
        </div>

        <div class="home-grid">
            <a href="trips.html" class="home-card">
                <div class="home-card-icon purple">
                    <i class="fas fa-route"></i>
                </div>
                <div class="home-card-content">
                    <h3>My Trips</h3>
                    <p>View and manage your travel itineraries. Import trips from PDFs and spreadsheets, see interactive maps, and get organized summaries.</p>
                </div>
            </a>

            <a href="about.html" class="home-card">
                <div class="home-card-icon blue">
                    <i class="fas fa-scroll"></i>
                </div>
                <div class="home-card-content">
                    <h3>About</h3>
                    <p>Learn about Libertas and the Roman deities of travel — Abeona, Adeona, and Libertas — who inspire this project.</p>
                </div>
            </a>

            <div class="home-card disabled">
                <div class="home-card-icon green">
                    <i class="fas fa-compass"></i>
                </div>
                <div class="home-card-content">
                    <h3>Explore <span class="coming-soon-badge">Coming Soon</span></h3>
                    <p>Discover destinations, find inspiration, and explore curated travel recommendations powered by AI.</p>
                </div>
            </div>

            <div class="home-card disabled">
                <div class="home-card-icon orange">
                    <i class="fas fa-magic"></i>
                </div>
                <div class="home-card-content">
                    <h3>Create Trip <span class="coming-soon-badge">Coming Soon</span></h3>
                    <p>Build a new itinerary from scratch with AI assistance. Just tell us where you want to go and we'll help plan the details.</p>
                </div>
            </div>
        </div>
    </div>

    <div class="home-quote">
        <blockquote>
            "The statues of Abeona and Adeona accompanied the statue of Libertas,
            signifying that freedom could go and return as she wished."
        </blockquote>
        <cite>— Marcus Terentius Varro</cite>
    </div>

    <script>
{main_js}
    </script>
</body>
</html>
"""


def generate_home_page() -> str:
    """Generate the Home page HTML."""
    template = get_template("home.html")
    return template.format(
        main_css=get_static_css("main.css"),
        home_css=get_static_css("home.css"),
        nav_html=get_nav_html("home"),
        main_js=get_static_js("main.js"),
    )


LOGIN_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Libertas</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <style>
{main_css}

{login_css}
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-box">
            <div class="login-header">
                <i class="fas fa-feather-alt brand-icon"></i>
                <h1>LIBERTAS</h1>
                <p class="tagline">Travel Freely</p>
            </div>

            <div class="login-error" id="login-error">
                <i class="fas fa-exclamation-circle"></i>
                <span id="error-message">Invalid username or password</span>
            </div>

            <form class="login-form" id="login-form" method="POST" action="/api/login">
                <div class="form-group">
                    <label for="username">Username</label>
                    <input type="text" id="username" name="username" required autocomplete="username" autofocus>
                </div>

                <div class="form-group">
                    <label for="password">Password</label>
                    <input type="password" id="password" name="password" required autocomplete="current-password">
                </div>

                <button type="submit" class="login-btn">
                    <i class="fas fa-sign-in-alt"></i> Sign In
                </button>
            </form>

            <div class="login-footer">
                Protected by authentication
            </div>
        </div>
    </div>

    <script>
    document.getElementById('login-form').addEventListener('submit', async function(e) {{
        e.preventDefault();

        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        const errorDiv = document.getElementById('login-error');
        const errorMsg = document.getElementById('error-message');

        try {{
            const response = await fetch('/api/login', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                }},
                body: JSON.stringify({{ username, password }}),
            }});

            const data = await response.json();

            if (data.success) {{
                // Redirect to the original page or home
                const redirect = new URLSearchParams(window.location.search).get('redirect') || '/';
                window.location.href = redirect;
            }} else {{
                errorMsg.textContent = data.error || 'Invalid username or password';
                errorDiv.classList.add('show');
            }}
        }} catch (err) {{
            errorMsg.textContent = 'Connection error. Please try again.';
            errorDiv.classList.add('show');
        }}
    }});
    </script>
</body>
</html>
"""


def generate_login_page() -> str:
    """Generate the Login page HTML."""
    return LOGIN_PAGE_TEMPLATE.format(
        main_css=get_static_css("main.css"),
        login_css=get_static_css("login.css"),
    )
