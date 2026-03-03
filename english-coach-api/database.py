"""
💾 Database Module — Session History Storage
=============================================
Uses SQLite to store practice sessions so the user
can track their progress over time.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "english_coach.db"


def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the sessions table if it doesn't exist."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            mode TEXT NOT NULL,
            original_text TEXT NOT NULL,
            analysis_json TEXT NOT NULL,
            audio_filename TEXT,
            grammar_score INTEGER,
            fluency_score INTEGER,
            overall_score INTEGER
        )
    """)
    conn.commit()
    conn.close()


def save_session(mode: str, original_text: str, analysis: dict, audio_filename: str | None = None) -> int:
    """Save a practice session and return its ID."""
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO sessions (timestamp, mode, original_text, analysis_json, audio_filename, grammar_score, fluency_score, overall_score)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now().isoformat(timespec="seconds"),
            mode,
            original_text,
            json.dumps(analysis),
            audio_filename,
            analysis.get("grammar_score", 0),
            analysis.get("fluency_score", 0),
            analysis.get("overall_score", 0),
        )
    )
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    return session_id


def get_sessions(limit: int = 50) -> list[dict]:
    """Get recent sessions."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_session(session_id: int) -> dict | None:
    """Get a single session by ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# Initialize DB on import
init_db()
