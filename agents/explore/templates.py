"""HTML templates for Libertas Explore agent."""

from pathlib import Path

# Import shared components from common
from agents.common.templates import read_asset_file

_STATIC_DIR = Path(__file__).parent / "static"
_TEMPLATES_DIR = Path(__file__).parent / "templates"


def get_static_css(filename: str) -> str:
    return read_asset_file(_STATIC_DIR / "css" / filename)


def get_static_js(filename: str) -> str:
    return read_asset_file(_STATIC_DIR / "js" / filename)


def get_template(filename: str) -> str:
    return read_asset_file(_TEMPLATES_DIR / filename)
