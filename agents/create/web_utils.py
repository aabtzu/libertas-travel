"""Web fetching utilities: HTML extraction, URL download, Google Drive conversion."""

from __future__ import annotations

import re
import ssl
import urllib.request


def extract_text_from_html(html_content: bytes) -> str:
    """Extract readable text from HTML content for itinerary parsing."""
    import html.parser

    class TextExtractor(html.parser.HTMLParser):
        def __init__(self):
            super().__init__()
            self.text_parts = []
            self.skip_tags = {"script", "style", "meta", "link", "noscript"}
            self.current_skip = False

        def handle_starttag(self, tag, attrs):
            if tag in self.skip_tags:
                self.current_skip = True
            elif tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
                self.text_parts.append("\n")

        def handle_endtag(self, tag):
            if tag in self.skip_tags:
                self.current_skip = False
            elif tag in ("p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
                self.text_parts.append("\n")

        def handle_data(self, data):
            if not self.current_skip:
                text = data.strip()
                if text:
                    self.text_parts.append(text + " ")

    try:
        html_str = html_content.decode("utf-8")
    except UnicodeDecodeError:
        html_str = html_content.decode("latin-1")

    extractor = TextExtractor()
    extractor.feed(html_str)
    text = "".join(extractor.text_parts)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = re.sub(r" +", " ", text)
    return text.strip()


def convert_google_drive_url(url: str) -> tuple[str, str]:
    """Convert Google Drive sharing URL to direct download URL. Returns (url, filename)."""
    file_id = None
    filename = "downloaded_file"

    if "/file/d/" in url:
        match = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
        if match:
            file_id = match.group(1)
    elif "id=" in url:
        match = re.search(r"id=([a-zA-Z0-9_-]+)", url)
        if match:
            file_id = match.group(1)
    elif "/spreadsheets/d/" in url:
        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
        if match:
            file_id = match.group(1)
            return (
                f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx",
                "spreadsheet.xlsx",
            )

    if file_id:
        return f"https://drive.google.com/uc?export=download&id={file_id}", filename
    return url, filename


def download_from_url(url: str) -> tuple[bytes, str, str]:
    """Download content from URL. Returns (content, filename, content_type)."""
    filename = "downloaded_file"

    from urllib.parse import urlparse as _urlparse

    parsed_url = _urlparse(url)
    if "google.com" in parsed_url.netloc or "drive.google.com" in parsed_url.netloc:
        url, filename = convert_google_drive_url(url)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
    }

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, context=ctx, timeout=60) as response:
        content_type = response.headers.get("Content-Type", "").lower()
        content_disp = response.headers.get("Content-Disposition", "")
        if "filename=" in content_disp:
            match = re.search(r'filename[*]?=["\']?([^"\';]+)', content_disp)
            if match:
                filename = match.group(1).strip("\"'")

        if "." not in filename:
            if "spreadsheet" in content_type or "excel" in content_type:
                filename += ".xlsx"
            elif "pdf" in content_type:
                filename += ".pdf"
            elif "html" in content_type:
                filename += ".html"

        return response.read(), filename, content_type


def fetch_webpage_for_chat(url: str) -> dict:
    """Fetch a web page and return extracted text for chat handlers."""
    try:
        content, filename, content_type = download_from_url(url)
        if "html" in content_type or filename.endswith(".html"):
            text = extract_text_from_html(content)
        else:
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                text = content.decode("latin-1")

        title = None
        try:
            html_str = content.decode("utf-8", errors="ignore")
            title_match = re.search(r"<title[^>]*>([^<]+)</title>", html_str, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()
        except Exception:
            pass

        if len(text) > 15000:
            text = text[:15000] + "\n\n[Content truncated...]"

        return {"success": True, "text": text, "title": title or url, "url": url}
    except Exception as e:
        return {"success": False, "error": str(e), "url": url}
