"""HTML templates for Libertas Explore agent."""

from pathlib import Path

# Import shared components from common
from agents.common.templates import (
    get_static_css as common_get_static_css,
    get_nav_html,
)

# Path to explore static files and templates
STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"


def get_static_css(filename: str) -> str:
    """Read a CSS file from the explore static directory."""
    css_path = STATIC_DIR / "css" / filename
    if css_path.exists():
        return css_path.read_text()
    return ""


def get_static_js(filename: str) -> str:
    """Read a JS file from the explore static directory."""
    js_path = STATIC_DIR / "js" / filename
    if js_path.exists():
        return js_path.read_text()
    return ""


def get_template(filename: str) -> str:
    """Read an HTML template file from explore templates directory."""
    template_path = TEMPLATES_DIR / filename
    if template_path.exists():
        return template_path.read_text()
    return ""


def generate_explore_page(google_maps_api_key: str = "") -> str:
    """Generate the Explore page HTML."""
    template = get_template("explore.html")
    return template.format(
        main_css=common_get_static_css("main.css"),
        explore_css=get_static_css("explore.css"),
        nav_html=get_nav_html("explore"),
        explore_js=get_static_js("explore.js"),
        google_maps_api_key=google_maps_api_key,
    )
