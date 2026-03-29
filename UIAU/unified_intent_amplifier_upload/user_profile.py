"""
user_profile.py — SQLite-backed user profile. Stores calibration data,
preferences, and usage stats. All data stays local — never sent anywhere.
"""

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from config import DB_PATH

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection to the local profile database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL DEFAULT 'Default User',
                created_at TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'English'
            );

            CREATE TABLE IF NOT EXISTS settings (
                profile_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (profile_id, key),
                FOREIGN KEY (profile_id) REFERENCES profiles(id)
            );

            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                event TEXT NOT NULL,
                data TEXT,
                logged_at TEXT NOT NULL,
                FOREIGN KEY (profile_id) REFERENCES profiles(id)
            );
        """)
        # Ensure at least one default profile exists
        cur = conn.execute("SELECT COUNT(*) FROM profiles")
        if cur.fetchone()[0] == 0:
            conn.execute(
                "INSERT INTO profiles (name, created_at, language) VALUES (?, ?, ?)",
                ("Default User", datetime.utcnow().isoformat(), "English")
            )
        logger.info("Database initialised at %s", DB_PATH)


def get_active_profile() -> dict:
    """Return the first (active) user profile as a dict."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM profiles ORDER BY id LIMIT 1").fetchone()
        return dict(row) if row else {}


def save_setting(key: str, value, profile_id: int = 1) -> None:
    """Upsert a setting key/value for a profile."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO settings (profile_id, key, value, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(profile_id, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
        """, (profile_id, key, json.dumps(value), datetime.utcnow().isoformat()))


def load_setting(key: str, default=None, profile_id: int = 1):
    """Load a setting value for a profile. Returns default if not found."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE profile_id=? AND key=?",
            (profile_id, key)
        ).fetchone()
        if row:
            return json.loads(row["value"])
        return default


def log_event(event: str, data: dict = None, profile_id: int = 1) -> None:
    """Log a usage event for analytics (stored locally only)."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO usage_log (profile_id, event, data, logged_at) VALUES (?, ?, ?, ?)",
            (profile_id, event, json.dumps(data or {}), datetime.utcnow().isoformat())
        )


def update_language(language: str, profile_id: int = 1) -> None:
    """Update the preferred language for a profile."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE profiles SET language=? WHERE id=?",
            (language, profile_id)
        )
    logger.info("Language updated to %s", language)
