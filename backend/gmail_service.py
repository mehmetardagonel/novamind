import os
import base64
from email.mime.text import MIMEText
from typing import List, Optional

from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from models import EmailOut

from datetime import datetime
from email.utils import parsedate_to_datetime

load_dotenv()

SCOPES = ["https://mail.google.com/"]

# Build client config directly from env (no client_secret.json)
# This is now used by main.py to create the flow
CLIENT_CONFIG = {
    "installed": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "project_id": os.getenv("GOOGLE_PROJECT_ID"),
        "auth_uri": os.getenv("GOOGLE_AUTH_URI"),
        "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
        "auth_provider_x509_cert_url": os.getenv("GOOGLE_AUTH_PROVIDER_X509_CERT_URL"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI")],
    }
}

# Sanity check so you fail fast if env is wrong
_required = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_PROJECT_ID", "GOOGLE_REDIRECT_URI"]
_missing = [k for k in _required if not os.getenv(k)]
if _missing:
    raise RuntimeError(f"Missing required Gmail env vars: {', '.join(_missing)}")


def _get_credentials() -> Optional[Credentials]:
    """
    Tries to load credentials from token.json.
    Tries to refresh if expired.
    Returns None if no token or refresh fails.
    IT DOES NOT RUN THE AUTH FLOW.
    """
    creds: Optional[Credentials] = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # If no credentials, return None.
    if not creds:
        return None
        
    # If they are valid, return them
    if creds.valid:
        return creds

    # If they are expired and refreshable, try to refresh
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Save the refreshed credentials
            with open("token.json", "w", encoding="utf-8") as token_file:
                token_file.write(creds.to_json())
            return creds
        except Exception:
            # Refresh failed, delete bad token and return None
            os.remove("token.json")
            return None

    # Not valid, not refreshable
    return None


def get_gmail_service():
    """
    Returns an authenticated Gmail API service client.
    Raises Exception("AUTH_REQUIRED") if credentials are not found or invalid.
    """
    creds = _get_credentials()
    
    # This is the new trigger that main.py will catch
    if not creds:
        raise Exception("AUTH_REQUIRED")
        
    return build("gmail", "v1", credentials=creds)


# --- All functions below this line are UNCHANGED ---
# They will now correctly propagate the "AUTH_REQUIRED" exception
# if get_gmail_service() fails.

def _extract_header(headers: List[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _decode_body(payload: dict) -> str:
    """
    Extracts a text/plain body from the Gmail message payload.
    Fallbacks to snippet if no simple body is found.
    """
    # If multipart, search parts
    if payload.get("parts"):
        for part in payload["parts"]:
            mime_type = part.get("mimeType", "")
            if mime_type.startswith("text/plain"):
                body = part.get("body", {}).get("data")
                if body:
                    return base64.urlsafe_b64decode(body).decode("utf-8", errors="ignore")
        # fallback: first part text/html or so
        for part in payload["parts"]:
            body = part.get("body", {}).get("data")
            if body:
                return base64.urlsafe_b64decode(body).decode("utf-8", errors="ignore")

    # Non-multipart
    body = payload.get("body", {}).get("data")
    if body:
        return base64.urlsafe_b64decode(body).decode("utf-8", errors="ignore")

    return ""


def fetch_messages(query: Optional[str] = None, max_results: int = 50) -> List[EmailOut]:
    """
    Fetch messages from Gmail matching the search query and map them to EmailOut model.
    """
    service = get_gmail_service() # This will now raise "AUTH_REQUIRED" if not logged in

    list_resp = service.users().messages().list(
        userId="me",
        q=query or "",
        maxResults=max_results,
    ).execute()

    message_refs = list_resp.get("messages", [])
    emails: List[EmailOut] = []

    for ref in message_refs:
        msg = service.users().messages().get(
            userId="me",
            id=ref["id"],
            format="full",
        ).execute()

        headers = msg.get("payload", {}).get("headers", [])
        subject = _extract_header(headers, "Subject")
        sender = _extract_header(headers, "From")
        recipient = _extract_header(headers, "To")
        date_str = _extract_header(headers, "Date")

        # Gmail date header is RFC 2822; parse it into datetime
        date_value: Optional[datetime] = None
        if date_str:
            try:
                date_value = parsedate_to_datetime(date_str)
            except Exception:
                date_value = None  # fallback if parsing fails

        body = _decode_body(msg.get("payload", {}))

        emails.append(
            EmailOut(
                sender=sender,
                recipient=recipient,
                subject=subject,
                body=body,
                date=date_value,
            )
        )

    return emails


def send_email(sender: str, to: str, subject: str, body: str) -> dict:
    """
    Send an email via Gmail API.
    `sender` can be "me" or a full email address.
    """
    service = get_gmail_service() # This will also raise the error

    message = MIMEText(body)
    message["to"] = to
    message["from"] = sender
    message["subject"] = subject

    raw = base66.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    body_dict = {"raw": raw}

    sent = service.users().messages().send(
        userId="me",
        body=body_dict,
    ).execute()

    return sent


def get_current_user_email() -> str:
    """
    Uses Gmail API to get the authenticated user's email address.
    """
    service = get_gmail_service() # This will also raise the error
    profile = service.users().getProfile(userId="me").execute()
    return profile.get("emailAddress", "")