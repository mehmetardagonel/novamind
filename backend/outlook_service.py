"""
Outlook Service - Microsoft Graph API Integration

Uses MSAL for OAuth authentication and Microsoft Graph API for email operations.
Supports reading, sending, and managing Outlook emails.
"""

import os
import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone

import msal
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Microsoft OAuth Configuration
OUTLOOK_CLIENT_ID = os.getenv("OUTLOOK_CLIENT_ID") or os.getenv("OUTLOOK_APP_ID")
OUTLOOK_CLIENT_SECRET = os.getenv("OUTLOOK_CLIENT_SECRET")
OUTLOOK_TENANT_ID = os.getenv("OUTLOOK_TENANT_ID", "common")  # 'common' for multi-tenant
OUTLOOK_REDIRECT_URI = os.getenv("OUTLOOK_REDIRECT_URI", "http://localhost:8001/auth/outlook/callback")

# Microsoft Graph API endpoints
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
AUTHORITY = f"https://login.microsoftonline.com/{OUTLOOK_TENANT_ID}"

# Required delegated OAuth scopes for email operations.
# MSAL treats `offline_access` / `openid` / `profile` as reserved and will reject them
# if explicitly included; MSAL/Microsoft Identity will handle refresh-token behavior.
OUTLOOK_SCOPES = [
    "Mail.Read",
    "Mail.ReadWrite",
    "Mail.Send",
    "User.Read",
]

# MSAL client configuration
MSAL_CLIENT_CONFIG = {
    "client_id": OUTLOOK_CLIENT_ID,
    "client_credential": OUTLOOK_CLIENT_SECRET,
    "authority": AUTHORITY,
}


def get_msal_app() -> msal.ConfidentialClientApplication:
    """Get MSAL application instance for token management."""
    return msal.ConfidentialClientApplication(
        OUTLOOK_CLIENT_ID,
        authority=AUTHORITY,
        client_credential=OUTLOOK_CLIENT_SECRET,
    )


def get_auth_url(state: Optional[str] = None) -> str:
    """
    Generate OAuth authorization URL for Outlook login.

    Args:
        state: Optional state parameter (e.g., user_id) for callback

    Returns:
        Authorization URL to redirect user to
    """
    app = get_msal_app()
    auth_url = app.get_authorization_request_url(
        scopes=OUTLOOK_SCOPES,
        redirect_uri=OUTLOOK_REDIRECT_URI,
        state=state,
    )
    return auth_url


def exchange_code_for_token(code: str) -> Dict[str, Any]:
    """
    Exchange authorization code for access token.

    Args:
        code: Authorization code from OAuth callback

    Returns:
        Token response containing access_token, refresh_token, etc.
    """
    app = get_msal_app()
    result = app.acquire_token_by_authorization_code(
        code,
        scopes=OUTLOOK_SCOPES,
        redirect_uri=OUTLOOK_REDIRECT_URI,
    )

    if "error" in result:
        logger.error(f"Token exchange error: {result.get('error_description')}")
        raise Exception(result.get("error_description", "Token exchange failed"))

    return result


def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """
    Refresh an expired access token.

    Args:
        refresh_token: The refresh token from previous authentication

    Returns:
        New token response
    """
    app = get_msal_app()
    result = app.acquire_token_by_refresh_token(
        refresh_token,
        scopes=OUTLOOK_SCOPES,
    )

    if "error" in result:
        logger.error(f"Token refresh error: {result.get('error_description')}")
        raise Exception(result.get("error_description", "Token refresh failed"))

    return result


def _make_graph_request(
    access_token: str,
    endpoint: str,
    method: str = "GET",
    data: Optional[Dict] = None
) -> Dict:
    """
    Make authenticated request to Microsoft Graph API.

    Args:
        access_token: OAuth access token
        endpoint: API endpoint (relative to GRAPH_API_BASE)
        method: HTTP method (GET, POST, PATCH, DELETE)
        data: Request body for POST/PATCH

    Returns:
        API response as dictionary
    """
    url = f"{GRAPH_API_BASE}{endpoint}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            if data is None:
                response = requests.post(url, headers=headers)
            else:
                response = requests.post(url, headers=headers, json=data)
        elif method == "PATCH":
            if data is None:
                response = requests.patch(url, headers=headers)
            else:
                response = requests.patch(url, headers=headers, json=data)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()

        # DELETE returns no content
        if method == "DELETE":
            return {"success": True}

        # Some Graph endpoints (e.g., sendMail, PATCH updates) return 202/204 with no body.
        if not response.content:
            return {"success": True}

        try:
            return response.json()
        except ValueError:
            return {"success": True}

    except requests.exceptions.HTTPError as e:
        logger.error(f"Graph API error: {e.response.status_code} - {e.response.text}")
        raise Exception(f"Microsoft Graph API error: {e.response.status_code}")


def get_user_profile(access_token: str) -> Dict:
    """
    Get current user's profile information.

    Args:
        access_token: OAuth access token

    Returns:
        User profile with email, displayName, etc.
    """
    return _make_graph_request(access_token, "/me")


def get_user_email(access_token: str) -> str:
    """
    Get current user's email address.

    Args:
        access_token: OAuth access token

    Returns:
        User's email address
    """
    profile = get_user_profile(access_token)
    return profile.get("mail") or profile.get("userPrincipalName", "")


def _parse_outlook_message(msg: Dict) -> Dict:
    """
    Parse Outlook message into standardized format.

    Args:
        msg: Raw message from Graph API

    Returns:
        Standardized email dictionary
    """
    # Parse date
    received_datetime = msg.get("receivedDateTime", "")
    try:
        date_obj = datetime.fromisoformat(received_datetime.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        date_obj = datetime.now(timezone.utc)

    # Get sender info
    sender_obj = msg.get("from", {}).get("emailAddress", {})
    sender_name = sender_obj.get("name", "")
    sender_email = sender_obj.get("address", "")
    sender = f"{sender_name} <{sender_email}>" if sender_name else sender_email

    # Get recipient info
    to_recipients = msg.get("toRecipients", [])
    recipient = ""
    if to_recipients:
        recip_obj = to_recipients[0].get("emailAddress", {})
        recipient = recip_obj.get("address", "")

    # Get body (prefer text, fallback to html)
    body_obj = msg.get("body", {})
    body = body_obj.get("content", "")
    if body_obj.get("contentType") == "html":
        # Simple HTML stripping (for preview)
        import re
        body = re.sub(r'<[^>]+>', '', body)
    body = (body or "")[:3000]

    # Map importance
    importance = msg.get("importance", "normal")
    is_important = importance == "high"

    # Get label IDs (categories in Outlook)
    categories = msg.get("categories", [])
    label_ids = categories + (["STARRED"] if msg.get("flag", {}).get("flagStatus") == "flagged" else [])

    return {
        "message_id": msg.get("id", ""),
        "sender": sender,
        "recipient": recipient,
        "subject": msg.get("subject", "(No Subject)"),
        "body": body,
        "snippet": msg.get("bodyPreview", "")[:200],
        "date": date_obj,
        "is_read": msg.get("isRead", False),
        "is_important": is_important,
        "label_ids": label_ids,
        "provider": "outlook",
    }


async def fetch_messages(
    access_token: str,
    folder: str = "inbox",
    query: Optional[str] = None,
    max_results: int = 25,
) -> List[Dict]:
    """
    Fetch emails from Outlook using Graph API.

    Args:
        access_token: OAuth access token
        folder: Mail folder (inbox, sentitems, drafts, deleteditems, junkemail)
        query: OData filter query
        max_results: Maximum number of emails to fetch

    Returns:
        List of parsed email dictionaries
    """
    # Build endpoint with query parameters
    endpoint = f"/me/mailFolders/{folder}/messages"
    params = [
        f"$top={max_results}",
        "$orderby=receivedDateTime desc",
        "$select=id,subject,bodyPreview,body,from,toRecipients,receivedDateTime,isRead,importance,categories,flag",
    ]

    if query:
        params.append(f"$filter={query}")

    endpoint += "?" + "&".join(params)

    try:
        response = _make_graph_request(access_token, endpoint)
        messages = response.get("value", [])

        return [_parse_outlook_message(msg) for msg in messages]

    except Exception as e:
        logger.error(f"Error fetching Outlook messages: {e}")
        return []


async def fetch_inbox(access_token: str, max_results: int = 25) -> List[Dict]:
    """Fetch inbox messages."""
    return await fetch_messages(access_token, "inbox", max_results=max_results)


async def fetch_sent(access_token: str, max_results: int = 25) -> List[Dict]:
    """Fetch sent messages."""
    return await fetch_messages(access_token, "sentitems", max_results=max_results)


async def fetch_drafts(access_token: str, max_results: int = 25) -> List[Dict]:
    """Fetch draft messages."""
    return await fetch_messages(access_token, "drafts", max_results=max_results)


async def fetch_trash(access_token: str, max_results: int = 25) -> List[Dict]:
    """Fetch deleted messages."""
    return await fetch_messages(access_token, "deleteditems", max_results=max_results)


async def fetch_spam(access_token: str, max_results: int = 25) -> List[Dict]:
    """Fetch junk/spam messages."""
    return await fetch_messages(access_token, "junkemail", max_results=max_results)


async def get_message(access_token: str, message_id: str) -> Optional[Dict]:
    """
    Get a single message by id (includes full body content).
    Returns parsed message dict or None if request fails.
    """
    try:
        endpoint = (
            f"/me/messages/{message_id}"
            "?$select=id,subject,bodyPreview,body,from,toRecipients,receivedDateTime,isRead,importance,categories,flag"
        )
        response = _make_graph_request(access_token, endpoint)
        return _parse_outlook_message(response)
    except Exception as e:
        logger.error(f"Error fetching Outlook message {message_id}: {e}")
        return None


async def send_draft(access_token: str, message_id: str) -> Dict:
    """Send an existing draft message by id."""
    try:
        _make_graph_request(access_token, f"/me/messages/{message_id}/send", method="POST")
        return {"success": True, "id": message_id}
    except Exception as e:
        logger.error(f"Error sending Outlook draft {message_id}: {e}")
        return {"success": False, "message": str(e)}


async def delete_message(access_token: str, message_id: str) -> Dict:
    """Delete a message (including drafts) by id."""
    try:
        _make_graph_request(access_token, f"/me/messages/{message_id}", method="DELETE")
        return {"success": True, "id": message_id}
    except Exception as e:
        logger.error(f"Error deleting Outlook message {message_id}: {e}")
        return {"success": False, "message": str(e)}


async def update_message(
    access_token: str,
    message_id: str,
    to: Optional[str] = None,
    subject: Optional[str] = None,
    body: Optional[str] = None,
    is_html: bool = False,
) -> Dict:
    """Update an existing message (draft) by id."""
    try:
        data: Dict[str, Any] = {}
        if to is not None:
            data["toRecipients"] = (
                [{"emailAddress": {"address": to}}] if to.strip() else []
            )
        if subject is not None:
            data["subject"] = subject
        if body is not None:
            data["body"] = {
                "contentType": "HTML" if is_html else "Text",
                "content": body,
            }

        if not data:
            return {"success": True, "id": message_id}

        _make_graph_request(access_token, f"/me/messages/{message_id}", method="PATCH", data=data)
        return {"success": True, "id": message_id}
    except Exception as e:
        logger.error(f"Error updating Outlook message {message_id}: {e}")
        return {"success": False, "message": str(e)}


async def send_email(
    access_token: str,
    to: str,
    subject: str,
    body: str,
    is_html: bool = False,
) -> Dict:
    """
    Send an email via Outlook.

    Args:
        access_token: OAuth access token
        to: Recipient email address
        subject: Email subject
        body: Email body content
        is_html: Whether body is HTML

    Returns:
        Success status dictionary
    """
    message = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML" if is_html else "Text",
                "content": body,
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": to,
                    }
                }
            ],
        },
        "saveToSentItems": True,
    }

    try:
        _make_graph_request(access_token, "/me/sendMail", method="POST", data=message)
        logger.info(f"Email sent to {to}")
        return {"success": True, "message": "Email sent successfully"}

    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return {"success": False, "message": str(e)}


async def create_draft(
    access_token: str,
    to: str,
    subject: str,
    body: str,
    is_html: bool = False,
) -> Dict:
    """
    Create a draft email.

    Args:
        access_token: OAuth access token
        to: Recipient email address
        subject: Email subject
        body: Email body content
        is_html: Whether body is HTML

    Returns:
        Created draft details
    """
    message = {
        "subject": subject,
        "body": {
            "contentType": "HTML" if is_html else "Text",
            "content": body,
        },
        "toRecipients": [
            {
                "emailAddress": {
                    "address": to,
                }
            }
        ] if to else [],
    }

    try:
        result = _make_graph_request(access_token, "/me/messages", method="POST", data=message)
        logger.info(f"Draft created: {result.get('id')}")
        return {"success": True, "draft": _parse_outlook_message(result)}

    except Exception as e:
        logger.error(f"Error creating draft: {e}")
        return {"success": False, "message": str(e)}


async def move_to_trash(access_token: str, message_id: str) -> Dict:
    """
    Move a message to trash.

    Args:
        access_token: OAuth access token
        message_id: Message ID to delete

    Returns:
        Success status
    """
    try:
        # Move to deleted items folder
        data = {"destinationId": "deleteditems"}
        _make_graph_request(
            access_token,
            f"/me/messages/{message_id}/move",
            method="POST",
            data=data
        )
        return {"success": True, "id": message_id}

    except Exception as e:
        logger.error(f"Error moving message to trash: {e}")
        return {"success": False, "message": str(e)}


async def restore_from_trash(access_token: str, message_id: str) -> Dict:
    """
    Restore a message from trash to inbox.

    Args:
        access_token: OAuth access token
        message_id: Message ID to restore

    Returns:
        Success status
    """
    try:
        data = {"destinationId": "inbox"}
        _make_graph_request(
            access_token,
            f"/me/messages/{message_id}/move",
            method="POST",
            data=data
        )
        return {"success": True, "id": message_id}

    except Exception as e:
        logger.error(f"Error restoring message: {e}")
        return {"success": False, "message": str(e)}


async def toggle_flag(access_token: str, message_id: str, flagged: bool) -> Dict:
    """
    Toggle flag (star) on a message.

    Args:
        access_token: OAuth access token
        message_id: Message ID
        flagged: True to flag, False to unflag

    Returns:
        Success status
    """
    try:
        data = {
            "flag": {
                "flagStatus": "flagged" if flagged else "notFlagged"
            }
        }
        _make_graph_request(
            access_token,
            f"/me/messages/{message_id}",
            method="PATCH",
            data=data
        )
        return {"success": True, "id": message_id}

    except Exception as e:
        logger.error(f"Error toggling flag: {e}")
        return {"success": False, "message": str(e)}


async def mark_as_read(access_token: str, message_id: str, is_read: bool = True) -> Dict:
    """
    Mark a message as read or unread.

    Args:
        access_token: OAuth access token
        message_id: Message ID
        is_read: True for read, False for unread

    Returns:
        Success status
    """
    try:
        data = {"isRead": is_read}
        _make_graph_request(
            access_token,
            f"/me/messages/{message_id}",
            method="PATCH",
            data=data
        )
        return {"success": True, "id": message_id}

    except Exception as e:
        logger.error(f"Error marking message: {e}")
        return {"success": False, "message": str(e)}


async def get_folders(access_token: str) -> List[Dict]:
    """
    Get all mail folders.

    Args:
        access_token: OAuth access token

    Returns:
        List of folder dictionaries
    """
    try:
        response = _make_graph_request(access_token, "/me/mailFolders")
        folders = response.get("value", [])

        return [
            {
                "id": f.get("id"),
                "name": f.get("displayName"),
                "type": "system" if f.get("displayName") in ["Inbox", "Sent Items", "Drafts", "Deleted Items", "Junk Email"] else "user",
                "unread_count": f.get("unreadItemCount", 0),
                "total_count": f.get("totalItemCount", 0),
            }
            for f in folders
        ]

    except Exception as e:
        logger.error(f"Error fetching folders: {e}")
        return []


# Singleton service class
class OutlookService:
    """Outlook email service wrapper."""

    def __init__(self):
        self._configured = bool(OUTLOOK_CLIENT_ID and OUTLOOK_CLIENT_SECRET)

    @property
    def is_configured(self) -> bool:
        """Check if Outlook integration is configured."""
        return self._configured

    def get_auth_url(self, state: Optional[str] = None) -> str:
        """Get OAuth authorization URL."""
        if not self.is_configured:
            raise Exception("Outlook integration not configured")
        return get_auth_url(state)

    def exchange_code(self, code: str) -> Dict:
        """Exchange auth code for tokens."""
        return exchange_code_for_token(code)

    def refresh_token(self, refresh_token: str) -> Dict:
        """Refresh access token."""
        return refresh_access_token(refresh_token)

    def get_user_email(self, access_token: str) -> str:
        """Get user's email address."""
        return get_user_email(access_token)

    async def fetch_inbox(self, access_token: str, max_results: int = 25) -> List[Dict]:
        """Fetch inbox messages."""
        return await fetch_inbox(access_token, max_results)

    async def fetch_sent(self, access_token: str, max_results: int = 25) -> List[Dict]:
        """Fetch sent messages."""
        return await fetch_sent(access_token, max_results)

    async def fetch_drafts(self, access_token: str, max_results: int = 25) -> List[Dict]:
        """Fetch drafts."""
        return await fetch_drafts(access_token, max_results)

    async def fetch_trash(self, access_token: str, max_results: int = 25) -> List[Dict]:
        """Fetch trash."""
        return await fetch_trash(access_token, max_results)

    async def fetch_spam(self, access_token: str, max_results: int = 25) -> List[Dict]:
        """Fetch spam/junk."""
        return await fetch_spam(access_token, max_results)

    async def send(self, access_token: str, to: str, subject: str, body: str) -> Dict:
        """Send email."""
        return await send_email(access_token, to, subject, body)

    async def create_draft(self, access_token: str, to: str, subject: str, body: str) -> Dict:
        """Create draft."""
        return await create_draft(access_token, to, subject, body)

    async def get_message(self, access_token: str, message_id: str) -> Optional[Dict]:
        """Get a message (includes full body)."""
        return await get_message(access_token, message_id)

    async def send_draft(self, access_token: str, message_id: str) -> Dict:
        """Send an existing draft by id."""
        return await send_draft(access_token, message_id)

    async def delete_message(self, access_token: str, message_id: str) -> Dict:
        """Delete a message by id."""
        return await delete_message(access_token, message_id)

    async def update_message(
        self,
        access_token: str,
        message_id: str,
        to: Optional[str] = None,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        is_html: bool = False,
    ) -> Dict:
        """Update a message (draft) by id."""
        return await update_message(access_token, message_id, to=to, subject=subject, body=body, is_html=is_html)

    async def trash(self, access_token: str, message_id: str) -> Dict:
        """Move to trash."""
        return await move_to_trash(access_token, message_id)

    async def restore(self, access_token: str, message_id: str) -> Dict:
        """Restore from trash."""
        return await restore_from_trash(access_token, message_id)

    async def star(self, access_token: str, message_id: str, starred: bool) -> Dict:
        """Toggle star/flag."""
        return await toggle_flag(access_token, message_id, starred)


# Global instance
outlook_service = OutlookService()
