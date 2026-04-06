"""Database connection management and schema initialization."""

from __future__ import annotations

import json  # noqa: F401 — used by sub-modules via wildcard-style re-import
import os
import sqlite3
from contextlib import contextmanager
from typing import Any  # noqa: F401 — re-exported for sub-modules

import bcrypt  # noqa: F401 — re-exported for users.py

try:
    import psycopg2
    import psycopg2.extras

    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = HAS_POSTGRES and DATABASE_URL is not None

# --- DDL constants ---

_DDL_PG_CREATE_USERS = """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

_DDL_PG_CREATE_TRIPS = """
    CREATE TABLE IF NOT EXISTS trips (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        title VARCHAR(255) NOT NULL,
        link VARCHAR(255) NOT NULL,
        dates VARCHAR(100),
        days INTEGER,
        locations INTEGER,
        activities INTEGER,
        map_status VARCHAR(50) DEFAULT 'pending',
        map_error TEXT,
        itinerary_data JSONB,
        is_public BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, link)
    )
"""

_DDL_PG_ALTER_TRIPS_ADD_IS_PUBLIC = (
    "ALTER TABLE trips ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT FALSE"
)

_DDL_PG_ALTER_TRIPS_ADD_IS_DRAFT = (
    "ALTER TABLE trips ADD COLUMN IF NOT EXISTS is_draft BOOLEAN DEFAULT FALSE"
)

_DDL_PG_CREATE_INDEX_TRIPS_USER_ID = (
    "CREATE INDEX IF NOT EXISTS idx_trips_user_id ON trips(user_id)"
)

_DDL_SQLITE_CREATE_USERS = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

_DDL_SQLITE_CREATE_TRIPS = """
    CREATE TABLE IF NOT EXISTS trips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        link TEXT NOT NULL,
        dates TEXT,
        days INTEGER,
        locations INTEGER,
        activities INTEGER,
        map_status TEXT DEFAULT 'pending',
        map_error TEXT,
        itinerary_data TEXT,
        is_public INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, link)
    )
"""

_DDL_SQLITE_ALTER_TRIPS_ADD_IS_PUBLIC = "ALTER TABLE trips ADD COLUMN is_public INTEGER DEFAULT 0"
_DDL_SQLITE_ALTER_TRIPS_ADD_IS_DRAFT = "ALTER TABLE trips ADD COLUMN is_draft INTEGER DEFAULT 0"

_DDL_SQLITE_CREATE_INDEX_TRIPS_USER_ID = (
    "CREATE INDEX IF NOT EXISTS idx_trips_user_id ON trips(user_id)"
)

_DDL_PG_CREATE_VENUES = """
    CREATE TABLE IF NOT EXISTS venues (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        venue_type VARCHAR(100),
        city VARCHAR(255),
        state VARCHAR(255),
        country VARCHAR(255),
        address TEXT,
        latitude DOUBLE PRECISION,
        longitude DOUBLE PRECISION,
        website TEXT,
        google_maps_link TEXT,
        notes TEXT,
        description TEXT,
        cuisine_type VARCHAR(255),
        michelin_stars INTEGER DEFAULT 0,
        chef VARCHAR(255),
        collection VARCHAR(255),
        source VARCHAR(50) DEFAULT 'curated',
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

_DDL_PG_CREATE_INDEX_VENUES_CITY = "CREATE INDEX IF NOT EXISTS idx_venues_city ON venues(city)"
_DDL_PG_CREATE_INDEX_VENUES_COUNTRY = (
    "CREATE INDEX IF NOT EXISTS idx_venues_country ON venues(country)"
)
_DDL_PG_CREATE_INDEX_VENUES_TYPE = (
    "CREATE INDEX IF NOT EXISTS idx_venues_type ON venues(venue_type)"
)

_DDL_SQLITE_CREATE_VENUES = """
    CREATE TABLE IF NOT EXISTS venues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        venue_type TEXT,
        city TEXT,
        state TEXT,
        country TEXT,
        address TEXT,
        latitude REAL,
        longitude REAL,
        website TEXT,
        google_maps_link TEXT,
        notes TEXT,
        description TEXT,
        cuisine_type TEXT,
        michelin_stars INTEGER DEFAULT 0,
        chef TEXT,
        collection TEXT,
        source TEXT DEFAULT 'curated',
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

_DDL_SQLITE_CREATE_INDEX_VENUES_CITY = "CREATE INDEX IF NOT EXISTS idx_venues_city ON venues(city)"
_DDL_SQLITE_CREATE_INDEX_VENUES_COUNTRY = (
    "CREATE INDEX IF NOT EXISTS idx_venues_country ON venues(country)"
)
_DDL_SQLITE_CREATE_INDEX_VENUES_TYPE = (
    "CREATE INDEX IF NOT EXISTS idx_venues_type ON venues(venue_type)"
)


def get_connection():
    """Get a database connection."""
    if USE_POSTGRES:
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url)
    else:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "libertas.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize database tables."""
    with get_db() as conn:
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute(_DDL_PG_CREATE_USERS)
            cursor.execute(_DDL_PG_CREATE_TRIPS)
            cursor.execute(_DDL_PG_ALTER_TRIPS_ADD_IS_PUBLIC)
            cursor.execute(_DDL_PG_ALTER_TRIPS_ADD_IS_DRAFT)
            cursor.execute(_DDL_PG_CREATE_INDEX_TRIPS_USER_ID)
        else:
            cursor.execute(_DDL_SQLITE_CREATE_USERS)
            cursor.execute(_DDL_SQLITE_CREATE_TRIPS)

            try:
                cursor.execute(_DDL_SQLITE_ALTER_TRIPS_ADD_IS_PUBLIC)
            except Exception:
                pass  # Column already exists

            try:
                cursor.execute(_DDL_SQLITE_ALTER_TRIPS_ADD_IS_DRAFT)
            except Exception:
                pass  # Column already exists

            cursor.execute(_DDL_SQLITE_CREATE_INDEX_TRIPS_USER_ID)

        # Venues table
        if USE_POSTGRES:
            cursor.execute(_DDL_PG_CREATE_VENUES)
            cursor.execute(_DDL_PG_CREATE_INDEX_VENUES_CITY)
            cursor.execute(_DDL_PG_CREATE_INDEX_VENUES_COUNTRY)
            cursor.execute(_DDL_PG_CREATE_INDEX_VENUES_TYPE)
        else:
            cursor.execute(_DDL_SQLITE_CREATE_VENUES)
            cursor.execute(_DDL_SQLITE_CREATE_INDEX_VENUES_CITY)
            cursor.execute(_DDL_SQLITE_CREATE_INDEX_VENUES_COUNTRY)
            cursor.execute(_DDL_SQLITE_CREATE_INDEX_VENUES_TYPE)

        print(f"[DB] Initialized {'PostgreSQL' if USE_POSTGRES else 'SQLite'} database")
