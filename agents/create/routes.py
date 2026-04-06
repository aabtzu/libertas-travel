"""Create blueprint: trip creation chat, file upload, URL import, plan upload."""

from __future__ import annotations

from flask import Blueprint, g, request

from agents.common.flask_utils import json_err, json_ok, require_auth
from agents.create import handler as create_handler

create_bp = Blueprint("create", __name__)


@create_bp.post("/api/create/chat")
@require_auth
def create_chat():
    data = request.get_json(silent=True) or {}
    result, status = create_handler.create_chat_handler(g.user_id, data)
    if status == 200:
        return json_ok(result)
    return json_err(result.get("error", "Unknown error"), status=status)


@create_bp.post("/api/create/upload-plan")
@require_auth
def upload_plan():
    if "file" not in request.files:
        return json_err("No file provided")

    file = request.files["file"]
    filename = file.filename or "upload"
    file_data = file.read()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    result, status = create_handler.upload_plan_handler(g.user_id, filename, file_data, ext)
    if status == 200:
        return json_ok(result)
    return json_err(result.get("error", "Unknown error"), status=status)


@create_bp.post("/api/upload")
@require_auth
def upload_file():
    if "file" not in request.files:
        return json_err("No file uploaded")

    file = request.files["file"]
    filename = file.filename or "upload"
    file_data = file.read()

    result, status = create_handler.upload_file_handler(
        user_id=g.user_id,
        file_data=file_data,
        filename=filename,
    )
    if status == 200:
        return json_ok(result)
    return json_err(result.get("error", "Unknown error"), status=status)


@create_bp.post("/api/import-url")
@require_auth
def import_url():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return json_err("No URL provided")

    result, status = create_handler.url_import_handler(
        user_id=g.user_id,
        url=url,
    )
    if status == 200:
        return json_ok(result)
    return json_err(result.get("error", "Unknown error"), status=status)
