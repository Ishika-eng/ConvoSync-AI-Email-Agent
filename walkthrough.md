# AI Email Coordination Assistant — Step-by-Step Implementation Guide

---

## Phase 1 — Project Setup

### 1.1 Create the folder structure
```bash
cd /Users/ishikamahadar/Documents/AI-Email-Coordination-Assistant
mkdir -p src/auth src/email_client src/agent src/scheduling src/intelligence src/llm src/utils tests
touch main.py config.py
```

### 1.2 Create `requirements.txt`
```text
google-api-python-client==2.120.0
google-auth-httplib2==0.2.0
google-auth-oauthlib==1.2.0
python-dotenv==1.0.1
APScheduler==3.10.4
dateparser==1.2.0
parsedatetime==2.6
pytz==2024.1
requests==2.31.0
groq==0.9.0
pytest==8.1.1
```

### 1.3 Create `.env.example`
```env
ASSISTANT_EMAIL=your-assistant@gmail.com
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
OLLAMA_HOST=http://localhost:11434
GROQ_API_KEY=your_groq_api_key
ASSISTANT_NAME=AI Email Assistant
CALENDAR_TIMEZONE=Asia/Kolkata
POLL_INTERVAL_SECONDS=60
```

### 1.4 Set up virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Phase 2 — Google OAuth & Auth Module

### 2.1 Create a Google Cloud Project
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project → e.g., `AI-Email-Assistant`
3. Go to **APIs & Services → Library**
   - Enable **Gmail API**
   - Enable **Google Calendar API**
4. Go to **APIs & Services → OAuth consent screen**
   - User type: **External** → fill app name → add your assistant email as a test user
5. Go to **APIs & Services → Credentials**
   - Click **Create Credentials → OAuth client ID**
   - App type: **Desktop App**
   - Download `credentials.json` → place it in the project root

### 2.2 `src/auth/gmail_auth.py`
```python
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/calendar",
]

def get_credentials():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds
```

### 2.3 `src/auth/credentials_manager.py`
```python
from dotenv import load_dotenv
import os
from src.auth.gmail_auth import get_credentials

load_dotenv()

class CredentialsManager:
    _creds = None

    @classmethod
    def get(cls):
        if not cls._creds:
            cls._creds = get_credentials()
        return cls._creds

    @classmethod
    def assistant_email(cls):
        return os.getenv("ASSISTANT_EMAIL")
```

---

## Phase 3 — Email Ingestion

### 3.1 `src/email_client/imap_reader.py`
```python
import imaplib
import email
from email.header import decode_header
from dataclasses import dataclass
from typing import List
import os

@dataclass
class EmailMessage:
    uid: str
    sender: str
    subject: str
    body: str
    thread_id: str
    date: str

def fetch_unseen_emails() -> List[EmailMessage]:
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(os.getenv("ASSISTANT_EMAIL"), os.getenv("GMAIL_APP_PASSWORD"))
    mail.select("inbox")
    _, uids = mail.search(None, "UNSEEN")
    messages = []
    for uid in uids[0].split():
        _, data = mail.fetch(uid, "(RFC822)")
        raw = email.message_from_bytes(data[0][1])
        body = ""
        if raw.is_multipart():
            for part in raw.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode(errors="ignore")
                    break
        else:
            body = raw.get_payload(decode=True).decode(errors="ignore")
        messages.append(EmailMessage(
            uid=uid.decode(),
            sender=raw.get("From"),
            subject=raw.get("Subject", ""),
            body=body,
            thread_id=raw.get("Message-ID", ""),
            date=raw.get("Date", ""),
        ))
    mail.logout()
    return messages
```

> **Note:** Use a Gmail **App Password** (not your main password). Generate at: Google Account → Security → 2-Step Verification → App Passwords.

### 3.2 `src/email_client/thread_fetcher.py`
```python
from googleapiclient.discovery import build
from src.auth.credentials_manager import CredentialsManager
import base64

def fetch_thread(thread_id: str):
    creds = CredentialsManager.get()
    service = build("gmail", "v1", credentials=creds)
    thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
    messages = []
    for msg in thread.get("messages", []):
        payload = msg.get("payload", {})
        body = ""
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    data = part["body"].get("data", "")
                    body = base64.urlsafe_b64decode(data).decode(errors="ignore")
                    break
        sender = next((h["value"] for h in payload.get("headers", []) if h["name"] == "From"), "")
        messages.append({"sender": sender, "body": body})
    return messages
```

### 3.3 `src/email_client/sender.py`
```python
import smtplib
import os
from email.mime.text import MIMEText

DISCLAIMER = """

---
⚠️ This message was sent by an experimental AI email assistant.
Please verify important information independently.
"""

def send_reply(to: str, subject: str, body: str, reply_to_msg_id: str = None):
    msg = MIMEText(body + DISCLAIMER)
    msg["Subject"] = subject if subject.startswith("Re:") else f"Re: {subject}"
    msg["From"] = os.getenv("ASSISTANT_EMAIL")
    msg["To"] = to
    if reply_to_msg_id:
        msg["In-Reply-To"] = reply_to_msg_id
        msg["References"] = reply_to_msg_id

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(os.getenv("ASSISTANT_EMAIL"), os.getenv("GMAIL_APP_PASSWORD"))
        smtp.send_message(msg)
```

---

## Phase 4 — LLM Gateway

### 4.1 Install Ollama & pull llama3
```bash
# Install Ollama (Mac)
brew install ollama
ollama serve &       # start in background
ollama pull llama3   # download model (~4GB)
```

### 4.2 Get a free Groq API key (fallback)
Go to [console.groq.com](https://console.groq.com) → sign up free → generate API key → paste into `.env`

### 4.3 `src/llm/llm_client.py`
```python
import requests
import os
from groq import Groq

def prompt(system: str, user: str) -> str:
    # Try Ollama first (local)
    try:
        resp = requests.post(
            f"{os.getenv('OLLAMA_HOST', 'http://localhost:11434')}/api/generate",
            json={"model": "llama3", "prompt": f"{system}\n\n{user}", "stream": False},
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json().get("response", "").strip()
    except Exception:
        pass

    # Fallback: Groq API
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    chat = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return chat.choices[0].message.content.strip()
```

---

## Phase 5 — Intent Classifier

### `src/agent/intent_classifier.py`
```python
from src.llm.llm_client import prompt

SYSTEM = """You are an email classifier. Classify the email into exactly one of:
- SCHEDULING_REQUEST: email mentions availability, meeting, scheduling, time slots
- THREAD_UPDATE_REQUEST: email asks for status, update, progress on a topic
- OTHER: anything else
Reply with only the class name, nothing else."""

def classify(subject: str, body: str) -> str:
    result = prompt(SYSTEM, f"Subject: {subject}\n\nBody: {body}")
    result = result.strip().upper()
    if "SCHEDULING" in result:
        return "SCHEDULING_REQUEST"
    elif "UPDATE" in result or "THREAD" in result:
        return "THREAD_UPDATE_REQUEST"
    return "OTHER"
```

---

## Phase 6 — Scheduling Pipeline

### 6.1 `src/scheduling/availability_parser.py`
```python
import dateparser
from src.llm.llm_client import prompt
from typing import List, Tuple
from datetime import datetime

def parse_slots(email_body: str, sender: str) -> List[Tuple[datetime, datetime]]:
    system = """Extract all time slots from the email. Return as JSON list:
[{"start": "YYYY-MM-DD HH:MM", "end": "YYYY-MM-DD HH:MM"}, ...]
If only a start time is mentioned, assume 1-hour slot. Return only JSON."""
    raw = prompt(system, email_body)
    import json, re
    try:
        data = json.loads(re.search(r'\[.*\]', raw, re.DOTALL).group())
        slots = []
        for item in data:
            start = dateparser.parse(item["start"])
            end = dateparser.parse(item["end"])
            if start and end:
                slots.append((start, end))
        return slots
    except Exception:
        return []
```

### 6.2 `src/scheduling/overlap_resolver.py`
```python
from typing import Dict, List, Tuple
from datetime import datetime

def find_overlaps(availability: Dict[str, List[Tuple[datetime, datetime]]]) -> List[Tuple[datetime, datetime]]:
    """Find time slots where ALL participants are free."""
    if not availability:
        return []
    all_slots = list(availability.values())
    common = all_slots[0]
    for participant_slots in all_slots[1:]:
        new_common = []
        for s1_start, s1_end in common:
            for s2_start, s2_end in participant_slots:
                overlap_start = max(s1_start, s2_start)
                overlap_end = min(s1_end, s2_end)
                if overlap_start < overlap_end:
                    new_common.append((overlap_start, overlap_end))
        common = new_common
    return sorted(common, key=lambda x: x[0])
```

### 6.3 `src/scheduling/calendar_manager.py`
```python
from googleapiclient.discovery import build
from src.auth.credentials_manager import CredentialsManager
from datetime import datetime
import os

def create_event(title: str, start: datetime, end: datetime, attendees: list, description: str = ""):
    creds = CredentialsManager.get()
    service = build("calendar", "v3", credentials=creds)
    tz = os.getenv("CALENDAR_TIMEZONE", "Asia/Kolkata")
    event = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": tz},
        "end": {"dateTime": end.isoformat(), "timeZone": tz},
        "attendees": [{"email": a} for a in attendees],
        "conferenceData": {
            "createRequest": {"requestId": f"meet-{int(start.timestamp())}"}
        },
    }
    result = service.events().insert(
        calendarId="primary",
        body=event,
        conferenceDataVersion=1,
        sendUpdates="all",  # sends calendar invites automatically
    ).execute()
    return result.get("htmlLink"), result.get("hangoutLink")
```

### 6.4 `src/scheduling/state_store.py`
```python
import sqlite3
import json

DB = "scheduling_state.db"

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS threads (
            thread_id TEXT PRIMARY KEY,
            participants TEXT,
            slots TEXT,
            status TEXT
        )
    """)
    conn.commit(); conn.close()

def upsert_thread(thread_id, participants, slots, status):
    conn = sqlite3.connect(DB)
    conn.execute("""
        INSERT INTO threads VALUES (?, ?, ?, ?)
        ON CONFLICT(thread_id) DO UPDATE SET
        participants=excluded.participants,
        slots=excluded.slots,
        status=excluded.status
    """, (thread_id, json.dumps(participants), json.dumps(slots, default=str), status))
    conn.commit(); conn.close()

def get_thread(thread_id):
    conn = sqlite3.connect(DB)
    row = conn.execute("SELECT * FROM threads WHERE thread_id=?", (thread_id,)).fetchone()
    conn.close()
    return row
```

---

## Phase 7 — Thread Intelligence Pipeline

### 7.1 `src/intelligence/thread_summarizer.py`
```python
from src.llm.llm_client import prompt

def summarize_thread(messages: list) -> str:
    thread_text = "\n\n".join(
        [f"From: {m['sender']}\n{m['body']}" for m in messages]
    )
    system = """You are an executive assistant. Read this email thread and write a concise 
status update (3-5 sentences) covering: what was discussed, what decisions were made, 
and the current status. Be factual and professional."""
    return prompt(system, thread_text)
```

### 7.2 `src/intelligence/reply_composer.py`
```python
from src.llm.llm_client import prompt

def compose_update_reply(summary: str, original_subject: str) -> str:
    system = """You are a professional executive assistant writing an email reply.
Write a short, professional email body using the provided summary as context.
Do not add a subject line. Do not add a sign-off."""
    body = prompt(system, f"Thread summary: {summary}\n\nOriginal subject: {original_subject}")
    return body
```

---

## Phase 8 — Orchestrator & Entry Point

### 8.1 `src/agent/orchestrator.py`
```python
from src.email_client.imap_reader import fetch_unseen_emails
from src.email_client.thread_fetcher import fetch_thread
from src.email_client.sender import send_reply
from src.agent.intent_classifier import classify
from src.scheduling.availability_parser import parse_slots
from src.scheduling.overlap_resolver import find_overlaps
from src.scheduling.calendar_manager import create_event
from src.scheduling.state_store import init_db, upsert_thread, get_thread
from src.intelligence.thread_summarizer import summarize_thread
from src.intelligence.reply_composer import compose_update_reply

def run_once():
    init_db()
    emails = fetch_unseen_emails()
    for em in emails:
        intent = classify(em.subject, em.body)

        if intent == "SCHEDULING_REQUEST":
            slots = parse_slots(em.body, em.sender)
            state = get_thread(em.thread_id)
            all_slots = {em.sender: slots}

            if state:
                import json
                existing = json.loads(state[2])
                all_slots.update(existing)
                participants = json.loads(state[1]) + [em.sender]
            else:
                participants = [em.sender]

            upsert_thread(em.thread_id, participants, all_slots, "collecting")
            overlaps = find_overlaps(all_slots)

            if overlaps and len(participants) >= 2:
                best_start, best_end = overlaps[0]
                cal_link, meet_link = create_event(
                    title=f"Meeting: {em.subject}",
                    start=best_start,
                    end=best_end,
                    attendees=participants,
                )
                upsert_thread(em.thread_id, participants, all_slots, "scheduled")
                body = (f"Great news! I've found a common time and scheduled the meeting.\n\n"
                        f"📅 Time: {best_start.strftime('%A, %B %d at %I:%M %p')}\n"
                        f"🔗 Calendar: {cal_link}\n"
                        f"🎥 Meet: {meet_link}\n\n"
                        f"Calendar invites have been sent to all participants.")
            else:
                body = ("Thank you for sharing your availability. "
                        "I'm still waiting for responses from other participants. "
                        "I'll confirm the meeting time once everyone has responded.")

            send_reply(em.sender, em.subject, body, em.thread_id)

        elif intent == "THREAD_UPDATE_REQUEST":
            thread_msgs = fetch_thread(em.thread_id)
            summary = summarize_thread(thread_msgs)
            reply_body = compose_update_reply(summary, em.subject)
            send_reply(em.sender, em.subject, reply_body, em.thread_id)
```

### 8.2 `main.py`
```python
from apscheduler.schedulers.blocking import BlockingScheduler
from src.agent.orchestrator import run_once
import os
from dotenv import load_dotenv

load_dotenv()

scheduler = BlockingScheduler()
interval = int(os.getenv("POLL_INTERVAL_SECONDS", 60))
scheduler.add_job(run_once, "interval", seconds=interval)

print(f"🤖 AI Email Assistant started. Polling every {interval}s...")
run_once()  # run immediately on start
scheduler.start()
```

---

## Phase 9 — Tests

### `tests/test_overlap_resolver.py`
```python
from src.scheduling.overlap_resolver import find_overlaps
from datetime import datetime

def test_basic_overlap():
    slots = {
        "a@x.com": [(datetime(2024,4,1,10,0), datetime(2024,4,1,12,0))],
        "b@x.com": [(datetime(2024,4,1,11,0), datetime(2024,4,1,13,0))],
    }
    result = find_overlaps(slots)
    assert len(result) == 1
    assert result[0][0] == datetime(2024,4,1,11,0)
    assert result[0][1] == datetime(2024,4,1,12,0)

def test_no_overlap():
    slots = {
        "a@x.com": [(datetime(2024,4,1,9,0), datetime(2024,4,1,10,0))],
        "b@x.com": [(datetime(2024,4,1,11,0), datetime(2024,4,1,12,0))],
    }
    assert find_overlaps(slots) == []
```

### Run tests
```bash
pytest tests/ -v
```

---

## Phase 10 — Run the Assistant

### Copy `.env.example` → `.env` and fill values
```bash
cp .env.example .env
# edit .env with your credentials
```

### Start the agent
```bash
source venv/bin/activate
python main.py
```

### End-to-End Test
1. **Scheduling test** — Send an email to your assistant address:
   > *"Hi, can we schedule a meeting? I'm free Monday 3-5pm and Tuesday morning."*
   - Expected: Assistant replies with a confirmed time + Google Calendar invite in your inbox

2. **Thread update test** — Reply to any thread:
   > *"What's the latest on this?"*
   - Expected: Assistant replies with a contextual summary of the thread

3. **Verify disclaimer** — Check that every reply ends with the AI disclaimer text ✅

---

## Quick Reference — File → Purpose

| File | Purpose |
|---|---|
| `main.py` | Entry point, starts polling loop |
| `src/auth/gmail_auth.py` | OAuth 2.0 flow |
| `src/email_client/imap_reader.py` | Reads new emails |
| `src/email_client/sender.py` | Sends replies + disclaimer |
| `src/agent/intent_classifier.py` | Routes email to correct pipeline |
| `src/llm/llm_client.py` | LLM calls (Ollama → Groq) |
| `src/scheduling/availability_parser.py` | Extracts time slots from NL |
| `src/scheduling/overlap_resolver.py` | Finds common free slots |
| `src/scheduling/calendar_manager.py` | Creates Google Calendar events |
| `src/scheduling/state_store.py` | Tracks scheduling thread state |
| `src/intelligence/thread_summarizer.py` | Summarizes email threads |
| `src/intelligence/reply_composer.py` | Writes professional replies |
