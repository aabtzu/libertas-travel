"""Parse itineraries from PDF and Excel files."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from datetime import date, time, datetime
from typing import Optional, Union

import anthropic
import pdfplumber
import openpyxl

from .models import Itinerary, ItineraryItem, Location


def fix_json_string(json_str: str) -> str:
    """Fix common JSON issues that Claude sometimes produces."""
    # Remove trailing commas before ] or }
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)

    # Fix unescaped newlines inside strings (common issue)
    # This is tricky - we need to find strings and escape newlines within them
    # Simple approach: replace literal newlines that appear to be inside strings
    lines = json_str.split('\n')
    fixed_lines = []
    in_string = False
    for line in lines:
        # Count unescaped quotes to track if we're in a string
        quote_count = len(re.findall(r'(?<!\\)"', line))
        if in_string:
            # We're continuing a string from previous line - this is the problem
            # Escape it and continue
            line = '\\n' + line.replace('\n', '\\n').replace('\r', '\\r')
        fixed_lines.append(line)
        # Update string state (odd number of quotes toggles state)
        if quote_count % 2 == 1:
            in_string = not in_string

    json_str = '\n'.join(fixed_lines)

    # Remove control characters except newlines and tabs
    json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', json_str)

    return json_str


EXTRACTION_PROMPT = """You are an expert at extracting structured travel itinerary data from text.

Analyze the following text from a travel itinerary document and extract all relevant information.

Return a JSON object with this exact structure:
{
    "title": "Trip title or destination",
    "destination_region": "The main destination region/state/country for context (e.g. 'Alaska, USA')",
    "start_date": "YYYY-MM-DD or null",
    "end_date": "YYYY-MM-DD or null",
    "travelers": ["list of traveler names"],
    "items": [
        {
            "title": "Activity/event title",
            "location_name": "Place name with region for geocoding (e.g. 'Seward, Alaska' not just 'Seward')",
            "location_address": "Full address if available",
            "location_type": "hotel|restaurant|attraction|airport|train_station|home|other",
            "date": "YYYY-MM-DD or null",
            "start_time": "HH:MM (24hr) or null",
            "end_time": "HH:MM (24hr) or null",
            "description": "Brief description",
            "category": "flight|hotel|activity|meal|transport|home|other",
            "confirmation_number": "if available or null",
            "notes": "any additional notes",
            "day_number": day number as integer or null,
            "is_home_location": true if this is the traveler's home/departure city, false otherwise
        }
    ]
}

Important:
- Extract ALL items/events from the itinerary
- Be precise with dates and times
- ALWAYS include the state/region/country with location names for accurate geocoding (e.g. "Homer, Alaska" not just "Homer")
- Mark home/departure locations with is_home_location: true (these are typically the origin city at start/end of trip)
- If information is not available, use null
- Ensure the JSON is valid

Text to analyze:
"""


class ItineraryParser:
    """Parse itineraries from various file formats using Claude."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY env var or pass api_key."
            )
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def parse_file(self, file_path: str | Path) -> Itinerary:
        """Parse an itinerary from a PDF or Excel file."""
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            text = self._extract_text_from_pdf(file_path)
        elif suffix in (".xlsx", ".xls"):
            text = self._extract_text_from_excel(file_path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

        return self._parse_with_claude(text, str(file_path))

    def parse_text(self, text: str, source_url: str = "unknown") -> Itinerary:
        """Parse an itinerary from raw text (e.g., from HTML page)."""
        return self._parse_with_claude(text, source_url)

    def _extract_text_from_pdf(self, file_path: Path) -> str:
        """Extract text content from a PDF file."""
        text_parts = []

        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)

                        # Also extract tables
                        tables = page.extract_tables()
                        for table in tables:
                            for row in table:
                                if row:
                                    row_text = " | ".join(str(cell) for cell in row if cell)
                                    text_parts.append(row_text)
                    except Exception as e:
                        # Some pages may have malformed color values or other issues
                        print(f"Warning: Could not fully extract page: {e}")
                        continue
        except Exception as e:
            raise ValueError(f"Could not parse PDF file: {e}")

        if not text_parts:
            raise ValueError("Could not extract any text from PDF. The file may be image-based or corrupted.")

        return "\n\n".join(text_parts)

    def _extract_text_from_excel(self, file_path: Path) -> str:
        """Extract text content from an Excel file."""
        text_parts = []
        workbook = openpyxl.load_workbook(file_path, data_only=True)

        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            text_parts.append(f"=== Sheet: {sheet_name} ===")

            for row in sheet.iter_rows():
                row_values = []
                for cell in row:
                    if cell.value is not None:
                        row_values.append(str(cell.value))
                if row_values:
                    text_parts.append(" | ".join(row_values))

        return "\n".join(text_parts)

    def _parse_with_claude(self, text: str, source_file: str) -> Itinerary:
        """Use Claude to extract structured data from itinerary text."""
        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            messages=[
                {
                    "role": "user",
                    "content": EXTRACTION_PROMPT + text,
                }
            ],
        )

        response_text = message.content[0].text

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = response_text.strip()

        # Fix common JSON issues like trailing commas
        json_str = fix_json_string(json_str)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            # Try to show context around the error
            lines = json_str.split('\n')
            error_line = e.lineno - 1 if e.lineno else 0
            start = max(0, error_line - 2)
            end = min(len(lines), error_line + 3)
            context = '\n'.join(f"{i+1}: {lines[i]}" for i in range(start, end))
            raise ValueError(f"Failed to parse Claude's response as JSON: {e}\nContext:\n{context}")

        return self._build_itinerary(data, source_file)

    def _build_itinerary(self, data: dict, source_file: str) -> Itinerary:
        """Build an Itinerary object from parsed data."""
        items = []

        for item_data in data.get("items", []):
            location = Location(
                name=item_data.get("location_name", "Unknown"),
                address=item_data.get("location_address"),
                location_type=item_data.get("location_type"),
            )

            item = ItineraryItem(
                title=item_data.get("title", "Untitled"),
                location=location,
                date=self._parse_date(item_data.get("date")),
                start_time=self._parse_time(item_data.get("start_time")),
                end_time=self._parse_time(item_data.get("end_time")),
                description=item_data.get("description"),
                category=item_data.get("category"),
                confirmation_number=item_data.get("confirmation_number"),
                notes=item_data.get("notes"),
                day_number=item_data.get("day_number"),
                is_home_location=item_data.get("is_home_location", False),
            )
            items.append(item)

        return Itinerary(
            title=data.get("title", "Untitled Itinerary"),
            items=items,
            start_date=self._parse_date(data.get("start_date")),
            end_date=self._parse_date(data.get("end_date")),
            travelers=data.get("travelers", []),
            source_file=source_file,
        )

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse a date string to a date object."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None

    def _parse_time(self, time_str: Optional[str]) -> Optional[time]:
        """Parse a time string to a time object."""
        if not time_str:
            return None
        try:
            return datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            return None
