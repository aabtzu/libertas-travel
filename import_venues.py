#!/usr/bin/env python3
"""Import venues from CSV seed data into the database."""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import import_venues_from_csv, get_venue_count

def main():
    # Get path to seed data
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, "data", "venues_seed.csv")

    if not os.path.exists(csv_path):
        print(f"Error: Seed data not found at {csv_path}")
        sys.exit(1)

    # Check current count
    current_count = get_venue_count()
    print(f"Current venue count: {current_count}")

    if current_count > 0:
        response = input("Venues already exist. Import anyway? (y/N): ")
        if response.lower() != 'y':
            print("Import cancelled.")
            sys.exit(0)

    # Import venues
    print(f"Importing venues from {csv_path}...")
    imported = import_venues_from_csv(csv_path, source="curated")

    # Show final count
    final_count = get_venue_count()
    print(f"Import complete. Total venues: {final_count}")

if __name__ == "__main__":
    main()
