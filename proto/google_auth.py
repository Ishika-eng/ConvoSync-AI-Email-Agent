"""
google_auth.py — OAuth 2.0 for Google Calendar API
On first run, opens a browser for the user to authorize.
Saves token to token.json for subsequent runs.
"""
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
]


def get_google_credentials():
    """Get valid Google OAuth credentials, refreshing or re-authorizing as needed."""
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("credentials.json"):
                raise FileNotFoundError(
                    "credentials.json not found.\n"
                    "Download it from Google Cloud Console:\n"
                    "APIs & Services → Credentials → OAuth 2.0 Client → Download JSON\n"
                    "Place it in the project root as credentials.json"
                )
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return creds
