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
        "from the email. List them as bullet points with day and time. "
        "If no specific times are mentioned, say 'No specific times mentioned'. "
        "Be concise."
    )
    return call_llm(system, body)


def summarize_thread(body: str) -> str:
    """Summarize the email thread/topic."""
    system = (
        "You are an executive assistant. Summarize this email in 3-4 sentences. "
        "Cover: what it is about, key points, and current status or ask. "
        "Be concise and professional."
    )
    return call_llm(system, body)


def compose_scheduling_reply(slots: str, sender_name: str, cal_link: str = "", meet_link: str = "") -> str:
    """Compose a reply for a scheduling request, optionally including calendar details."""
    system = (
        "You are a professional AI scheduling assistant. "
        "Write a polite, concise email reply body (no subject, no sign-off). "
        "If a calendar link and meet link are provided, mention that the meeting has been "
        "scheduled and include them clearly. If not, acknowledge the slots and say you are coordinating. "
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
        "based on the thread summary provided. Keep it under 5 sentences."
    )
    user = f"Sender: {sender_name}\nThread summary:\n{summary}"
    return call_llm(system, user)
