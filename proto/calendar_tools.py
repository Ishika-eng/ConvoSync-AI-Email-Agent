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
    owner_email: str = None,
) -> tuple[str, str]:
    """
    Create a Google Calendar event and auto-send invites to all attendees.
    If owner_email is provided and has a token in DB, use that. Otherwise use assistant default.
    Returns: (calendar_event_link, google_meet_link)
    """
    from proto.db_tools import get_user_token
    from google.oauth2.credentials import Credentials

    creds = None
    if owner_email:
        token_data = get_user_token(owner_email)
        if token_data:
            print(f"   🔑 Using authorized token for {owner_email}")
            creds = Credentials.from_authorized_user_info(token_data)

    if not creds:
        # Fallback to assistant's default credentials
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
            end_dt = dateparser.parse(end_full, settings={"PREFER_DATES_FROM": "future", "RELATIVE_BASE": now, "RETURN_AS_TIMEZONE_AWARE": True})

        # 2. Fallback: try parsing the whole line as a single time (or just the start part)
        if not start_dt:
            clean = re.sub(r'\s*[-–]\s*\d{1,2}(?::\d{2})?(?:am|pm)?.*$', '', line, flags=re.IGNORECASE)
            start_dt = dateparser.parse(clean, settings={"PREFER_DATES_FROM": "future", "RELATIVE_BASE": now, "RETURN_AS_TIMEZONE_AWARE": True})

        if start_dt:
            # Check if year is too far in future (dateparser bug sometimes picks next year)
            if start_dt.year > now.year + 1:
                start_dt = start_dt.replace(year=now.year)
                if end_dt: end_dt = end_dt.replace(year=now.year)

            if end_dt and end_dt > start_dt:
                return start_dt, end_dt
            return start_dt, start_dt + timedelta(hours=1)

    return None


def get_participant_busy_slots(emails: list[str], start: datetime, end: datetime) -> list[dict]:
    """
    Fetch busy slots for multiple users from Google Calendar FreeBusy API.
    Only checks users who have authorized the assistant (token in DB).
    """
    from proto.db_tools import get_user_token
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    busy_slots = []
    for email in emails:
        token_data = get_user_token(email)
        if not token_data:
            continue

        try:
            import dateparser
            from datetime import timedelta, timezone
            creds = Credentials.from_authorized_user_info(token_data)
            service = build("calendar", "v3", credentials=creds)

            # Convert local naive time to Assistant's timezone, then to UTC for Google
            # We assume the extracted time is in the CALENDAR_TIMEZONE (default IST)
            import pytz
            tz_name = os.getenv("CALENDAR_TIMEZONE", "Asia/Kolkata")
            local_tz = pytz.timezone(tz_name)
            
            if start.tzinfo:
                start_aw = start.astimezone(pytz.utc)
                end_aw = end.astimezone(pytz.utc)
            else:
                start_aw = local_tz.localize(start).astimezone(pytz.utc)
                end_aw = local_tz.localize(end).astimezone(pytz.utc)

            body = {
                "timeMin": start_aw.isoformat().replace("+00:00", "Z"),
                "timeMax": end_aw.isoformat().replace("+00:00", "Z"),
                "items": [{"id": "primary"}]
            }
            print(f"   🔍 Querying FreeBusy for {email}: {body['timeMin']} -> {body['timeMax']}")
            res = service.freebusy().query(body=body).execute()
            slots = res.get("calendars", {}).get("primary", {}).get("busy", [])
            print(f"   🔍 Found {len(slots)} busy slots for {email}")
            for s in slots:
                # Normalize to naive UTC-like for comparison
                dt_start = dateparser.parse(s["start"]).replace(tzinfo=None)
                dt_end = dateparser.parse(s["end"]).replace(tzinfo=None)
                busy_slots.append({
                    "email": email,
                    "start": dt_start,
                    "end": dt_end
                })
        except Exception as e:
            print(f"   ⚠️ Could not fetch busy slots for {email}: {e}")

    return busy_slots


def find_consensus_slot(slots_text: str, participants: list[str]) -> tuple[datetime, datetime] | None:
    """
    Finds the best slot that works for ALL authorized participants.
    1. Parses all proposed slots.
    2. Fetches busy times for participants.
    3. Returns the first slot that has zero overlaps.
    """
    import dateparser
    from datetime import timedelta

    # 1. Parse all possible slots from the text
    lines = [l.strip("•- ").strip() for l in slots_text.splitlines() if l.strip()]
    proposed_slots = []
    now = datetime.now()

    for line in lines:
        slot = find_best_slot(line) # Re-use the smart parsing logic
        if slot:
            proposed_slots.append(slot)

    if not proposed_slots:
        return None

    # 2. Fetch busy slots for the range of the proposed times
    overall_start = min(s[0] for s in proposed_slots)
    overall_end = max(s[1] for s in proposed_slots)
    busy_data = get_participant_busy_slots(participants, overall_start, overall_end)

    # 3. Filter proposed slots against busy data
    import pytz
    tz_name = os.getenv("CALENDAR_TIMEZONE", "Asia/Kolkata")
    local_tz = pytz.timezone(tz_name)

    for p_start, p_end in proposed_slots:
        # Normalize proposed to naive UTC for accurate comparison with busy_data
        # If the slot is already aware (has a timezone like EST/PST), convert it directly.
        # Otherwise, assume it's in the assistant's local timezone (IST).
        if p_start.tzinfo:
            p_start_utc = p_start.astimezone(pytz.utc).replace(tzinfo=None)
            p_end_utc = p_end.astimezone(pytz.utc).replace(tzinfo=None)
        else:
            p_start_utc = local_tz.localize(p_start).astimezone(pytz.utc).replace(tzinfo=None)
            p_end_utc = local_tz.localize(p_end).astimezone(pytz.utc).replace(tzinfo=None)
        
        has_conflict = False
        for busy in busy_data:
            # Overlap check: (StartA < EndB) and (EndA > StartB)
            # Both sides are now naive UTC-equivalent
            if (p_start_utc < busy["end"]) and (p_end_utc > busy["start"]):
                print(f"   ⚠️ Conflict for {busy['email']} at {p_start.strftime('%I:%M %p')}")
                has_conflict = True
                break
        
        if not has_conflict:
            print(f"   ✅ Consensus reached: {p_start.strftime('%A %B %d, %I:%M %p')}")
            return p_start, p_end

    # Fallback: If everything has a conflict, return the first one anyway?
    # Or return None to signify "no consensus reachable"
    return proposed_slots[0]


