"""Command-line interface for the itinerary agent."""

import argparse
import json
import sys
from pathlib import Path

from .parser import ItineraryParser
from .summarizer import ItinerarySummarizer
from .mapper import ItineraryMapper
from .web_view import ItineraryWebView


def main():
    parser = argparse.ArgumentParser(
        description="Parse, summarize, and map travel itineraries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Parse and summarize a PDF itinerary
  python -m agents.itinerary.cli trip.pdf

  # Parse Excel and generate map
  python -m agents.itinerary.cli itinerary.xlsx --map output_map.html

  # Generate unified web page with summary and map tabs
  python -m agents.itinerary.cli trip.pdf --web trip_view.html

  # Full processing with all outputs
  python -m agents.itinerary.cli trip.pdf --summary --map trip_map.html --json trip_data.json

  # Quick local summary (no API call)
  python -m agents.itinerary.cli trip.pdf --quick-summary
        """,
    )

    parser.add_argument(
        "input_file",
        type=str,
        help="Path to the itinerary file (PDF or Excel)",
    )

    parser.add_argument(
        "--summary",
        action="store_true",
        help="Generate an AI-powered detailed summary",
    )

    parser.add_argument(
        "--quick-summary",
        action="store_true",
        help="Generate a quick local summary (no API call)",
    )

    parser.add_argument(
        "--map",
        type=str,
        metavar="OUTPUT_PATH",
        help="Generate an interactive map and save to this path",
    )

    parser.add_argument(
        "--json",
        type=str,
        metavar="OUTPUT_PATH",
        help="Export parsed itinerary data as JSON",
    )

    parser.add_argument(
        "--no-route",
        action="store_true",
        help="Don't draw route lines on the map",
    )

    parser.add_argument(
        "--cluster",
        action="store_true",
        help="Cluster nearby markers on the map",
    )

    parser.add_argument(
        "--web",
        type=str,
        metavar="OUTPUT_PATH",
        help="Generate a unified web page with summary and map tabs",
    )

    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Use quick local summary instead of AI (for --web)",
    )

    parser.add_argument(
        "--api-key",
        type=str,
        help="Anthropic API key (or set ANTHROPIC_API_KEY env var)",
    )

    args = parser.parse_args()

    # Validate input file
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if input_path.suffix.lower() not in (".pdf", ".xlsx", ".xls"):
        print(f"Error: Unsupported file format: {input_path.suffix}", file=sys.stderr)
        print("Supported formats: .pdf, .xlsx, .xls", file=sys.stderr)
        sys.exit(1)

    try:
        # Parse the itinerary
        print(f"Parsing {input_path.name}...")
        itinerary_parser = ItineraryParser(api_key=args.api_key)
        itinerary = itinerary_parser.parse_file(input_path)
        print(f"Found {len(itinerary.items)} items in itinerary: {itinerary.title}")

        # Generate quick summary (local)
        if args.quick_summary:
            print("\n" + "=" * 50)
            print("QUICK SUMMARY")
            print("=" * 50 + "\n")
            summarizer = ItinerarySummarizer(api_key=args.api_key)
            print(summarizer.quick_summary(itinerary))

        # Generate AI summary
        if args.summary:
            print("\n" + "=" * 50)
            print("AI-GENERATED SUMMARY")
            print("=" * 50 + "\n")
            summarizer = ItinerarySummarizer(api_key=args.api_key)
            print(summarizer.summarize(itinerary))

        # Generate map
        if args.map:
            print(f"\nGenerating map...")
            mapper = ItineraryMapper()
            mapper.create_map(
                itinerary,
                output_path=args.map,
                show_route=not args.no_route,
                cluster_markers=args.cluster,
            )
            print(f"Map saved to: {args.map}")

        # Export JSON
        if args.json:
            output_path = Path(args.json)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(itinerary.to_dict(), f, indent=2, default=str)
            print(f"JSON data saved to: {args.json}")

        # Generate unified web page
        if args.web:
            print(f"\nGenerating web view...")
            web_view = ItineraryWebView(api_key=args.api_key)
            web_view.generate(
                itinerary,
                output_path=args.web,
                use_ai_summary=not args.no_ai,
            )
            print(f"Web view saved to: {args.web}")

        # Default output if no specific output requested
        if not any([args.summary, args.quick_summary, args.map, args.json, args.web]):
            summarizer = ItinerarySummarizer(api_key=args.api_key)
            print("\n" + summarizer.quick_summary(itinerary))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
