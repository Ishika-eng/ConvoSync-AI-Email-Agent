import os
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import smtplib
from email.message import EmailMessage

from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from proto.db_tools import init_db, save_user_token, get_user_token

load_dotenv()
init_db()

# Allow HTTP for local development (Google normally requires HTTPS for OAuth)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- GOOGLE OAUTH CONFIG ---
CLIENT_SECRETS_FILE = "credentials.json"
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.modify",
    "openid"
]
REDIRECT_URI = "http://localhost:8000/auth/callback"

class ConnectionRequest(BaseModel):
    name: str
    email: str
    message: str

@app.get("/")
def read_root():
    return {"status": "ConvoSync Hub is Live", "version": "1.0.0"}

@app.get("/auth/login")
def login():
    """Starts the Google OAuth2 flow."""
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    return RedirectResponse(authorization_url)

@app.get("/auth/callback")
def callback(request: Request):
    """Handles the redirect back from Google and saves the token."""
    try:
        code = request.query_params.get("code")
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code missing")

        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Verify ID token to get the user's email
        id_info = id_token.verify_oauth2_token(
            credentials.id_token,
            google_requests.Request(),
            flow.client_config["client_id"]
        )
        email = id_info.get("email")

        # Save the token to SQLite
        token_dict = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes
        }
        save_user_token(email, token_dict)

        print(f"✅ Successfully connected: {email}")
        return RedirectResponse(url=f"http://localhost:5173/?connected=true&email={email}")

    except Exception as e:
        import traceback
        print("❌ OAUTH ERROR:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/send-to-ai")
def send_to_ai(req: ConnectionRequest):
    """Forwards a message to the AI assistant via SMTP."""
    assistant_email = os.getenv("ASSISTANT_EMAIL")
    app_password = os.getenv("GMAIL_APP_PASSWORD")

    if not assistant_email or not app_password:
        raise HTTPException(status_code=500, detail="Assistant email or app password not configured.")

    try:
        msg = EmailMessage()
        msg["Subject"] = f"New Connection Request from {req.name}"
        msg["From"] = assistant_email
        msg["To"] = assistant_email
        msg.set_content(f"Name: {req.name}\nEmail: {req.email}\n\nMessage:\n{req.message}")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(assistant_email, app_password)
            smtp.send_message(msg)

        return {"status": "success", "message": "Your message has been delivered to ConvoSync AI!"}
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to deliver message.")

@app.get("/auth/status/{email}")
def auth_status(email: str):
    """Checks if a user is already connected."""
    token = get_user_token(email)
    return {"connected": token is not None}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
