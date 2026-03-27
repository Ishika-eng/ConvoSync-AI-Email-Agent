import sqlite3
import json
import os

DB_PATH = "assistant_state.db"

def init_db():
    """Initializes the SQLite database and creates the user_tokens table."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_tokens (
                email TEXT PRIMARY KEY,
                token_json TEXT NOT NULL,
                preferences_json TEXT, -- NEW: store working hours
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def save_user_token(email: str, token_data: dict):
    """Saves or updates the token JSON for a specific user email."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        token_json = json.dumps(token_data)
        cursor.execute("""
            INSERT INTO user_tokens (email, token_json)
            VALUES (?, ?)
            ON CONFLICT(email) DO UPDATE SET token_json=excluded.token_json
        """, (email, token_json))
        conn.commit()

def save_user_preferences(email: str, preferences: dict):
    """Saves or updates the preferences JSON for a specific user email."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        pref_json = json.dumps(preferences)
        cursor.execute("""
            UPDATE user_tokens SET preferences_json = ? WHERE email = ?
        """, (pref_json, email))
        conn.commit()

def get_user_preferences(email: str) -> dict | None:
    """Retrieves the preferences JSON for a specific user email."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT preferences_json FROM user_tokens WHERE email = ?", (email,))
        row = cursor.fetchone()
        if row and row[0]:
            return json.loads(row[0])
    # Default preferences if none set
    return {
        "office_start": "09:00",
        "office_end": "18:00",
        "lunch_start": "13:00",
        "lunch_end": "14:00",
        "dinner_start": "20:00",
        "dinner_end": "21:00"
    }

def get_user_token(email: str) -> dict | None:
    """Retrieves the token JSON for a specific user email."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT token_json FROM user_tokens WHERE email = ?", (email,))
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
    return None

if __name__ == "__main__":
    init_db()
    print("✅ Database initialized")
