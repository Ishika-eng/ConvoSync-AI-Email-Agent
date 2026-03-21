# AI Email Coordination Assistant — Implementation Plan

An autonomous email agent that monitors a dedicated inbox, parses scheduling/availability requests in plain English, computes common free slots across participants, creates Google Calendar events, sends invites, and responds to thread-update queries — all while appending an AI disclaimer to every outbound email.

---

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| **Runtime** | Python 3.11 | Rich ecosystem for NLP, Google APIs, IMAP |
| **Email (read)** | `imaplib` / Gmail IMAP | Free, no extra credentials beyond OAuth |
| **Email (send)** | Gmail SMTP via `smtplib` | Simple, reliable |
| **Gmail API** | `google-api-python-client` | Programmatic label/thread access |
| **Calendar API** | `google-api-python-client` | Official Google Calendar integration |
| **LLM (NLP core)** | Ollama + `llama3` (local) | Free / open-source; falls back to Groq API (free tier) |
| **Time parsing** | `dateparser` + `parsedatetime` | Robust NL date/time extraction |
| **Timezone** | `pytz` / `zoneinfo` | IANA timezone normalization |
| **Scheduling DB** | SQLite (via `sqlite3`) + JSON files | Zero-ops local state |
| **Auth / Secrets** | `google-auth-oauthlib`, `.env` via `python-dotenv` | Secure token storage |
| **Task queue** | APScheduler (in-process) | Polling loop without Redis/Celery overhead |
| **Testing** | `pytest` + `unittest.mock` | Standard Python testing |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Email Polling Loop                    │
│              (APScheduler — every 60 sec)               │
└────────────────────────┬────────────────────────────────┘
                         │ new emails
                         ▼
              ┌──────────────────────┐
              │   Email Ingestion    │  ← IMAP/Gmail API
              │   (fetch & parse)    │
              └──────────┬───────────┘
                         │
              ┌──────────▼───────────┐
              │  Intent Classifier   │  ← LLM prompt
              │  scheduling | update │
              └──────┬───────┬───────┘
                     │       │
          ┌──────────▼─┐  ┌──▼────────────┐
          │ Scheduling │  │Thread Intel   │
          │  Pipeline  │  │  Pipeline     │
          └──────┬─────┘  └──────┬────────┘
                 │               │
    ┌────────────▼──────┐   ┌────▼──────────────┐
    │Availability Parser│   │Thread Summarizer  │
    │(dateparser + LLM) │   │(LLM prompt chain) │
    └────────┬──────────┘   └────────┬──────────┘
             │                       │
    ┌────────▼──────────┐   ┌────────▼──────────┐
    │Overlap Resolver   │   │Reply Composer     │
    │(slot intersection)│   │(+ AI disclaimer)  │
    └────────┬──────────┘   └────────┬──────────┘
             │                       │
    ┌────────▼──────────┐            │
    │Google Calendar API│            │
    │(create event +    │            │
    │ send invites)     │            │
    └────────┬──────────┘            │
             │                       │
             └──────────┬────────────┘
                        ▼
              ┌─────────────────────┐
              │  Gmail SMTP Sender  │
              │  (+ AI disclaimer)  │
              └─────────────────────┘
```

---

## Proposed Changes / Components

### Component 1 — Project Scaffold & Auth

#### [NEW] `src/auth/gmail_auth.py`
- OAuth 2.0 flow for Gmail + Calendar scopes
- Stores/refreshes `token.json` automatically

#### [NEW] `src/auth/credentials_manager.py`
- Loads `.env` secrets (assistant Gmail, client ID/secret)
- Provides a singleton credentials object

#### [NEW] `.env.example`
- Template for `ASSISTANT_EMAIL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OLLAMA_HOST`, `GROQ_API_KEY`

---

### Component 2 — Email Ingestion

#### [NEW] `src/email_client/imap_reader.py`
- Connects via IMAP SSL to Gmail
- Fetches UNSEEN emails from INBOX
- Parses raw MIME → structured `EmailMessage` dataclass (subject, sender, body, thread_id, date)
- Marks processed emails with a Gmail label `AI-Processed`

#### [NEW] `src/email_client/thread_fetcher.py`
- Uses Gmail API `users.threads.get` to pull full thread history
- Returns ordered list of messages for a given `thread_id`

#### [NEW] `src/email_client/sender.py`
- Sends reply via SMTP
- Automatically appends:
  ```
  ---
  ⚠️ This message was sent by an experimental AI email assistant. 
  Please verify important information independently.
  ```

---

### Component 3 — Intent Classification

#### [NEW] `src/agent/intent_classifier.py`
- LLM prompt: classifies email as one of:
  - `SCHEDULING_REQUEST` — contains availability / meeting request
  - `THREAD_UPDATE_REQUEST` — asks for status/update on a topic
  - `OTHER` — no action needed
- Falls back to keyword heuristics if LLM unavailable

---

### Component 4 — Scheduling Pipeline

#### [NEW] `src/scheduling/availability_parser.py`
- Extracts time slots from free-form text using:
  1. `dateparser.parse()` for relative expressions ("next Monday 3pm")
  2. `parsedatetime` for complex phrases ("sometime Thursday afternoon")
  3. LLM fallback for ambiguous expressions
- Normalizes all slots to UTC `datetime` ranges
- Associates slots with participant email addresses

#### [NEW] `src/scheduling/overlap_resolver.py`
- Accepts `Dict[str, List[TimeSlot]]` per participant
- Computes intersection of all availability windows
- Returns ranked list of common slots (shortest conflict first)
- Handles "no overlap found" gracefully → asks participants to provide more slots

#### [NEW] `src/scheduling/calendar_manager.py`
- Wraps Google Calendar API v3
- `create_event(title, start, end, attendees, description)` → returns `event_id` + `meet_link`
- Sends Google Calendar invites automatically to all attendees via the API

#### [NEW] `src/scheduling/state_store.py`
- SQLite DB tracking active scheduling threads:
  - `thread_id`, `participants`, `collected_slots`, `status` (collecting | scheduled | failed)
- Prevents double-processing the same thread

---

### Component 5 — Thread Intelligence Pipeline

#### [NEW] `src/intelligence/thread_summarizer.py`
- Accepts ordered thread messages
- LLM prompt: "Summarize the latest status / update from this thread, focusing on what has changed most recently."
- Returns a concise contextual summary

#### [NEW] `src/intelligence/reply_composer.py`
- Combines the summary into a polished email reply
- Ensures professional tone
- Appends AI disclaimer

---

### Component 6 — LLM Gateway

#### [NEW] `src/llm/llm_client.py`
- Tries Ollama (`llama3`) first (local, free)
- Falls back to Groq API (`llama3-8b-8192`, free tier) if Ollama unavailable
- Provides `prompt(system, user) → str` interface used by all components

---

### Component 7 — Orchestrator & Polling Loop

#### [NEW] `src/agent/orchestrator.py`
- Main agent loop using APScheduler (60-second interval)
- Flow:
  1. Fetch new emails
  2. Classify intent
  3. Route to Scheduling or Thread Intelligence pipeline
  4. Send reply via `sender.py`
  5. Update state store

#### [NEW] `main.py`
- Entry point; starts the orchestrator

---

### Component 8 — Configuration & Utilities

#### [NEW] `src/utils/time_utils.py`
- Timezone conversion helpers
- Slot formatting (human-readable)

#### [NEW] `config.py`
- Central config: polling interval, disclaimer text, LLM model names, calendar timezone

---

### Component 9 — Tests

#### [NEW] `tests/test_availability_parser.py`
#### [NEW] `tests/test_overlap_resolver.py`
#### [NEW] `tests/test_intent_classifier.py`
#### [NEW] `tests/test_thread_summarizer.py`

---

## Folder Structure

```
AI-Email-Coordination-Assistant/
├── main.py
├── config.py
├── .env.example
├── requirements.txt
├── src/
│   ├── auth/
│   │   ├── gmail_auth.py
│   │   └── credentials_manager.py
│   ├── email_client/
│   │   ├── imap_reader.py
│   │   ├── thread_fetcher.py
│   │   └── sender.py
│   ├── agent/
│   │   ├── intent_classifier.py
│   │   └── orchestrator.py
│   ├── scheduling/
│   │   ├── availability_parser.py
│   │   ├── overlap_resolver.py
│   │   ├── calendar_manager.py
│   │   └── state_store.py
│   ├── intelligence/
│   │   ├── thread_summarizer.py
│   │   └── reply_composer.py
│   ├── llm/
│   │   └── llm_client.py
│   └── utils/
│       └── time_utils.py
└── tests/
    ├── test_availability_parser.py
    ├── test_overlap_resolver.py
    ├── test_intent_classifier.py
    └── test_thread_summarizer.py
```

---

## Phased Build Plan

| Phase | Work | Deliverable |
|---|---|---|
| **1 — Auth & Email I/O** | Gmail OAuth, IMAP read, SMTP send | Can read inbox & send reply with disclaimer |
| **2 — LLM Gateway** | Ollama + Groq fallback wrapper | `llm_client.prompt()` working |
| **3 — Intent Classification** | Classify SCHEDULING vs UPDATE | Emails correctly routed |
| **4 — Availability Parsing** | dateparser + LLM + timezone normalization | Slots extracted from free-form text |
| **5 — Overlap & Calendar** | Slot intersection + Google Calendar event creation | Meeting created, invites sent |
| **6 — Thread Intelligence** | Thread fetch + LLM summarization + reply | Update emails answered contextually |
| **7 — State Machine** | SQLite tracking multi-turn scheduling threads | No duplicate processing |
| **8 — Polish & Tests** | Pytest suite, error handling, retry logic | Production-ready agent |

---

## Verification Plan

### Automated Tests
```bash
pytest tests/ -v
```
- Unit test: slot extraction from 10+ NL expressions
- Unit test: overlap computation with 3 participants
- Unit test: intent classification accuracy against labelled samples
- Unit test: thread summarizer output is non-empty and relevant

### Integration Tests (manual)
1. Send a scheduling request email to the assistant address with 2–3 participants CC'd → verify Calendar event created + invite received
2. Send a follow-up "any update?" email in an existing thread → verify contextual summary reply
3. Verify every outbound email contains the AI disclaimer
4. Test "no overlap" scenario → verify assistant replies asking for more availability

> [!IMPORTANT]
> You will need a dedicated Google account for the assistant, with Gmail IMAP enabled and OAuth credentials (`client_id`, `client_secret`) from Google Cloud Console with **Gmail API** and **Google Calendar API** scopes enabled.

> [!NOTE]
> All AI components use open-source/free models: Ollama (`llama3`) locally, Groq free tier as cloud fallback. No paid AI API is required.
