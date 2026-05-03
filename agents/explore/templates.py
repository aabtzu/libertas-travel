"""HTML templates for Libertas Explore agent."""

from pathlib import Path

# Import shared components from common
from agents.common.templates import get_nav_html

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
    # Concatenate the split CSS files into the inline <style> block
    css_files = ("explore.css", "explore-cards-panel.css", "explore-responsive.css")
    explore_css = "\n".join(get_static_css(name) for name in css_files)
    js_files = ("explore.js", "explore-map.js", "explore-trip.js")
    explore_js = "\n".join(get_static_js(name) for name in js_files)
    return template.format(
        explore_css=explore_css,
        nav_html=get_nav_html("explore"),
        explore_js=explore_js,
        explore_trip_panel_js=get_static_js("explore-trip-panel.js"),
        google_maps_api_key=google_maps_api_key,
    )
