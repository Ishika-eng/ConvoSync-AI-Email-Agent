"""
calendar_tools.py — Google Calendar event creation + auto-invite (Solution C + B)
"""
import os
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from proto.google_auth import get_google_credentials


def create_calendar_event(
    title: str,
    start: datetime,
    end: datetime,
    attendees: list[str],
    description: str = "",
) -> tuple[str, str]:
    """
    Create a Google Calendar event and auto-send invites to all attendees.
    Returns: (calendar_event_link, google_meet_link)
    """
    creds = get_google_credentials()
    service = build("calendar", "v3", credentials=creds)

    tz = os.getenv("CALENDAR_TIMEZONE", "Asia/Kolkata")

    event = {
        "summary": title,
        "description": description,
        "start": {
            "dateTime": start.isoformat(),
            "timeZone": tz,
        },
        "end": {
            "dateTime": end.isoformat(),
            "timeZone": tz,
        },
        "attendees": [{"email": a} for a in attendees],
        "conferenceData": {
            "createRequest": {
                "requestId": f"proto-meet-{int(start.timestamp())}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }

    result = service.events().insert(
        calendarId="primary",
        body=event,
        conferenceDataVersion=1,
        sendUpdates="all",   # ← auto-emails invites to all attendees
    ).execute()

    cal_link = result.get("htmlLink", "")
    meet_link = result.get("conferenceData", {}).get("entryPoints", [{}])[0].get("uri", "")

    print(f"   → Calendar event created: {cal_link}")
    print(f"   → Meet link: {meet_link}")
    return cal_link, meet_link


def find_best_slot(slots_text: str) -> tuple[datetime, datetime] | None:
    """
    Parse the LLM's extracted slots text and return the best (first valid) slot.
    Handles formats like: 'Sunday, 4pm-5pm', 'Tuesday 3-4pm', 'Monday 10am'
    Returns a (start, end) tuple or None if nothing parseable.
    """
    import dateparser
    import re
    from datetime import datetime

    # Use current time as base to avoid jumping to 2027
    now = datetime.now()
    
    lines = [l.strip("•- ").strip() for l in slots_text.splitlines() if l.strip()]

    for line in lines:
        # Skip lines that say "no specific time"
        if "no specific" in line.lower() or "not mentioned" in line.lower():
            continue

        start_dt = end_dt = None

        # 1. Try to detect a time range like "4pm-5pm" or "3-4pm"
        range_match = re.search(
            r'(\d{1,2}(?::\d{2})?(?:am|pm)?)\s*[-–]\s*(\d{1,2}(?::\d{2})?(?:am|pm)?)\b',
            line, re.IGNORECASE
        )

        if range_match:
            prefix = line[:range_match.start()].strip().rstrip(',').strip()
            start_str = range_match.group(1)
            end_str = range_match.group(2)

            # Bi-directional am/pm inheritance
            # Case 1: "2-3pm" -> inherit "pm" from end
            if not re.search(r'am|pm', start_str, re.IGNORECASE) and re.search(r'am|pm', end_str, re.IGNORECASE):
                suffix = re.search(r'am|pm', end_str, re.IGNORECASE).group()
                start_str += suffix
            
            # Case 2: "10am-11" -> inherit "am" from start
            elif re.search(r'am|pm', start_str, re.IGNORECASE) and not re.search(r'am|pm', end_str, re.IGNORECASE):
                suffix = re.search(r'am|pm', start_str, re.IGNORECASE).group()
                end_str += suffix

            # Combine prefix (e.g. "Wednesday") + time
            start_full = f"{prefix} {start_str}".strip() if prefix else start_str
            end_full = f"{prefix} {end_str}".strip() if prefix else end_str

            start_dt = dateparser.parse(start_full, settings={"PREFER_DATES_FROM": "future", "RELATIVE_BASE": now})
            end_dt = dateparser.parse(end_full, settings={"PREFER_DATES_FROM": "future", "RELATIVE_BASE": now})

        # 2. Fallback: try parsing the whole line as a single time (or just the start part)
        if not start_dt:
            clean = re.sub(r'\s*[-–]\s*\d{1,2}(?::\d{2})?(?:am|pm)?.*$', '', line, flags=re.IGNORECASE)
            start_dt = dateparser.parse(clean, settings={"PREFER_DATES_FROM": "future", "RELATIVE_BASE": now})

        if start_dt:
            # Check if year is too far in future (dateparser bug sometimes picks next year)
            if start_dt.year > now.year + 1:
                start_dt = start_dt.replace(year=now.year)
                if end_dt: end_dt = end_dt.replace(year=now.year)

            if end_dt and end_dt > start_dt:
                return start_dt, end_dt
            return start_dt, start_dt + timedelta(hours=1)

    return None


