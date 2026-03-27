# AI Email Coordination Assistant

A production-grade, autonomous email agent that monitors an inbox, coordinates meeting times across participants using LLM-powered reasoning, and manages Google Calendar events.

## Features
- **Agentic Loop**: Built with **LangGraph** for robust multi-turn task completion.
- **Persistence**: SQLite database tracks conversation state and participant availability.
- **Calendar Integration**: Automatic Google Calendar event creation and invite dispatch.
- **Thread Intelligence**: High-level context understanding by analyzing full email histories.
- **Timezone Aware**: Normalizes availability to UTC and displays localized times for participants.
- **Disclaimer Integration**: Every AI-generated response includes a mandatory experimental disclaimer.

## Setup

### 1. Prerequisites
- Python 3.10+
- Google Cloud Project with **Gmail API** and **Google Calendar API** enabled.
- `credentials.json` (OAuth Desktop App) in the project root.
- Groq API Key (for LLM reasoning).

### 2. Installation
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configuration
Copy `.env.example` to `.env` and fill in:
- `ASSISTANT_EMAIL`: The bot's Gmail address.
- `GMAIL_APP_PASSWORD`: App password from Google Security settings.
- `GROQ_API_KEY`: Your Groq platform key.
- `CALENDAR_TIMEZONE`: e.g., `Asia/Kolkata` or `America/New_York`.

## Usage
### Start Monitoring
```bash
python main.py --watch
```

### Run Once
```bash
python main.py
```

## Project Structure
- `src/agent`: LangGraph workflow.
- `src/auth`: Google OAuth logic.
- `src/email`: Gmail client (IMAP/SMTP/API).
- `src/calendar`: Calendar management.
- `src/db`: Persistence layer.
- `src/utils`: Utilities like logging and time normalization.
