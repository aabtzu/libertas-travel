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
                    is_public BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, link)
                )
            """)

            # Add is_public column if it doesn't exist (for existing databases)
            cursor.execute("""
                ALTER TABLE trips ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT FALSE
            """)

            # Add is_draft column if it doesn't exist
            cursor.execute("""
                ALTER TABLE trips ADD COLUMN IF NOT EXISTS is_draft BOOLEAN DEFAULT FALSE
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
                    is_public INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, link)
                )
            """)

            # Add is_public column if it doesn't exist (for existing databases)
            try:
                cursor.execute("ALTER TABLE trips ADD COLUMN is_public INTEGER DEFAULT 0")
            except:
                pass  # Column already exists

            # Add is_draft column if it doesn't exist
            try:
                cursor.execute("ALTER TABLE trips ADD COLUMN is_draft INTEGER DEFAULT 0")
            except:
                pass  # Column already exists

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
                SELECT id, title, link, dates, days, locations, activities, map_status, map_error, is_public, is_draft, itinerary_data
                FROM trips WHERE user_id = %s ORDER BY created_at DESC
            """, (user_id,))
            columns = ['id', 'title', 'link', 'dates', 'days', 'locations', 'activities', 'map_status', 'map_error', 'is_public', 'is_draft', 'itinerary_data']
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        else:
            cursor.execute("""
                SELECT id, title, link, dates, days, locations, activities, map_status, map_error, is_public, is_draft, itinerary_data
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
                SELECT id, title, link, dates, days, locations, activities, map_status, map_error, itinerary_data, is_draft
                FROM trips WHERE user_id = %s AND link = %s
            """, (user_id, link))
            row = cursor.fetchone()
            if row:
                columns = ['id', 'title', 'link', 'dates', 'days', 'locations', 'activities', 'map_status', 'map_error', 'itinerary_data', 'is_draft']
                trip = dict(zip(columns, row))
                if trip['itinerary_data']:
                    trip['itinerary_data'] = trip['itinerary_data']  # Already parsed by psycopg2 for JSONB
                    # Extract start_date and end_date from itinerary_data for convenience
                    trip['start_date'] = trip['itinerary_data'].get('start_date')
                    trip['end_date'] = trip['itinerary_data'].get('end_date')
                else:
                    trip['start_date'] = None
                    trip['end_date'] = None
                return trip
        else:
            cursor.execute("""
                SELECT id, title, link, dates, days, locations, activities, map_status, map_error, itinerary_data, is_draft
                FROM trips WHERE user_id = ? AND link = ?
            """, (user_id, link))
            row = cursor.fetchone()
            if row:
                trip = dict(row)
                if trip['itinerary_data']:
                    trip['itinerary_data'] = json.loads(trip['itinerary_data'])
                    # Extract start_date and end_date from itinerary_data for convenience
                    trip['start_date'] = trip['itinerary_data'].get('start_date')
                    trip['end_date'] = trip['itinerary_data'].get('end_date')
                else:
                    trip['start_date'] = None
                    trip['end_date'] = None
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


def get_pending_geocoding_trips() -> List[Dict[str, Any]]:
    """Get all trips with pending or processing map status that need geocoding.

    Used on startup to recover stale geocoding tasks after server restart.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute("""
                SELECT link, itinerary_data
                FROM trips
                WHERE map_status IN ('pending', 'processing')
                AND itinerary_data IS NOT NULL
            """)
            rows = cursor.fetchall()
            return [{'link': row[0], 'itinerary_data': row[1]} for row in rows]
        else:
            cursor.execute("""
                SELECT link, itinerary_data
                FROM trips
                WHERE map_status IN ('pending', 'processing')
                AND itinerary_data IS NOT NULL
            """)
            rows = cursor.fetchall()
            result = []
            for row in rows:
                itinerary_data = json.loads(row['itinerary_data']) if row['itinerary_data'] else None
                if itinerary_data:
                    result.append({'link': row['link'], 'itinerary_data': itinerary_data})
            return result


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


# ============ User List Functions ============

def get_all_users() -> List[Dict[str, Any]]:
    """Get list of all users (id and username only, for sharing)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users ORDER BY username")
        if USE_POSTGRES:
            return [{"id": row[0], "username": row[1]} for row in cursor.fetchall()]
        else:
            return [dict(row) for row in cursor.fetchall()]


# ============ Trip Sharing Functions ============

def copy_trip_to_user(source_user_id: int, link: str, target_user_id: int) -> Optional[int]:
    """Copy a trip from one user to another. Returns new trip ID or None if failed."""
    # Get the source trip
    source_trip = get_trip_by_link(source_user_id, link)
    if not source_trip:
        return None

    # Create new trip data for target user
    trip_data = {
        "title": source_trip["title"],
        "link": source_trip["link"],
        "dates": source_trip.get("dates"),
        "days": source_trip.get("days"),
        "locations": source_trip.get("locations"),
        "activities": source_trip.get("activities"),
        "map_status": source_trip.get("map_status", "ready"),
    }

    # Add to target user (uses upsert, so will update if exists)
    return add_trip(target_user_id, trip_data, source_trip.get("itinerary_data"))


def share_trip_with_all(source_user_id: int, link: str) -> int:
    """Share a trip with all users. Returns count of users shared with."""
    users = get_all_users()
    shared_count = 0
    for user in users:
        if user["id"] != source_user_id:
            if copy_trip_to_user(source_user_id, link, user["id"]):
                shared_count += 1
    return shared_count


# ============ Public Trips Functions ============

def set_trip_public(user_id: int, link: str, is_public: bool) -> bool:
    """Set a trip's public visibility."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute("""
                UPDATE trips SET is_public = %s
                WHERE user_id = %s AND link = %s
            """, (is_public, user_id, link))
        else:
            cursor.execute("""
                UPDATE trips SET is_public = ?
                WHERE user_id = ? AND link = ?
            """, (is_public, user_id, link))
        return cursor.rowcount > 0


def get_public_trips(exclude_user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get all public trips, optionally excluding a specific user's trips."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            if exclude_user_id:
                cursor.execute("""
                    SELECT t.id, t.title, t.link, t.dates, t.days, t.locations, t.activities,
                           t.map_status, t.map_error, u.username as owner_username, t.itinerary_data
                    FROM trips t
                    JOIN users u ON t.user_id = u.id
                    WHERE t.is_public = TRUE AND t.user_id != %s
                    ORDER BY t.created_at DESC
                """, (exclude_user_id,))
            else:
                cursor.execute("""
                    SELECT t.id, t.title, t.link, t.dates, t.days, t.locations, t.activities,
                           t.map_status, t.map_error, u.username as owner_username, t.itinerary_data
                    FROM trips t
                    JOIN users u ON t.user_id = u.id
                    WHERE t.is_public = TRUE
                    ORDER BY t.created_at DESC
                """)
            columns = ['id', 'title', 'link', 'dates', 'days', 'locations', 'activities', 'map_status', 'map_error', 'owner_username', 'itinerary_data']
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        else:
            if exclude_user_id:
                cursor.execute("""
                    SELECT t.id, t.title, t.link, t.dates, t.days, t.locations, t.activities,
                           t.map_status, t.map_error, u.username as owner_username, t.itinerary_data
                    FROM trips t
                    JOIN users u ON t.user_id = u.id
                    WHERE t.is_public = 1 AND t.user_id != ?
                    ORDER BY t.created_at DESC
                """, (exclude_user_id,))
            else:
                cursor.execute("""
                    SELECT t.id, t.title, t.link, t.dates, t.days, t.locations, t.activities,
                           t.map_status, t.map_error, u.username as owner_username, t.itinerary_data
                    FROM trips t
                    JOIN users u ON t.user_id = u.id
                    WHERE t.is_public = 1
                    ORDER BY t.created_at DESC
                """)
            return [dict(row) for row in cursor.fetchall()]


# ============ Draft Trip Functions ============

def create_draft_trip(user_id: int, title: str, start_date: Optional[str] = None,
                      end_date: Optional[str] = None, num_days: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Create a new draft trip. Returns the trip data with link or None if failed."""
    import re

    # Generate link from title
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9]+', '_', slug)
    slug = re.sub(r'_+', '_', slug).strip('_')
    base_link = f"{slug}.html"

    # Check for existing trips with this link and find a unique one
    link = base_link
    with get_db() as conn:
        cursor = conn.cursor()
        counter = 1
        while True:
            if USE_POSTGRES:
                cursor.execute("SELECT COUNT(*) FROM trips WHERE user_id = %s AND link = %s", (user_id, link))
            else:
                cursor.execute("SELECT COUNT(*) FROM trips WHERE user_id = ? AND link = ?", (user_id, link))
            count = cursor.fetchone()[0]
            if count == 0:
                break
            counter += 1
            link = f"{slug}_{counter}.html"

    # Format dates string
    dates = None
    if start_date and end_date:
        dates = f"{start_date} - {end_date}"
    elif start_date:
        dates = start_date

    # Calculate days if dates provided
    if not num_days and start_date and end_date:
        from datetime import datetime
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            num_days = (end - start).days + 1
        except:
            pass

    trip_data = {
        "title": title,
        "link": link,
        "dates": dates,
        "days": num_days,
        "locations": 0,
        "activities": 0,
        "map_status": "pending",
    }

    itinerary_data = {
        "title": title,
        "items": [],
        "start_date": start_date,
        "end_date": end_date,
        "travelers": []
    }

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            itinerary_json = json.dumps(itinerary_data)

            if USE_POSTGRES:
                cursor.execute("""
                    INSERT INTO trips (user_id, title, link, dates, days, locations, activities, map_status, itinerary_data, is_draft)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                    RETURNING id
                """, (
                    user_id, title, link, dates, num_days, 0, 0, "pending", itinerary_json
                ))
                trip_id = cursor.fetchone()[0]
            else:
                cursor.execute("""
                    INSERT INTO trips (user_id, title, link, dates, days, locations, activities, map_status, itinerary_data, is_draft)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """, (
                    user_id, title, link, dates, num_days, 0, 0, "pending", itinerary_json
                ))
                trip_id = cursor.lastrowid

            return {
                "id": trip_id,
                "link": link,
                "title": title,
                "dates": dates,
                "days": num_days,
                "start_date": start_date,
                "end_date": end_date,
                "is_draft": True,
                "itinerary_data": itinerary_data
            }
        except Exception as e:
            print(f"[DB] Error creating draft trip: {e}")
            return None


def get_draft_trips(user_id: int) -> List[Dict[str, Any]]:
    """Get all draft trips for a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute("""
                SELECT id, title, link, dates, days, locations, activities, map_status, map_error, is_public
                FROM trips WHERE user_id = %s AND is_draft = TRUE ORDER BY created_at DESC
            """, (user_id,))
            columns = ['id', 'title', 'link', 'dates', 'days', 'locations', 'activities', 'map_status', 'map_error', 'is_public']
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        else:
            cursor.execute("""
                SELECT id, title, link, dates, days, locations, activities, map_status, map_error, is_public
                FROM trips WHERE user_id = ? AND is_draft = 1 ORDER BY created_at DESC
            """, (user_id,))
            return [dict(row) for row in cursor.fetchall()]


def update_trip_itinerary_data(user_id: int, link: str, itinerary_data: Dict) -> bool:
    """Update a trip's itinerary_data (for auto-save)."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            itinerary_json = json.dumps(itinerary_data)

            # Also update counts from itinerary_data
            items = itinerary_data.get('items', [])
            locations = len(set(
                item.get('location', {}).get('name')
                for item in items
                if item.get('location') and item.get('location', {}).get('name')
            ))
            activities = len(items)

            if USE_POSTGRES:
                cursor.execute("""
                    UPDATE trips SET itinerary_data = %s, locations = %s, activities = %s
                    WHERE user_id = %s AND link = %s
                """, (itinerary_json, locations, activities, user_id, link))
            else:
                cursor.execute("""
                    UPDATE trips SET itinerary_data = ?, locations = ?, activities = ?
                    WHERE user_id = ? AND link = ?
                """, (itinerary_json, locations, activities, user_id, link))
            return cursor.rowcount > 0
        except Exception as e:
            print(f"[DB] Error updating trip itinerary: {e}")
            return False


def publish_draft(user_id: int, link: str) -> bool:
    """Publish a draft trip (set is_draft=False)."""
    with get_db() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute("""
                UPDATE trips SET is_draft = FALSE
                WHERE user_id = %s AND link = %s
            """, (user_id, link))
        else:
            cursor.execute("""
                UPDATE trips SET is_draft = 0
                WHERE user_id = ? AND link = ?
            """, (user_id, link))
        return cursor.rowcount > 0


def add_item_to_trip(user_id: int, link: str, item: Dict) -> bool:
    """Add an item to a trip's itinerary_data."""
    trip = get_trip_by_link(user_id, link)
    if not trip:
        return False

    itinerary_data = trip.get('itinerary_data') or {"title": trip["title"], "items": [], "travelers": []}
    if 'items' not in itinerary_data:
        itinerary_data['items'] = []

    itinerary_data['items'].append(item)
    return update_trip_itinerary_data(user_id, link, itinerary_data)


# Initialize database on import
init_db()
