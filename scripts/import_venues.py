#!/usr/bin/env python3
"""Import venues from CSV seed data into the database."""

import os
import sys

# Add the project root (parent of scripts/) to sys.path so `from database`
# resolves when this file is run directly.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

from database import get_venue_count, import_venues_from_csv  # noqa: E402


def main():
    csv_path = os.path.join(_REPO_ROOT, "data", "venues_seed.csv")

    if not os.path.exists(csv_path):
        print(f"Error: Seed data not found at {csv_path}")
        sys.exit(1)

    # Check current count
    current_count = get_venue_count()
    print(f"Current venue count: {current_count}")

    if current_count > 0:
        response = input("Venues already exist. Import anyway? (y/N): ")
        if response.lower() != "y":
            print("Import cancelled.")
            sys.exit(0)

    # Import venues
    print(f"Importing venues from {csv_path}...")
    import_venues_from_csv(csv_path, source="curated")

    # Show final count
    final_count = get_venue_count()
    print(f"Import complete. Total venues: {final_count}")


if __name__ == "__main__":
    main()
