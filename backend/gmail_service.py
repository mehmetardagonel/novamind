import os
import base64
import logging
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

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Sanity check so you fail fast if env is wrong
_required = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_PROJECT_ID", "GOOGLE_REDIRECT_URI"]
_missing = [k for k in _required if not os.getenv(k)]
if _missing:
    raise RuntimeError(f"Missing required Gmail env vars: {', '.join(_missing)}")


def _get_credentials() -> Credentials:
    """
    Load credentials from token.json if exists, otherwise run OAuth flow using CLIENT_CONFIG
    and save token.json. No client_secret.json is ever used.
    """
    creds: Optional[Credentials] = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # If there are no (valid) credentials, do the OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh existing token
            creds.refresh(Request())
        else:
            # First-time auth: open browser and ask user to sign in
            flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open("token.json", "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    return creds


def get_gmail_service():
    """
    Returns an authenticated Gmail API service client.
    """
    creds = _get_credentials()
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


def fetch_messages(query: Optional[str] = None, max_results: int = 50) -> List[EmailOut]:
    """
    Fetch messages from Gmail matching the search query and map them to EmailOut model.
    Handles pagination to fetch up to max_results emails (Gmail API returns max 500 per request).
    """
    service = get_gmail_service()
    all_message_refs = []
    page_token = None
    emails: List[EmailOut] = []

    try:
        logger.info(f"Requesting messages from Gmail API with query: '{query or 'ALL'}'")
        # Fetch message references with pagination
        while len(all_message_refs) < max_results:
            # Calculate remaining emails to fetch
            remaining = max_results - len(all_message_refs)
            # Gmail API maxResults is capped at 500 per request
            page_size = min(500, remaining)

            list_resp = service.users().messages().list(
                userId="me",
                q=query or "",
                maxResults=page_size,
                pageToken=page_token
            ).execute()

            message_refs = list_resp.get("messages", [])
            all_message_refs.extend(message_refs)

            # Check if there are more pages
            page_token = list_resp.get("nextPageToken")
            if not page_token:
                # No more pages available
                break

        # Ensure we don't exceed max_results
        all_message_refs = all_message_refs[:max_results]

        # Fetch full message details for each reference
        for ref in all_message_refs:
            try:
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
                        id=msg["id"],
                        sender=sender,
                        recipient=recipient,
                        subject=subject,
                        body=body,
                        date=date_value,
                    )
                )
            except Exception as e:
                # Log but continue with other messages
                import logging
                logging.warning(f"Failed to fetch message {ref['id']}: {str(e)}")
                continue

        return emails
    except Exception as e:
        import logging
        logging.error(f"Error fetching messages: {str(e)}")
        return emails  # Return what we've fetched so far


def send_email(sender: str, to: str, subject: str, body: str) -> dict:
    """
    Send an email via Gmail API.
    `sender` can be "me" or a full email address.
    """
    service = get_gmail_service()
    
    logger.info(f"Sending email via Gmail API to: {to}")

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


def get_current_user_email() -> str:
    """
    Uses Gmail API to get the authenticated user's email address.
    """
    service = get_gmail_service()
    profile = service.users().getProfile(userId="me").execute()
    return profile.get("emailAddress", "")


def create_draft(to: str, subject: str, body: str) -> dict:
    """
    Create a draft email in Gmail (stored with DRAFT label).
    Returns draft object with draft id and message details.
    """
    service = get_gmail_service()
    
    logger.info(f"Creating draft via Gmail API for: {to}")

    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    draft = service.users().drafts().create(
        userId="me",
        body={"message": {"raw": raw}}
    ).execute()

    return draft


def get_drafts(max_results: int = 50) -> List[dict]:
    """
    Fetch all draft messages from Gmail (label:DRAFT).
    Returns list of draft objects.
    """
    service = get_gmail_service()
    
    logger.info("Fetching drafts from Gmail API...")

    drafts_list = service.users().drafts().list(
        userId="me",
        maxResults=max_results
    ).execute()

    drafts = drafts_list.get("drafts", [])
    return drafts


def get_drafts_by_recipient(to_email: str, max_results: int = 50) -> List[dict]:
    """
    Get all drafts for a specific recipient email address.
    Returns list of draft objects with full message details.
    Uses Gmail Drafts API (not Messages API) to get actual draft IDs.
    """
    service = get_gmail_service()

    try:
        # Get all drafts
        drafts_list = service.users().drafts().list(
            userId="me",
            maxResults=max_results
        ).execute()

        drafts = drafts_list.get("drafts", [])
        filtered_drafts = []

        # Filter drafts by recipient
        for draft in drafts:
            try:
                # Get full draft details including message
                full_draft = service.users().drafts().get(
                    userId="me",
                    id=draft["id"],
                    format="full"
                ).execute()

                # Extract recipient from message headers
                msg = full_draft.get("message", {})
                headers = msg.get("payload", {}).get("headers", [])
                recipient = _extract_header(headers, "To")

                # Check if recipient matches
                if to_email.lower() in recipient.lower():
                    # Add draft ID to the response
                    full_draft["draft_id"] = draft["id"]

                    # Extract subject and date from headers for easy access
                    full_draft["subject"] = _extract_header(headers, "Subject") or "(No subject)"
                    full_draft["date"] = _extract_header(headers, "Date") or "Unknown"

                    filtered_drafts.append(full_draft)
            except Exception as e:
                import logging
                logging.warning(f"Failed to get draft {draft['id']}: {str(e)}")
                continue

        return filtered_drafts

    except Exception as e:
        import logging
        logging.error(f"Error getting drafts for recipient {to_email}: {str(e)}")
        return []


def get_draft_by_id(draft_id: str) -> Optional[dict]:
    """
    Get a specific draft by ID.
    Returns draft object or None if not found.
    """
    service = get_gmail_service()

    try:
        draft = service.users().drafts().get(
            userId="me",
            id=draft_id
        ).execute()
        return draft
    except Exception:
        return None


def delete_draft(draft_id: str) -> bool:
    """
    Delete a draft email by ID.
    Returns True if successful, False otherwise.
    """
    service = get_gmail_service()

    try:
        service.users().drafts().delete(
            userId="me",
            id=draft_id
        ).execute()
        return True
    except Exception:
        return False


def send_draft(draft_id: str) -> Optional[dict]:
    """
    Send a draft email and remove it from drafts.
    Returns sent message object or None if failed.
    """
    service = get_gmail_service()

    try:
        sent = service.users().drafts().send(
            userId="me",
            body={"id": draft_id}
        ).execute()
        return sent
    except Exception as e:
        import logging
        logging.error(f"Failed to send draft {draft_id}: {str(e)}")
        return None


def update_draft(draft_id: str, to: Optional[str] = None,
                subject: Optional[str] = None, body: Optional[str] = None) -> Optional[dict]:
    """
    Update a draft email. Since Gmail API doesn't support partial updates,
    we delete the old draft and create a new one with updated content.

    Args:
        draft_id: ID of the draft to update
        to: New recipient email
        subject: New subject
        body: New body content

    Returns: New draft object or None if failed
    """
    service = get_gmail_service()

    try:
        # Get existing draft to preserve unmodified fields
        existing_draft = get_draft_by_id(draft_id)
        if not existing_draft:
            return None

        # Extract existing message details
        msg = existing_draft.get("message", {})
        msg_id = msg.get("id")

        # Fetch full message to get current headers
        full_msg = service.users().messages().get(
            userId="me",
            id=msg_id,
            format="full"
        ).execute()

        headers = full_msg.get("payload", {}).get("headers", [])
        current_to = to or _extract_header(headers, "To")
        current_subject = subject or _extract_header(headers, "Subject")
        current_body = body or _decode_body(full_msg.get("payload", {}))

        # Create new draft with updated content FIRST (to avoid data loss if creation fails)
        new_draft = create_draft(current_to, current_subject, current_body)

        # Only delete old draft if new one was created successfully
        if new_draft and new_draft.get("id"):
            try:
                delete_draft(draft_id)
            except Exception as e:
                # Log but don't fail - new draft exists, old one can be manually deleted
                import logging
                logging.warning(f"Could not delete old draft {draft_id}: {e}")

        return new_draft
    except Exception:
        return None


def delete_all_spam() -> dict:
    """
    Delete all spam emails from Gmail (query: is:spam).
    Returns dict with deleted_count, failed_count, and failed_ids for tracking.
    """
    service = get_gmail_service()

    try:
        # Find all spam messages
        spam_list = service.users().messages().list(
            userId="me",
            q="is:spam"
        ).execute()

        spam_messages = spam_list.get("messages", [])
        deleted_count = 0
        failed_count = 0
        failed_ids = []

        # Delete each spam message
        for msg in spam_messages:
            try:
                service.users().messages().delete(
                    userId="me",
                    id=msg["id"]
                ).execute()
                deleted_count += 1
            except Exception as e:
                failed_count += 1
                failed_ids.append(msg["id"])
                import logging
                logging.warning(f"Failed to delete spam {msg['id']}: {str(e)}")
                continue

        # Log summary if there were failures
        if failed_count > 0:
            import logging
            logging.warning(f"Spam deletion summary: {deleted_count} deleted, {failed_count} failed. Failed IDs: {failed_ids}")

        return {
            "deleted_count": deleted_count,
            "failed_count": failed_count,
            "failed_ids": failed_ids
        }
    except Exception as e:
        import logging
        logging.error(f"Error deleting spam: {str(e)}")
        return {
            "deleted_count": 0,
            "failed_count": 0,
            "failed_ids": [],
            "error": str(e)
        }


def move_mails(email_ids: List[str], target_label_name: str, remove_from_inbox: bool = True) -> int:
    """
    Move emails to a target folder/label.
    Gmail doesn't have folders, it uses labels. This function adds the target label
    and optionally removes INBOX label (for true "move" behavior).

    Args:
        email_ids: List of message IDs to move
        target_label_name: Name of the target label (e.g., 'Work', 'Archive')
        remove_from_inbox: If True, removes INBOX label when moving (default: True for true move behavior)

    Returns: Count of successfully moved emails
    """
    service = get_gmail_service()

    try:
        logger.info(f"Moving {len(email_ids)} emails to label '{target_label_name}' via Gmail API")
        # Get all labels to find target label ID
        labels_response = service.users().labels().list(userId="me").execute()
        labels = labels_response.get("labels", [])

        target_label_id = None
        for label in labels:
            if label.get("name") == target_label_name:
                target_label_id = label.get("id")
                break

        # If label doesn't exist, create it
        if not target_label_id:
            new_label = service.users().labels().create(
                userId="me",
                body={"name": target_label_name}
            ).execute()
            target_label_id = new_label.get("id")

        # Move each email by adding the target label
        actually_moved_count = 0
        for email_id in email_ids:
            try:
                # Get email's current labels to avoid duplicates and handle removal
                msg = service.users().messages().get(
                    userId="me",
                    id=email_id,
                    format="minimal"
                ).execute()
                current_labels = msg.get("labelIds", [])

                # Skip if email already has the target label
                if target_label_id in current_labels:
                    continue

                # Prepare modification body
                modify_body = {"addLabelIds": [target_label_id]}

                # Remove INBOX if requested and email is in INBOX and target is not INBOX
                if remove_from_inbox and "INBOX" in current_labels and target_label_name != "INBOX":
                    modify_body["removeLabelIds"] = ["INBOX"]

                service.users().messages().modify(
                    userId="me",
                    id=email_id,
                    body=modify_body
                ).execute()
                actually_moved_count += 1
            except Exception as e:
                # Log but continue with other emails
                import logging
                logging.warning(f"Failed to move email {email_id}: {e}")
                continue

        return actually_moved_count
    except Exception as e:
        import logging
        logging.error(f"Error in move_mails: {e}")
        return 0
