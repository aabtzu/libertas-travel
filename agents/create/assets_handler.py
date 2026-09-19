"""Handler for trip source-file assets: save, list, delete, and chat context."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

import database as db
from database.assets import (
    delete_asset,
    get_assets_for_trip,
    get_extracted_texts_for_trip,
    save_asset,
)

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", Path(__file__).parent.parent.parent / "output"))


def _sanitize_name(name: str) -> str:
    """Strip unsafe characters from a filename, keeping alphanum, dot, dash, underscore."""
    return re.sub(r"[^\w.\-]", "_", name)[:200]


def _assets_dir(trip_link: str) -> Path:
    """Return the directory where assets for a trip are stored."""
    stem = trip_link.removesuffix(".html") if trip_link.endswith(".html") else trip_link
    return OUTPUT_DIR / "assets" / stem


def save_trip_asset(
    trip_link: str,
    original_name: str,
    file_data: bytes,
    mime_type: str,
    extracted_text: str | None = None,
) -> int | None:
    """Write file to disk and record asset in DB. Returns asset id or None."""
    assets_dir = _assets_dir(trip_link)
    assets_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _sanitize_name(original_name)
    stored_filename = f"{int(time.time())}_{safe_name}"
    dest = assets_dir / stored_filename
    dest.write_bytes(file_data)

    return save_asset(
        trip_link=trip_link,
        original_name=original_name,
        stored_filename=stored_filename,
        mime_type=mime_type,
        file_size=len(file_data),
        extracted_text=extracted_text,
    )


def list_assets_handler(user_id: int, link: str) -> tuple[dict, int]:
    """Return the list of assets for a trip the user can edit."""
    if not db.can_user_edit_trip(link, user_id):
        return {"error": "Not authorized"}, 403

    raw = get_assets_for_trip(link)
    assets = []
    for a in raw:
        assets.append(
            {
                "id": a["id"],
                "original_name": a["original_name"],
                "mime_type": a["mime_type"] or "",
                "file_size": a["file_size"] or 0,
                "created_at": str(a["created_at"]),
                "is_image": (a["mime_type"] or "").startswith("image/"),
            }
        )
    return {"assets": assets}, 200


def delete_asset_handler(user_id: int, link: str, asset_id: int) -> tuple[dict, int]:
    """Delete an asset from disk and DB after verifying ownership."""
    if not db.can_user_edit_trip(link, user_id):
        return {"error": "Not authorized"}, 403

    from database.assets import get_asset_by_id

    asset = get_asset_by_id(asset_id)
    if not asset or asset.get("link") != link:
        return {"error": "Asset not found"}, 404

    # Remove from disk; ignore errors (file may already be gone)
    try:
        path = _assets_dir(link) / asset["stored_filename"]
        if path.exists():
            path.unlink()
    except Exception as e:
        print(f"[assets] Warning: could not remove file: {e}")

    deleted = delete_asset(asset_id, link)
    if not deleted:
        return {"error": "Could not delete asset"}, 500
    return {"ok": True}, 200


def get_asset_file_path(link: str, asset_id: int) -> tuple[Path | None, dict | None]:
    """Return (file_path, asset_row) for serving a file. None if not found."""
    from database.assets import get_asset_by_id

    asset = get_asset_by_id(asset_id)
    if not asset or asset.get("link") != link:
        return None, None
    path = _assets_dir(link) / asset["stored_filename"]
    if not path.exists():
        return None, asset
    return path, asset


def get_assets_context_for_chat(link: str) -> str:
    """Return extracted text from all assets, formatted for LLM context injection."""
    texts = get_extracted_texts_for_trip(link)
    if not texts:
        return ""
    parts = []
    for i, text in enumerate(texts, 1):
        parts.append(f"### Source document {i}\n{text.strip()}")
    return "\n\n".join(parts)
