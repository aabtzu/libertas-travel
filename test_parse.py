#!/usr/bin/env python3
"""Test script to debug parsing on Render.

Usage on Render shell:
  # Test with a URL
  python test_parse.py --url "https://drive.google.com/file/d/1mUMZId72G-KJmsZXIoC3BQdFUaKadYsG/view"

  # Test with a local file
  python test_parse.py --file /path/to/file.pdf

  # Just test PDF extraction (no Claude API call)
  python test_parse.py --file /path/to/file.pdf --extract-only
"""

import argparse
import os
import sys
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

def test_download(url: str) -> tuple[bytes, str]:
    """Test downloading from URL."""
    print(f"\n=== STEP 1: Download from URL ===")
    print(f"URL: {url}")

    from server import download_from_url

    try:
        file_data, filename, content_type = download_from_url(url)
        print(f"✓ Downloaded {len(file_data)} bytes")
        print(f"  Filename: {filename}")
        print(f"  Content-Type: {content_type}")
        print(f"  First 100 bytes: {file_data[:100]}")
        return file_data, filename
    except Exception as e:
        print(f"✗ Download failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def test_extract_pdf(file_path: str) -> str:
    """Test PDF text extraction."""
    print(f"\n=== STEP 2: Extract text from PDF ===")
    print(f"File: {file_path}")

    from agents.itinerary.parser import ItineraryParser

    parser = ItineraryParser.__new__(ItineraryParser)
    parser.api_key = "dummy"  # Not needed for extraction

    try:
        text = parser._extract_text_from_pdf(file_path)
        print(f"✓ Extracted {len(text)} characters")
        print(f"  First 500 chars:\n{text[:500]}")
        return text
    except Exception as e:
        print(f"✗ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_parse(file_path: str) -> None:
    """Test full parsing with Claude."""
    print(f"\n=== STEP 3: Parse with Claude API ===")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("✗ ANTHROPIC_API_KEY not set")
        return None

    print(f"API key present: {api_key[:8]}...")

    from agents.itinerary.parser import ItineraryParser

    try:
        parser = ItineraryParser()
        itinerary = parser.parse_file(file_path)
        print(f"✓ Parsed successfully!")
        print(f"  Title: {itinerary.title}")
        print(f"  Items: {len(itinerary.items)}")
        print(f"  Dates: {itinerary.start_date} - {itinerary.end_date}")
        return itinerary
    except Exception as e:
        print(f"✗ Parse failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_geocoding(itinerary) -> None:
    """Test geocoding."""
    print(f"\n=== STEP 4: Test Geocoding ===")

    from agents.itinerary.mapper import ItineraryMapper

    mapper = ItineraryMapper()

    # Test first 3 locations
    for i, item in enumerate(itinerary.items[:3]):
        loc = item.location
        print(f"\nLocation {i+1}: {loc.name}")
        try:
            mapper._geocode_location(loc)
            if loc.has_coordinates:
                print(f"  ✓ Geocoded: ({loc.latitude}, {loc.longitude})")
            else:
                print(f"  ✗ Could not geocode")
        except Exception as e:
            print(f"  ✗ Geocoding error: {e}")

def test_web_view(itinerary, output_path: str) -> None:
    """Test web view generation."""
    print(f"\n=== STEP 5: Generate Web View ===")

    from agents.itinerary.web_view import ItineraryWebView

    try:
        web_view = ItineraryWebView()
        web_view.generate(itinerary, output_path, use_ai_summary=False)
        print(f"✓ Generated: {output_path}")
    except Exception as e:
        print(f"✗ Web view failed: {e}")
        import traceback
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description="Test parsing pipeline")
    parser.add_argument("--url", help="URL to download and parse")
    parser.add_argument("--file", help="Local file to parse")
    parser.add_argument("--extract-only", action="store_true",
                       help="Only test extraction, skip Claude API")
    parser.add_argument("--output", default="/tmp/test_output.html",
                       help="Output path for web view")

    args = parser.parse_args()

    if not args.url and not args.file:
        print("Error: Provide --url or --file")
        sys.exit(1)

    file_path = args.file

    # If URL provided, download first
    if args.url:
        file_data, filename = test_download(args.url)
        if not file_data:
            sys.exit(1)

        # Save to temp file
        suffix = ".pdf" if file_data[:4] == b'%PDF' else ".xlsx"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(file_data)
            file_path = f.name
        print(f"Saved to: {file_path}")

    # Test extraction
    text = test_extract_pdf(file_path)
    if not text:
        sys.exit(1)

    if args.extract_only:
        print("\n=== Extract-only mode, stopping here ===")
        sys.exit(0)

    # Test full parse
    itinerary = test_parse(file_path)
    if not itinerary:
        sys.exit(1)

    # Test geocoding
    test_geocoding(itinerary)

    # Test web view
    test_web_view(itinerary, args.output)

    print("\n=== ALL TESTS COMPLETE ===")

if __name__ == "__main__":
    main()
