import os
import base64
from email.mime.text import MIMEText
from typing import List, Optional

from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from models import EmailOut

from datetime import datetime
from email.utils import parsedate_to_datetime

from pathlib import Path

load_dotenv()

SCOPES = ["https://mail.google.com/"]

# Build client config directly from env (no client_secret.json)
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

TOKENS_DIR = Path("tokens")
TOKENS_DIR.mkdir(exist_ok=True)

# Sanity check so you fail fast if env is wrong
_required = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_PROJECT_ID", "GOOGLE_REDIRECT_URI"]
_missing = [k for k in _required if not os.getenv(k)]
if _missing:
    raise RuntimeError(f"Missing required Gmail env vars: {', '.join(_missing)}")


def _get_credentials(user_id: str) -> Credentials:
    """
    Load credentials from token.json if exists, otherwise run OAuth flow using CLIENT_CONFIG
    and save token.json. No client_secret.json is ever used.
    """
    creds: Optional[Credentials] = None
    token_path = TOKENS_DIR / f"token_{user_id}.json"

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
            creds = flow.run_local_server(port=0)

        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds

def get_gmail_service(user_id: str):
    creds = _get_credentials(user_id)
    return build("gmail", "v1", credentials=creds)

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

def fetch_messages(query: Optional[str] = None, max_results: int = 50, user_id: str = "") -> List[EmailOut]:
    """
    Fetch messages from Gmail matching the search query and map them to EmailOut model.
    """
    service = get_gmail_service(user_id=user_id)

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
                message_id=msg["id"],
                sender=sender,
                recipient=recipient,
                subject=subject,
                body=body,
                date=date_value,  # 👈 pass datetime, not the raw string
            )
        )

    return emails

def send_email(sender: str, to: str, subject: str, body: str, user_id: str = "") -> dict:
    """
    Send an email via Gmail API.
    `sender` can be "me" or a full email address.
    """
    service = get_gmail_service(user_id=user_id)

    message = MIMEText(body)
    message["to"] = to
    message["from"] = sender
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    body_dict = {"raw": raw}

    sent = service.users().messages().send(
        userId="me",
        body=body_dict,
    ).execute()

    return sent

def get_current_user_email(user_id: str = "") -> str:
    """
    Uses Gmail API to get the authenticated user's email address.
    """
    service = get_gmail_service(user_id=user_id)
    profile = service.users().getProfile(userId="me").execute()
    return profile.get("emailAddress", "")

def _to_emailout(msg: dict) -> EmailOut:
    headers = msg.get("payload", {}).get("headers", [])
    subject = _extract_header(headers, "Subject")
    sender = _extract_header(headers, "From")
    recipient = _extract_header(headers, "To")
    date_str = _extract_header(headers, "Date")
    body = _decode_body(msg.get("payload", {}))

    dt: Optional[datetime] = None
    if date_str:
        try:
            dt = parsedate_to_datetime(date_str)
        except Exception:
            dt = None

    return EmailOut(
        message_id=msg["id"],
        sender=sender,
        recipient=recipient,
        subject=subject,
        body=body,
        date=dt,
    )

def fetch_messages_by_label(label_id: str, max_results: int = 50, include_spam_trash: bool = False, user_id: str = "") -> list[EmailOut]:
    """
    List messages by Gmail system/user label.
    System labels include: INBOX, SENT, STARRED, IMPORTANT, SPAM, TRASH, DRAFT, etc.
    """
    service = get_gmail_service(user_id=user_id)

    resp = service.users().messages().list(
        userId="me",
        labelIds=[label_id],
        maxResults=max_results,
        includeSpamTrash=include_spam_trash
    ).execute()

    refs = resp.get("messages", [])
    results: list[EmailOut] = []

    for ref in refs:
        msg = service.users().messages().get(
            userId="me",
            id=ref["id"],
            format="full",
        ).execute()
        results.append(_to_emailout(msg))

    return results

def fetch_drafts(max_results: int = 50, user_id: str = "") -> list[EmailOut]:
    """
    List Drafts. Drafts API is separate from messages.
    """
    service = get_gmail_service(user_id=user_id)

    resp = service.users().drafts().list(userId="me", maxResults=max_results).execute()
    drafts = resp.get("drafts", [])
    results: list[EmailOut] = []

    for dr in drafts:
        d = service.users().drafts().get(userId="me", id=dr["id"]).execute()
        # draft payload wraps a 'message' object
        msg = d.get("message", {})
        if msg:
            # Ensure we have full message if needed
            if not msg.get("payload"):
                msg = service.users().messages().get(
                    userId="me", id=msg["id"], format="full"
                ).execute()
            results.append(_to_emailout(msg))

    return results

def trash_message(message_id: str, user_id: str = "") -> dict:
    """
    Move a message to Trash.
    """
    service = get_gmail_service(user_id=user_id)
    return service.users().messages().trash(
        userId="me",
        id=message_id
    ).execute()

def set_star(message_id: str, starred: bool, user_id: str = "") -> dict:
    """
    Star or unstar a message using the STARRED label.
    """
    service = get_gmail_service(user_id=user_id)

    if starred:
        body = {
            "addLabelIds": ["STARRED"],
            "removeLabelIds": []
        }
    else:
        body = {
            "addLabelIds": [],
            "removeLabelIds": ["STARRED"]
        }

    return service.users().messages().modify(
        userId="me",
        id=message_id,
        body=body
    ).execute()
