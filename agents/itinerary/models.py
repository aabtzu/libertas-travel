"""Data models for itinerary parsing."""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, field
from datetime import date, time


@dataclass
class Location:
    """A geographic location."""

    name: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_type: str | None = None  # hotel, restaurant, attraction, airport, etc.

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "address": self.address,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "location_type": self.location_type,
        }


@dataclass
class ItineraryItem:
    """A single item/event in an itinerary."""

    title: str
    location: Location
    date: date | None = None
    end_date: date | None = None  # checkout date for hotels, return date for rentals
    start_time: time | None = None
    end_time: time | None = None
    description: str | None = None
    category: str | None = None  # flight, hotel, activity, meal, transport, etc.
    confirmation_number: str | None = None
    notes: str | None = None
    day_number: int | None = None
    is_home_location: bool = False  # True if this is the traveler's home/origin
    website_url: str | None = None  # Direct link to hotel/activity website if available
    google_maps_link: str | None = None  # Stored Maps URL set by fill_missing_links

    @property
    def maps_url(self) -> str:
        """Return a Google Maps URL for this item.

        Prefers the stored google_maps_link (set by Fill Links, which is precise).
        Falls back to a constructed search query when none is stored.
        """
        if self.google_maps_link:
            return self.google_maps_link
        loc = self.location.name if self.location else None
        query = urllib.parse.quote(f"{self.title} {loc}" if loc else self.title)
        return f"https://www.google.com/maps/search/?api=1&query={query}"

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "location": self.location.to_dict(),
            "date": self.date.isoformat() if self.date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "description": self.description,
            "category": self.category,
            "confirmation_number": self.confirmation_number,
            "notes": self.notes,
            "day_number": self.day_number,
            "is_home_location": self.is_home_location,
            "website_url": self.website_url,
            "google_maps_link": self.google_maps_link,
        }


@dataclass
class Itinerary:
    """A complete travel itinerary."""

    title: str
    items: list[ItineraryItem] = field(default_factory=list)
    start_date: date | None = None
    end_date: date | None = None
    travelers: list[str] = field(default_factory=list)
    source_file: str | None = None

    @property
    def duration_days(self) -> int | None:
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return None

    @property
    def locations(self) -> list[Location]:
        """Get all unique locations with coordinates."""
        seen = set()
        locations = []
        for item in self.items:
            if item.location.has_coordinates:
                key = (item.location.latitude, item.location.longitude)
                if key not in seen:
                    seen.add(key)
                    locations.append(item.location)
        return locations

    def items_by_date(self) -> dict[date, list[ItineraryItem]]:
        """Group items by date."""
        by_date: dict[date, list[ItineraryItem]] = {}
        for item in self.items:
            if item.date:
                if item.date not in by_date:
                    by_date[item.date] = []
                by_date[item.date].append(item)
        return dict(sorted(by_date.items()))

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "items": [item.to_dict() for item in self.items],
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "travelers": self.travelers,
            "source_file": self.source_file,
            "duration_days": self.duration_days,
        }
