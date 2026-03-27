"""
llm_tools.py — Groq LLM wrapper (Solution B AI engine)
All LLM calls go through here.
"""
import os
from groq import Groq

_client = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _client


def call_llm(system: str, user: str, model: str = "llama-3.1-8b-instant") -> str:
    """Single LLM call: system prompt + user message → response string."""
    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


# ── Specific LLM tasks ──────────────────────────────────────────────────────

def classify_intent(subject: str, body: str) -> str:
    """Returns: SCHEDULING_REQUEST | THREAD_UPDATE_REQUEST | OTHER"""
    system = (
        "You are an email intent classifier. "
        "Classify the email into EXACTLY one of these categories:\n"
        "- SCHEDULING_REQUEST: email discusses availability, meeting times, "
        "  scheduling, calendar, time slots\n"
        "- THREAD_UPDATE_REQUEST: email asks for a status update, progress "
        "  report, or summary of a topic\n"
        "- OTHER: anything else\n"
        "Reply with ONLY the category name, nothing else."
    )
    user = f"Subject: {subject}\n\nBody:\n{body}"
    result = call_llm(system, user).upper()

    if "SCHEDULING" in result:
        return "SCHEDULING_REQUEST"
    elif "UPDATE" in result or "THREAD" in result:
        return "THREAD_UPDATE_REQUEST"
    return "OTHER"


def extract_time_slots(body: str) -> str:
    """Extract mentioned time slots from email body as readable text."""
    system = (
        "You are a scheduling assistant. Extract all mentioned time slots "
        "from the email. List them as bullet points with day, time, and timezone "
        "if specified (e.g., 'Monday 10am EST', 'Tuesday 2pm GMT'). "
        "Crucial: Do not ignore timezone markers like EST, PST, UTC, or GMT. "
        "If no specific times are mentioned, say 'No specific times mentioned'. "
        "Be concise."
    )
    return call_llm(system, body)


def extract_meeting_metadata(body: str) -> dict:
    """Extract location and determine if the meeting is physical.
    Returns: {'location': str, 'is_physical': bool}
    """
    system = (
        "You are a logistics assistant. Analyze the email and extract:\n"
        "1. Location: The specific place mentioned (e.g., 'Starbucks', 'Zoom', 'The Office').\n"
        "2. Type: Is this a 'Physical' meeting or 'Virtual'?\n"
        "If no location is mentioned, assume 'TBD'.\n"
        "Return the result as a raw JSON object with keys 'location' and 'is_physical' (boolean)."
    )
    import json
    try:
        raw = call_llm(system, body)
        # Handle cases where LLM adds markdown or fluff
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        data = json.loads(raw)
        return {
            "location": data.get("location", "TBD"),
            "is_physical": bool(data.get("is_physical", False))
        }
    except:
        return {"location": "TBD", "is_physical": False}


def summarize_thread(body: str) -> str:
    """Summarize the email thread/topic."""
    system = (
        "You are an executive assistant. Summarize this email thread in 3-4 sentences. "
        "CRITICAL: Ignore any signatures, legal disclaimers, or assistant warnings "
        "(e.g., 'This reply was sent by an experimental AI assistant'). "
        "Do NOT include meta-talk like 'Here is a summary'. Just provide the summary points."
    )
    return call_llm(system, body)


def compose_scheduling_reply(slots: str, sender_name: str, cal_link: str = "", meet_link: str = "") -> str:
    """Compose a reply for a scheduling request, optionally including calendar details."""
    system = (
        "You are a professional AI scheduling assistant. "
        "Write a polite, concise email reply body (no subject, no sign-off). "
        "CRITICAL: If the mentioned slots start with 'Confirmed:', you MUST use "
        "only that specific date and time for the reply. Ignore all other options. "
        "If a calendar link and meet link are provided in the input, mention that the meeting "
        "has been scheduled and include the EXACT links provided. "
        "If NO links are provided, do NOT invent any. Just acknowledge the slots. "
        "Keep it under 6 sentences."
    )
    calendar_info = ""
    if cal_link:
        calendar_info = f"\nCalendar invite: {cal_link}"
    if meet_link:
        calendar_info += f"\nGoogle Meet: {meet_link}"

    user = f"Sender: {sender_name}\nMentioned slots:\n{slots}{calendar_info}"
    return call_llm(system, user)


def compose_update_reply(summary: str, sender_name: str) -> str:
    """Compose a reply for a thread update request."""
    system = (
        "You are a professional AI executive assistant. "
        "Write a polite, concise email reply body (no subject, no sign-off) "
        "based on the thread summary provided. "
        "IMPORTANT: If the summary mentions 'verifying details independently', "
        "ignore that part as it is a system warning, not a user request. "
        "Keep it under 5 sentences."
    )
    user = f"Sender: {sender_name}\nThread summary:\n{summary}"
    return call_llm(system, user)
