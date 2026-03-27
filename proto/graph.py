"""
graph.py — LangGraph agent definition (Solution B agentic loop)

Agent nodes:
  read_email → classify_intent → extract_slots → create_calendar → compose_reply → send_reply
                               ↘ summarize_thread ↗
"""
import os
from typing import TypedDict, Literal
from datetime import datetime
from langgraph.graph import StateGraph, END

from proto.email_tools import fetch_latest_unseen, send_reply, EmailMessage
from proto.llm_tools import (
    classify_intent,
    extract_time_slots,
    summarize_thread,
    compose_scheduling_reply,
    compose_update_reply,
)
from proto.calendar_tools import create_calendar_event, find_best_slot


# ── Agent State ──────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    email: EmailMessage | None          # raw email fetched from inbox
    participants: list[str]             # all emails in thread (To/Cc)
    intent: str                         # SCHEDULING_REQUEST | THREAD_UPDATE_REQUEST | OTHER
    processed_content: str              # slots text or summary
    cal_link: str                       # Google Calendar event link
    meet_link: str                      # Google Meet link
    reply_body: str                     # composed reply text
    status: str                         # done | skipped | error


# ── Nodes ────────────────────────────────────────────────────────────────────

def node_read_email(state: AgentState) -> AgentState:
    """Node 1: Read the latest unread email from Gmail via IMAP."""
    print("\n🔍 [Node] read_email")
    msg = fetch_latest_unseen()
    if msg:
        return {**state, "email": msg, "participants": msg.recipients}
    return {**state, "email": msg, "participants": []}


def node_classify_intent(state: AgentState) -> AgentState:
    """Node 2: Use LLM to classify the email intent."""
    print("🧠 [Node] classify_intent")
    em = state["email"]
    if em is None:
        return {**state, "intent": "OTHER", "status": "skipped"}

    intent = classify_intent(em.subject, em.body)
    print(f"   → Intent: {intent}")
    return {**state, "intent": intent}


def node_extract_slots(state: AgentState) -> AgentState:
    """Node 3a: Extract time slots from a scheduling email."""
    print("📅 [Node] extract_slots")
    slots = extract_time_slots(state["email"].body)
    print(f"   → Slots found:\n{slots}")
    return {**state, "processed_content": slots}


def node_create_calendar(state: AgentState) -> AgentState:
    """Node 4: Parse the best slot and create a Google Calendar event."""
    print("📆 [Node] create_calendar")
    em = state["email"]
    slots_text = state["processed_content"]
    participants = state["participants"]

    # --- ADVANCED: Consensus Engine ---
    from proto.calendar_tools import find_consensus_slot
    slot = find_consensus_slot(slots_text, participants)

    if slot is None:
        print("   → No parseable or available slot found, skipping calendar creation")
        return {**state, "cal_link": "", "meet_link": ""}

    start, end = slot
    print(f"   → Scheduling: {start.strftime('%A %B %d, %I:%M %p')} → {end.strftime('%I:%M %p')}")

    # Extract sender email as the event "owner" (if they are connected)
    sender_email = em.sender
    import re
    match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', sender_email)
    owner_email = match.group() if match else None

    # Filter attendees (remove the assistant from invitations)
    assistant_email = os.getenv("ASSISTANT_EMAIL")
    attendees = [p for p in participants if p.lower() != assistant_email.lower()]

    try:
        cal_link, meet_link = create_calendar_event(
            title=f"Meeting: {em.subject or 'Team Sync'}",
            start=start,
            end=end,
            attendees=attendees,
            description=(
                f"Meeting coordinated by ConvoSync AI.\n"
                f"Consensus reached among: {', '.join(attendees)}\n"
            ),
            owner_email=owner_email,
        )
        return {**state, "cal_link": cal_link, "meet_link": meet_link}
    except Exception as e:
        print(f"   ⚠️ Calendar skipped: {e}")
        return {**state, "cal_link": "", "meet_link": ""}


def node_summarize_thread(state: AgentState) -> AgentState:
    """Node 3b: Summarize the email thread for an update request."""
    print("📝 [Node] summarize_thread")
    summary = summarize_thread(state["email"].body)
    print(f"   → Summary:\n{summary}")
    return {**state, "processed_content": summary}


def node_compose_reply(state: AgentState) -> AgentState:
    """Node 5: Compose the reply email body using the LLM."""
    print("✍️  [Node] compose_reply")
    em = state["email"]
    sender_name = em.sender.split("<")[0].strip() or em.sender
    cal_link = state.get("cal_link", "")
    meet_link = state.get("meet_link", "")

    if state["intent"] == "SCHEDULING_REQUEST":
        body = compose_scheduling_reply(
            slots=state["processed_content"],
            sender_name=sender_name,
            cal_link=cal_link,
            meet_link=meet_link,
        )
    else:
        body = compose_update_reply(state["processed_content"], sender_name)

    print(f"   → Reply composed ({len(body)} chars)")
    return {**state, "reply_body": body}


def node_send_reply(state: AgentState) -> AgentState:
    """Node 6: Send the reply via Gmail SMTP."""
    print("📤 [Node] send_reply")
    em = state["email"]
    send_reply(
        to=em.sender,
        subject=em.subject,
        body=state["reply_body"],
        reply_to_msg_id=em.message_id,
    )
    return {**state, "status": "done"}


def node_skip(state: AgentState) -> AgentState:
    """Node: No action needed for this email."""
    print("⏭️  [Node] skip — intent is OTHER or no email found")
    return {**state, "status": "skipped"}


# ── Routing ──────────────────────────────────────────────────────────────────

def route_after_classify(state: AgentState) -> Literal[
    "extract_slots", "summarize_thread", "skip"
]:
    intent = state.get("intent", "OTHER")
    if intent == "SCHEDULING_REQUEST":
        return "extract_slots"
    elif intent == "THREAD_UPDATE_REQUEST":
        return "summarize_thread"
    return "skip"


# ── Build Graph ───────────────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(AgentState)

    # Register nodes
    g.add_node("read_email",       node_read_email)
    g.add_node("classify_intent",  node_classify_intent)
    g.add_node("extract_slots",    node_extract_slots)
    g.add_node("create_calendar",  node_create_calendar)
    g.add_node("summarize_thread", node_summarize_thread)
    g.add_node("compose_reply",    node_compose_reply)
    g.add_node("send_reply",       node_send_reply)
    g.add_node("skip",             node_skip)

    # Entry point
    g.set_entry_point("read_email")

    # Edges
    g.add_edge("read_email", "classify_intent")
    g.add_conditional_edges(
        "classify_intent",
        route_after_classify,
        {
            "extract_slots":    "extract_slots",
            "summarize_thread": "summarize_thread",
            "skip":             "skip",
        },
    )

    # Scheduling path: extract → calendar → compose → send
    g.add_edge("extract_slots",    "create_calendar")
    g.add_edge("create_calendar",  "compose_reply")

    # Update path: summarize → compose → send
    g.add_edge("summarize_thread", "compose_reply")

    g.add_edge("compose_reply",    "send_reply")
    g.add_edge("send_reply",       END)
    g.add_edge("skip",             END)

    return g.compile()
