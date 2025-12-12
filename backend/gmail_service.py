import os
import base64
import logging
from email.mime.text import MIMEText
from typing import List, Optional, Dict

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
    Load credentials from token.json if exists, otherwise raise AUTH_REQUIRED.
    This allows the web application to handle OAuth flow via redirect.
    """
    creds: Optional[Credentials] = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # If there are no (valid) credentials, raise AUTH_REQUIRED
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Try to refresh existing token
            try:
                creds.refresh(Request())
                # Save the refreshed credentials
                with open("token.json", "w", encoding="utf-8") as token_file:
                    token_file.write(creds.to_json())
            except Exception as e:
                # If refresh fails, need to re-authenticate
                logger.error(f"Token refresh failed: {str(e)}")
                raise Exception("AUTH_REQUIRED")
        else:
            # No valid credentials - need to authenticate
            raise Exception("AUTH_REQUIRED")

    return creds


def get_gmail_service(credentials: Credentials = None, user_id: str | None = None):
    """
    Build Gmail API service with provided credentials.
    If no credentials provided, falls back to legacy token.json (backward compatibility).
    """
    if credentials is None:
        # Backward compatibility: use old token.json approach
        credentials = _get_credentials()
    return build("gmail", "v1", credentials=credentials)


async def get_user_gmail_service(user_id: str, account_id: str):
    """
    Get Gmail service for a specific user's account.
    Fetches credentials from database.
    """
    from gmail_account_service import gmail_account_service

    credentials = await gmail_account_service.get_credentials(user_id, account_id)
    if not credentials:
        raise Exception("ACCOUNT_NOT_FOUND")

    if not credentials.valid:
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                # Get email address from token info or Gmail profile
                service_temp = build("gmail", "v1", credentials=credentials)
                profile = service_temp.users().getProfile(userId="me").execute()
                email_address = profile.get("emailAddress")

                # Save refreshed token back to database
                await gmail_account_service.save_account(
                    user_id=user_id,
                    email_address=email_address,
                    credentials=credentials
                )
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                raise Exception("AUTH_REQUIRED")
        else:
            raise Exception("AUTH_REQUIRED")

    return build("gmail", "v1", credentials=credentials)


async def get_primary_account_service(user_id: str):
    """
    Get Gmail service for user's primary account.
    Falls back to first account if no primary is set.
    Raises exception if no accounts connected.
    """
    from gmail_account_service import gmail_account_service

    accounts = await gmail_account_service.get_all_accounts(user_id)
    if not accounts:
        raise Exception("NO_GMAIL_ACCOUNTS_CONNECTED")

    # Find primary account, or use first as fallback
    primary_account = next(
        (acc for acc in accounts if acc.get("is_primary", False)),
        accounts[0]
    )

    logger.info(f"Using primary account: {primary_account['email_address']} for user {user_id}")

    return await get_user_gmail_service(user_id, primary_account["id"])


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


def fetch_messages(query: Optional[str] = None, max_results: int = 25) -> List[EmailOut]:
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
                        message_id=msg["id"],
                        sender=sender,
                        recipient=recipient,
                        subject=subject,
                        body=body,
                        date=date_value,
                        label_ids=msg.get("labelIds", []),
                    )
                )
            except Exception as e:
                # Log but continue with other messages
                import logging
                logging.warning(f"Failed to fetch message {ref['id']}: {str(e)}")
                continue

        return emails
    except Exception as e:
        logging.error(f"Error fetching messages: {str(e)}")
        if str(e) == "AUTH_REQUIRED":
            # re-raise so FastAPI can handle it and send auth_url
            raise
        return emails  # Return what we've fetched so far


def fetch_messages_with_service(
    service,
    query: Optional[str] = None,
    max_results: int = 25
) -> List[EmailOut]:
    """
    Fetch messages using a provided Gmail service instance.
    Used for multi-account support where service is already authenticated.
    """
    all_message_refs = []
    page_token = None
    emails: List[EmailOut] = []

    try:
        logger.info(f"Requesting messages with custom service, query: '{query or 'ALL'}'")
        # Fetch message references with pagination
        while len(all_message_refs) < max_results:
            remaining = max_results - len(all_message_refs)
            page_size = min(500, remaining)

            list_resp = service.users().messages().list(
                userId="me",
                q=query or "",
                maxResults=page_size,
                pageToken=page_token
            ).execute()

            message_refs = list_resp.get("messages", [])
            all_message_refs.extend(message_refs)

            page_token = list_resp.get("nextPageToken")
            if not page_token:
                break

        all_message_refs = all_message_refs[:max_results]

        # Fetch full message details
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

                date_value: Optional[datetime] = None
                if date_str:
                    try:
                        date_value = parsedate_to_datetime(date_str)
                    except Exception:
                        date_value = None

                body = _decode_body(msg.get("payload", {}))

                emails.append(
                    EmailOut(
                        message_id=msg["id"],
                        sender=sender,
                        recipient=recipient,
                        subject=subject,
                        body=body,
                        date=date_value,
                        label_ids=msg.get("labelIds", []),
                    )
                )
            except Exception as e:
                logging.warning(f"Failed to fetch message {ref['id']}: {str(e)}")
                continue

        return emails
    except Exception as e:
        logging.error(f"Error fetching messages with service: {str(e)}")
        return emails


def send_email(sender: str, to: str, subject: str, body: str, service=None) -> dict:
    """
    Send an email via Gmail API.
    `sender` can be "me" or a full email address.
    """
    if service is None:
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
        label_ids=msg.get("labelIds", []),
    )

def fetch_messages_by_label(label_id: str, max_results: int = 25, include_spam_trash: bool = False, user_id: str = "") -> list[EmailOut]:
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

def fetch_drafts(max_results: int = 25, user_id: str = "") -> list[EmailOut]:
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
    Move a message to Trash by adding the TRASH label.

    We *do not* remove INBOX or any other labels. Gmail and your
    list endpoints automatically hide TRASH messages from normal
    views (Inbox, Important, Starred, etc.).
    """
    service = get_gmail_service(user_id=user_id)

    return service.users().messages().modify(
        userId="me",
        id=message_id,
        body={
            "addLabelIds": ["TRASH"],
            "removeLabelIds": []
        }
    ).execute()


def untrash_message(message_id: str, user_id: str = "") -> dict:
    """
    Restore a message from Trash by removing the TRASH label.

    This brings the message back to exactly the labels it had
    before being trashed (INBOX, IMPORTANT, STARRED, custom, etc.
    are all preserved).
    """
    service = get_gmail_service(user_id=user_id)

    return service.users().messages().modify(
        userId="me",
        id=message_id,
        body={
            "addLabelIds": ["INBOX"],
            "removeLabelIds": ["TRASH"]
        }
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


def create_draft(to: str, subject: str, body: str, service=None) -> dict:
    """
    Create a draft email in Gmail (stored with DRAFT label).
    Returns draft object with draft id and message details.
    """
    if service is None:
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


def get_drafts(max_results: int = 25) -> List[dict]:
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


def get_drafts_by_recipient(to_email: str, max_results: int = 25) -> List[dict]:
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


def get_draft_by_id(draft_id: str, service=None) -> Optional[dict]:
    """
    Get a specific draft by ID.
    Returns draft object or None if not found.
    """
    if service is None:
        service = get_gmail_service()

    try:
        draft = service.users().drafts().get(
            userId="me",
            id=draft_id
        ).execute()
        return draft
    except Exception:
        return None


def delete_draft(draft_id: str, service=None) -> bool:
    """
    Delete a draft email by ID.
    Returns True if successful, False otherwise.
    """
    if service is None:
        service = get_gmail_service()

    try:
        service.users().drafts().delete(
            userId="me",
            id=draft_id
        ).execute()
        return True
    except Exception:
        return False


def send_draft(draft_id: str, service=None) -> Optional[dict]:
    """
    Send a draft email and remove it from drafts.
    Returns sent message object or None if failed.
    """
    if service is None:
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
                subject: Optional[str] = None, body: Optional[str] = None, service=None) -> Optional[dict]:
    """
    Update a draft email. Since Gmail API doesn't support partial updates,
    we delete the old draft and create a new one with updated content.

    Args:
        draft_id: ID of the draft to update
        to: New recipient email
        subject: New subject
        body: New body content
        service: Optional Gmail service (for multi-account support)

    Returns: New draft object or None if failed
    """
    if service is None:
        service = get_gmail_service()

    try:
        # Get existing draft to preserve unmodified fields
        existing_draft = get_draft_by_id(draft_id, service=service)
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
    
# ===== LABEL HELPERS =====

def list_labels(user_id: str = "") -> List[dict]:
    """
    List all Gmail labels for the current user.
    We'll filter to 'user' labels in the FastAPI layer.
    """
    service = get_gmail_service(user_id=user_id)
    resp = service.users().labels().list(userId="me").execute()
    return resp.get("labels", [])


def create_label(name: str, user_id: str = "") -> dict:
    """
    Create a new Gmail label with default visibility.
    """
    service = get_gmail_service(user_id=user_id)

    body = {
        "name": name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    }

    created = service.users().labels().create(
        userId="me",
        body=body,
    ).execute()

    return created


def delete_label(label_id: str, user_id: str = "") -> None:
    """
    Delete a Gmail label by id.
    System labels (INBOX, SENT, etc.) cannot be deleted and
    will raise an error.
    """
    service = get_gmail_service(user_id=user_id)
    service.users().labels().delete(userId="me", id=label_id).execute()


def modify_message_labels(
    message_id: str,
    add_label_ids: List[str] | None = None,
    remove_label_ids: List[str] | None = None,
    user_id: str = "",
) -> dict:
    """
    Add/remove labels on a specific message.
    Used by /emails/{message_id}/labels.
    """
    service = get_gmail_service(user_id=user_id)

    body = {
        "addLabelIds": add_label_ids or [],
        "removeLabelIds": remove_label_ids or [],
    }

    resp = service.users().messages().modify(
        userId="me",
        id=message_id,
        body=body,
    ).execute()

    return resp


def revoke_gmail_token(token_path: str = "token.json") -> bool:
    """
    Revoke Gmail OAuth token with Google API and delete the token file.

    This function:
    1. Checks if token file exists
    2. Loads credentials from the token
    3. Calls Google's revocation endpoint to invalidate the token
    4. Deletes the token file from disk
    5. Handles errors gracefully (always tries to delete file)

    Args:
        token_path: Path to the token.json file to revoke (default: "token.json")

    Returns:
        True if revocation succeeded or file didn't exist, False if revocation failed
    """
    import requests

    # If token doesn't exist, nothing to revoke
    if not os.path.exists(token_path):
        logger.info(f"Token file {token_path} does not exist, nothing to revoke")
        return True

    try:
        # Load credentials from token file
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        # Revoke the token with Google's OAuth2 revocation endpoint
        revoke_url = "https://oauth2.googleapis.com/revoke"

        # Use access token if available, otherwise use refresh token
        token_to_revoke = creds.token if creds.token else creds.refresh_token

        if token_to_revoke:
            logger.info(f"Revoking token for {token_path}")
            response = requests.post(
                revoke_url,
                params={'token': token_to_revoke},
                headers={'content-type': 'application/x-www-form-urlencoded'}
            )

            if response.status_code == 200:
                logger.info(f"Successfully revoked token for {token_path}")
            else:
                logger.warning(
                    f"Token revocation returned status {response.status_code}. "
                    f"Continuing with file deletion."
                )
                # Continue with file deletion even if revocation failed
        else:
            logger.warning(f"No token found in {token_path} to revoke")

        # Delete the token file from disk
        os.remove(token_path)
        logger.info(f"Deleted token file: {token_path}")
        return True

    except Exception as e:
        logger.error(f"Error revoking token {token_path}: {str(e)}")

        # Even if revocation failed, try to delete the file
        try:
            if os.path.exists(token_path):
                os.remove(token_path)
                logger.info(f"Deleted token file despite revocation error: {token_path}")
        except Exception as delete_error:
            logger.error(f"Could not delete token file: {str(delete_error)}")

        return False


# ============ MULTI-ACCOUNT SUPPORT FUNCTIONS ============


async def fetch_messages_multi_account(
    user_id: str,
    query: str,
    max_per_account: int = 25
) -> List[EmailOut]:
    """
    Fetch messages from all connected accounts and merge them.
    Used for implementing unified views across multiple Gmail accounts.
    """
    from gmail_account_service import gmail_account_service

    accounts = await gmail_account_service.get_all_accounts(user_id)
    if not accounts:
        return []

    all_emails = []
    for account in accounts:
        try:
            service = await get_user_gmail_service(user_id, account["id"])
            emails = fetch_messages_with_service(service, query, max_per_account)

            # Add account metadata to each email
            for email in emails:
                email.account_id = account["id"]
                email.account_email = account["email_address"]

            all_emails.extend(emails)
        except Exception as e:
            logger.error(f"Failed to fetch from account {account['id']}: {e}")
            # Continue with other accounts even if one fails
            continue

    # Sort by date (newest first) with timezone normalization
    from datetime import datetime as dt_class, timezone

    def normalize_date(date_obj):
        """Convert any datetime to timezone-aware UTC for comparison."""
        if date_obj is None:
            return dt_class.min.replace(tzinfo=timezone.utc)
        if date_obj.tzinfo is None:
            # Assume UTC if no timezone info
            return date_obj.replace(tzinfo=timezone.utc)
        # Convert to UTC
        return date_obj.astimezone(timezone.utc)

    all_emails.sort(key=lambda x: normalize_date(x.date), reverse=True)
    return all_emails


async def fetch_messages_by_label_multi(
    user_id: str,
    label_id: str,
    max_per_account: int = 25,
    include_spam_trash: bool = False
) -> List[EmailOut]:
    """
    Fetch messages by label from all connected accounts.
    """
    query = f"label:{label_id}"
    return await fetch_messages_multi_account(user_id, query, max_per_account)


async def fetch_drafts_multi(user_id: str, max_per_account: int = 25) -> List[EmailOut]:
    """
    Fetch draft emails from all connected accounts.
    """
    query = "label:DRAFT"
    return await fetch_messages_multi_account(user_id, query, max_per_account)


async def modify_message_multi_account(
    user_id: str,
    message_id: str,
    modify_func
) -> Dict:
    """
    Try to modify a message across all accounts until one succeeds.
    Message IDs are unique per account, so only one will match.
    """
    from gmail_account_service import gmail_account_service

    accounts = await gmail_account_service.get_all_accounts(user_id)
    if not accounts:
        raise Exception("No Gmail accounts connected")

    last_error = None
    for account in accounts:
        try:
            service = await get_user_gmail_service(user_id, account["id"])
            result = modify_func(service, message_id)
            logger.info(f"Successfully modified message {message_id} in account {account['email_address']}")
            return result
        except Exception as e:
            last_error = e
            # Try next account
            continue

    # If we get here, message wasn't found in any account
    raise Exception(f"Message {message_id} not found in any account: {last_error}")


async def trash_message_multi(user_id: str, message_id: str) -> Dict:
    """
    Move message to trash in whichever account it belongs to.
    """
    def trash_func(service, msg_id):
        return service.users().messages().trash(userId="me", id=msg_id).execute()

    return await modify_message_multi_account(user_id, message_id, trash_func)


async def untrash_message_multi(user_id: str, message_id: str) -> Dict:
    """
    Restore message from trash in whichever account it belongs to.
    """
    def untrash_func(service, msg_id):
        return service.users().messages().untrash(userId="me", id=msg_id).execute()

    return await modify_message_multi_account(user_id, message_id, untrash_func)


async def set_star_multi(user_id: str, message_id: str, starred: bool) -> Dict:
    """
    Star or unstar a message in whichever account it belongs to.
    """
    def star_func(service, msg_id):
        body = {
            "addLabelIds": ["STARRED"] if starred else [],
            "removeLabelIds": [] if starred else ["STARRED"]
        }
        return service.users().messages().modify(userId="me", id=msg_id, body=body).execute()

    return await modify_message_multi_account(user_id, message_id, star_func)


async def modify_message_labels_multi(
    user_id: str,
    message_id: str,
    add_label_ids: List[str] = None,
    remove_label_ids: List[str] = None
) -> Dict:
    """
    Modify message labels in whichever account it belongs to.
    """
    def modify_func(service, msg_id):
        body = {
            "addLabelIds": add_label_ids or [],
            "removeLabelIds": remove_label_ids or []
        }
        return service.users().messages().modify(userId="me", id=msg_id, body=body).execute()

    return await modify_message_multi_account(user_id, message_id, modify_func)


async def get_primary_account_service(user_id: str):
    """
    Get Gmail service for the primary account (or first account as fallback).
    Used for label operations which are per-account.
    """
    from gmail_account_service import gmail_account_service

    accounts = await gmail_account_service.get_all_accounts(user_id)
    if not accounts:
        raise Exception("No Gmail accounts connected")

    # Find primary account, or use first as fallback
    primary = next((acc for acc in accounts if acc.get("is_primary")), accounts[0])
    return await get_user_gmail_service(user_id, primary["id"])


async def list_labels_multi(user_id: str) -> List[Dict]:
    """
    List labels from the primary account.
    """
    service = await get_primary_account_service(user_id)
    resp = service.users().labels().list(userId="me").execute()
    return resp.get("labels", [])


async def create_label_multi(user_id: str, name: str) -> Dict:
    """
    Create a label in the primary account.
    """
    service = await get_primary_account_service(user_id)
    body = {"name": name}
    return service.users().labels().create(userId="me", body=body).execute()


async def delete_label_multi(user_id: str, label_id: str) -> None:
    """
    Delete a label from the primary account.
    """
    service = await get_primary_account_service(user_id)
    service.users().labels().delete(userId="me", id=label_id).execute()
