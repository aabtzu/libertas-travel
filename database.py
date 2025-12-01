"""PostgreSQL database module for multi-user support."""

import os
import json
import bcrypt
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# Always import sqlite3 for local dev fallback
import sqlite3

# Try to import psycopg2 for production
try:
    import psycopg2
    import psycopg2.extras
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

# Database URL from environment (Render sets this automatically)
DATABASE_URL = os.environ.get("DATABASE_URL")

# Use PostgreSQL if available, otherwise SQLite for local development
USE_POSTGRES = HAS_POSTGRES and DATABASE_URL is not None


def get_connection():
    """Get a database connection."""
    if USE_POSTGRES:
        # Render uses postgres:// but psycopg2 needs postgresql://
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url)
    else:
        # SQLite for local development
        db_path = os.path.join(os.path.dirname(__file__), "libertas.db")
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
            # PostgreSQL schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, link)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trips_user_id ON trips(user_id)
            """)
        else:
            # SQLite schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, link)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trips_user_id ON trips(user_id)
            """)

        print(f"[DB] Initialized {'PostgreSQL' if USE_POSTGRES else 'SQLite'} database")


# ============ User Functions ============

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def create_user(username: str, email: str, password: str) -> Optional[int]:
    """Create a new user. Returns user ID or None if failed."""
    password_hash = hash_password(password)

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            if USE_POSTGRES:
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
                    (username, email, password_hash)
                )
                return cursor.fetchone()[0]
            else:
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                    (username, email, password_hash)
                )
                return cursor.lastrowid
        except Exception as e:
            print(f"[DB] Error creating user: {e}")
            return None


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get user by username."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute("SELECT id, username, email, password_hash FROM users WHERE username = %s", (username,))
        else:
            cursor.execute("SELECT id, username, email, password_hash FROM users WHERE username = ?", (username,))

        row = cursor.fetchone()
        if row:
            if USE_POSTGRES:
                return {"id": row[0], "username": row[1], "email": row[2], "password_hash": row[3]}
            else:
                return dict(row)
        return None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute("SELECT id, username, email FROM users WHERE id = %s", (user_id,))
        else:
            cursor.execute("SELECT id, username, email FROM users WHERE id = ?", (user_id,))

        row = cursor.fetchone()
        if row:
            if USE_POSTGRES:
                return {"id": row[0], "username": row[1], "email": row[2]}
            else:
                return dict(row)
        return None


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate user and return user dict if successful."""
    user = get_user_by_username(username)
    if user and verify_password(password, user["password_hash"]):
        del user["password_hash"]  # Don't return the hash
        return user
    return None


def username_exists(username: str) -> bool:
    """Check if username already exists."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute("SELECT 1 FROM users WHERE username = %s", (username,))
        else:
            cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        return cursor.fetchone() is not None


def email_exists(email: str) -> bool:
    """Check if email already exists."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute("SELECT 1 FROM users WHERE email = %s", (email,))
        else:
            cursor.execute("SELECT 1 FROM users WHERE email = ?", (email,))
        return cursor.fetchone() is not None


# ============ Trip Functions ============

def get_user_trips(user_id: int) -> List[Dict[str, Any]]:
    """Get all trips for a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute("""
                SELECT id, title, link, dates, days, locations, activities, map_status, map_error
                FROM trips WHERE user_id = %s ORDER BY created_at DESC
            """, (user_id,))
            columns = ['id', 'title', 'link', 'dates', 'days', 'locations', 'activities', 'map_status', 'map_error']
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        else:
            cursor.execute("""
                SELECT id, title, link, dates, days, locations, activities, map_status, map_error
                FROM trips WHERE user_id = ? ORDER BY created_at DESC
            """, (user_id,))
            return [dict(row) for row in cursor.fetchall()]


def add_trip(user_id: int, trip_data: Dict[str, Any], itinerary_data: Optional[Dict] = None) -> Optional[int]:
    """Add a trip for a user. Returns trip ID or None if failed."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            itinerary_json = json.dumps(itinerary_data) if itinerary_data else None

            if USE_POSTGRES:
                cursor.execute("""
                    INSERT INTO trips (user_id, title, link, dates, days, locations, activities, map_status, itinerary_data)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, link) DO UPDATE SET
                        title = EXCLUDED.title,
                        dates = EXCLUDED.dates,
                        days = EXCLUDED.days,
                        locations = EXCLUDED.locations,
                        activities = EXCLUDED.activities,
                        map_status = EXCLUDED.map_status,
                        itinerary_data = EXCLUDED.itinerary_data
                    RETURNING id
                """, (
                    user_id,
                    trip_data.get("title"),
                    trip_data.get("link"),
                    trip_data.get("dates"),
                    trip_data.get("days"),
                    trip_data.get("locations"),
                    trip_data.get("activities"),
                    trip_data.get("map_status", "pending"),
                    itinerary_json
                ))
                return cursor.fetchone()[0]
            else:
                # SQLite doesn't have ON CONFLICT ... DO UPDATE in older versions
                cursor.execute("""
                    INSERT OR REPLACE INTO trips (user_id, title, link, dates, days, locations, activities, map_status, itinerary_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    trip_data.get("title"),
                    trip_data.get("link"),
                    trip_data.get("dates"),
                    trip_data.get("days"),
                    trip_data.get("locations"),
                    trip_data.get("activities"),
                    trip_data.get("map_status", "pending"),
                    itinerary_json
                ))
                return cursor.lastrowid
        except Exception as e:
            print(f"[DB] Error adding trip: {e}")
            return None


def get_trip_by_link(user_id: int, link: str) -> Optional[Dict[str, Any]]:
    """Get a specific trip by link for a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute("""
                SELECT id, title, link, dates, days, locations, activities, map_status, map_error, itinerary_data
                FROM trips WHERE user_id = %s AND link = %s
            """, (user_id, link))
            row = cursor.fetchone()
            if row:
                columns = ['id', 'title', 'link', 'dates', 'days', 'locations', 'activities', 'map_status', 'map_error', 'itinerary_data']
                trip = dict(zip(columns, row))
                if trip['itinerary_data']:
                    trip['itinerary_data'] = trip['itinerary_data']  # Already parsed by psycopg2 for JSONB
                return trip
        else:
            cursor.execute("""
                SELECT id, title, link, dates, days, locations, activities, map_status, map_error, itinerary_data
                FROM trips WHERE user_id = ? AND link = ?
            """, (user_id, link))
            row = cursor.fetchone()
            if row:
                trip = dict(row)
                if trip['itinerary_data']:
                    trip['itinerary_data'] = json.loads(trip['itinerary_data'])
                return trip
        return None


def update_trip_map_status(user_id: int, link: str, status: str, error: Optional[str] = None):
    """Update the map status for a trip."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute("""
                UPDATE trips SET map_status = %s, map_error = %s
                WHERE user_id = %s AND link = %s
            """, (status, error, user_id, link))
        else:
            cursor.execute("""
                UPDATE trips SET map_status = ?, map_error = ?
                WHERE user_id = ? AND link = ?
            """, (status, error, user_id, link))


def update_trip(user_id: int, link: str, updates: Dict[str, Any]) -> bool:
    """Update a trip's fields (title, dates, days, locations, activities)."""
    if not updates:
        return False

    # Build the SET clause dynamically
    allowed_fields = ['title', 'dates', 'days', 'locations', 'activities']
    set_parts = []
    values = []

    for field in allowed_fields:
        if field in updates:
            if USE_POSTGRES:
                set_parts.append(f"{field} = %s")
            else:
                set_parts.append(f"{field} = ?")
            values.append(updates[field])

    if not set_parts:
        return False

    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            query = f"UPDATE trips SET {', '.join(set_parts)} WHERE user_id = %s AND link = %s"
            values.extend([user_id, link])
        else:
            query = f"UPDATE trips SET {', '.join(set_parts)} WHERE user_id = ? AND link = ?"
            values.extend([user_id, link])

        cursor.execute(query, values)
        return cursor.rowcount > 0


def delete_trip(user_id: int, link: str) -> bool:
    """Delete a trip."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute("DELETE FROM trips WHERE user_id = %s AND link = %s", (user_id, link))
        else:
            cursor.execute("DELETE FROM trips WHERE user_id = ? AND link = ?", (user_id, link))
        return cursor.rowcount > 0


def get_trip_owner(link: str) -> Optional[int]:
    """Get the user_id of a trip owner by link (for any user)."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute("SELECT user_id FROM trips WHERE link = %s", (link,))
        else:
            cursor.execute("SELECT user_id FROM trips WHERE link = ?", (link,))
        row = cursor.fetchone()
        return row[0] if row else None


# Initialize database on import
init_db()
