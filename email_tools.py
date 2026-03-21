"""
email_tools.py — IMAP reader + SMTP sender (Solution C)
"""
import imaplib
import smtplib
import email as email_lib
from email.header import decode_header
from email.mime.text import MIMEText
import os
from dataclasses import dataclass

DISCLAIMER = """

---
⚠️ This reply was sent by an experimental AI email assistant.
Please verify important information independently.
"""


@dataclass
class EmailMessage:
    uid: str
    sender: str
    subject: str
    body: str
    message_id: str


def fetch_latest_unseen() -> EmailMessage | None:
    """Fetch the single latest unread email from the inbox."""
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(os.getenv("ASSISTANT_EMAIL"), os.getenv("GMAIL_APP_PASSWORD"))
    mail.select("inbox")

    _, uids = mail.search(None, "UNSEEN")
    uid_list = uids[0].split()

    if not uid_list:
        print("📭 No unread emails found.")
        mail.logout()
        return None

    # Process the latest unread
    uid = uid_list[-1]
    _, data = mail.fetch(uid, "(RFC822)")
    raw = email_lib.message_from_bytes(data[0][1])

    # Decode subject
    subject_parts = decode_header(raw.get("Subject", ""))
    subject = ""
    for part, enc in subject_parts:
        if isinstance(part, bytes):
            subject += part.decode(enc or "utf-8", errors="ignore")
        else:
            subject += part

    # Extract plain-text body
    body = ""
    if raw.is_multipart():
        for part in raw.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode(errors="ignore")
                break
    else:
        body = raw.get_payload(decode=True).decode(errors="ignore")

    msg = EmailMessage(
        uid=uid.decode(),
        sender=raw.get("From", ""),
        subject=subject,
        body=body.strip(),
        message_id=raw.get("Message-ID", ""),
    )

    mail.logout()
    print(f"📬 Fetched email from: {msg.sender} | Subject: {msg.subject}")
    return msg


def send_reply(to: str, subject: str, body: str, reply_to_msg_id: str = None):
    """Send a reply email via SMTP with the AI disclaimer appended."""
    msg = MIMEText(body + DISCLAIMER)
    msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    msg["From"] = os.getenv("ASSISTANT_EMAIL")
    msg["To"] = to
    if reply_to_msg_id:
        msg["In-Reply-To"] = reply_to_msg_id
        msg["References"] = reply_to_msg_id

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(os.getenv("ASSISTANT_EMAIL"), os.getenv("GMAIL_APP_PASSWORD"))
        smtp.send_message(msg)

    print(f"✅ Reply sent to: {to}")
