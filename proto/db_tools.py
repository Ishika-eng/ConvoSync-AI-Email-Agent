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
