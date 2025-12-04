"""Common HTML templates and components shared across all Libertas agents."""

from pathlib import Path

# Path to static files and templates
STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"


def get_static_css(filename: str) -> str:
    """Read a CSS file from the common static directory."""
    css_path = STATIC_DIR / "css" / filename
    if css_path.exists():
        return css_path.read_text()
    return ""


def get_static_js(filename: str) -> str:
    """Read a JS file from the common static directory."""
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
        create_active="active" if active_page == "create" else "",
        explore_active="active" if active_page == "explore" else "",
        about_active="active" if active_page == "about" else "",
    )


NAV_HTML = """
<nav class="libertas-nav">
    <a href="/" class="brand">
        <i class="fas fa-feather-alt brand-icon"></i>
        <div>
            <div class="brand-name">LIBERTAS</div>
            <div class="brand-tagline">Travel freely</div>
        </div>
    </a>
    <div class="nav-links">
        <a href="/" class="nav-link {home_active}"><i class="fas fa-home"></i> Home</a>
        <a href="/trips.html" class="nav-link {trips_active}"><i class="fas fa-route"></i> My Trips</a>
        <a href="/create.html" class="nav-link {create_active}"><i class="fas fa-plus-circle"></i> Create</a>
        <a href="/explore.html" class="nav-link {explore_active}"><i class="fas fa-compass"></i> Explore</a>
        <a href="/about.html" class="nav-link {about_active}"><i class="fas fa-scroll"></i> About</a>
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


def generate_about_page() -> str:
    """Generate the About page HTML."""
    template = get_template("about.html")
    return template.format(nav_html=get_nav_html("about"))


def generate_home_page() -> str:
    """Generate the Home page HTML."""
    template = get_template("home.html")
    return template.format(nav_html=get_nav_html("home"))


def generate_login_page() -> str:
    """Generate the Login page HTML."""
    return get_template("login.html")


def generate_register_page() -> str:
    """Generate the Register page HTML."""
    return get_template("register.html")
