import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    ASSISTANT_EMAIL = os.getenv("ASSISTANT_EMAIL")
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    CALENDAR_TIMEZONE = os.getenv("CALENDAR_TIMEZONE", "Asia/Kolkata")
    POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", 60))
    
    # AI Disclaimer
    DISCLAIMER = """
---
⚠️ This reply was sent by an experimental AI email assistant.
Please verify important information independently.
"""

    # Preferences
    WORK_HOURS_START = int(os.getenv("WORK_HOURS_START", 9))  # 9 AM
    WORK_HOURS_END = int(os.getenv("WORK_HOURS_END", 21))    # 9 PM
    BUFFER_MINUTES = int(os.getenv("BUFFER_MINUTES", 15))
    TRAVEL_BUFFER_MINUTES = int(os.getenv("TRAVEL_BUFFER_MINUTES", 30))
    
    # Habits (Reclaim-style protection)
    # Format: {"name": str, "start": "HH:MM", "end": "HH:MM"}
    HABITS = [
        {"name": "Lunch", "start": "12:00", "end": "13:30"},
        {"name": "Focus Time", "start": "09:00", "end": "10:30"}, 
    ]
    
config = Config()
