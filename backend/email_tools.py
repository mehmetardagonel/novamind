"""
Email Tools - Wrapper functions for email operations
These functions support Gmail and Outlook operations for the AI agent.
Legacy mode (no user_id) uses Gmail token.json.
"""

from typing import List, Dict, Optional
import logging
from dotenv import load_dotenv
from models import EmailOut
from gmail_service import (
    fetch_messages,
    send_email as gmail_send_email,
    get_current_user_email,
    create_draft,
    get_drafts as get_gmail_drafts,
    get_draft_by_id as get_gmail_draft_by_id,
    delete_draft as delete_gmail_draft,
    send_draft as send_gmail_draft,
    update_draft as update_gmail_draft,
    get_drafts_by_recipient as get_gmail_drafts_by_recipient,
    delete_all_spam as delete_all_gmail_spam,
    move_mails as move_gmail_mails
)
from filters import EmailFilters
from datetime import timedelta, date, datetime, timezone

load_dotenv()
logger = logging.getLogger(__name__)

# ============ BASIC EMAIL OPERATIONS ============

def list_email_accounts(user_id: str) -> List[Dict]:
    """List all connected email accounts (Gmail + Outlook) for a user."""
    try:
        if not user_id:
            return []

        import asyncio
        from email_account_service import email_account_service

        return asyncio.run(email_account_service.get_all_accounts(user_id))
    except Exception as e:
        logger.error(f"Error listing email accounts: {str(e)}")
        return []


def _get_primary_email_account(user_id: str) -> Optional[Dict]:
    """Return the user's primary email account record (Gmail or Outlook)."""
    try:
        if not user_id:
            return None

        import asyncio
        from email_account_service import email_account_service

        primary = asyncio.run(email_account_service.get_primary_account(user_id))
        if primary:
            return primary

        accounts = asyncio.run(email_account_service.get_all_accounts(user_id))
        return accounts[0] if accounts else None
    except Exception as e:
        logger.error(f"Error getting primary email account: {str(e)}")
        return None


def get_emails(folder: str = "inbox") -> List[Dict]:
    """Get all emails from a specific folder (inbox by default)"""
    try:
        # Gmail API uses labels, not folders. inbox = INBOX label
        query = f'in:{folder}' if folder != 'inbox' else ''
        emails = fetch_messages(query=query)
        return [email.model_dump(mode='json') for email in emails]
    except Exception as e:
        logger.error(f"Error fetching emails: {str(e)}")
        return []


def get_emails_by_date(date_filter: str) -> List[Dict]:
    """
    Get emails filtered by date
    date_filter: 'today', 'yesterday', 'last_week', 'last_month', 'last_3_months'
    """
    try:
        today = date.today()
        if date_filter == 'today':
            since = today
        elif date_filter == 'yesterday':
            since = today - timedelta(days=1)
            today = today - timedelta(days=1)
        elif date_filter == 'last_week':
            since = today - timedelta(days=7)
        elif date_filter == 'last_month':
            since = today - timedelta(days=30)
        elif date_filter == 'last_3_months':
            since = today - timedelta(days=90)
        else:
            since = today

        filters = EmailFilters(since=since)
        query = filters.to_gmail_query()
        emails = fetch_messages(query=query)
        return [email.model_dump(mode='json') for email in emails]
    except Exception as e:
        logger.error(f"Error fetching emails by date: {str(e)}")
        return []


def get_emails_from_sender(sender: str) -> List[Dict]:
    """Get all emails from a specific sender"""
    try:
        filters = EmailFilters(sender=sender)
        query = filters.to_gmail_query()
        emails = fetch_messages(query=query)
        return [email.model_dump(mode='json') for email in emails]
    except Exception as e:
        logger.error(f"Error fetching emails from sender: {str(e)}")
        return []


def send_email(to: str, subject: str, body: str, user_id: str = None) -> Dict:
    """
    Send an email via the user's primary account (Gmail or Outlook).

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body
        user_id: User ID for multi-account support (optional, uses legacy if None)
    """
    try:
        if user_id:
            primary = _get_primary_email_account(user_id)
            if not primary:
                return {"success": False, "message": "No email accounts connected"}

            provider = primary.get("provider")
            account_id = primary.get("id")

            import asyncio
            from email_account_service import email_account_service

            if provider == "outlook":
                access_token = asyncio.run(
                    email_account_service.get_outlook_access_token(user_id, account_id)
                )
                if not access_token:
                    return {"success": False, "message": "Invalid or expired Outlook token"}

                from outlook_service import outlook_service

                result = asyncio.run(outlook_service.send(access_token, to, subject, body))
                result["provider"] = "outlook"
                result["account_id"] = account_id
                return result

            from gmail_service import get_user_gmail_service

            service = asyncio.run(get_user_gmail_service(user_id, account_id))
            profile = service.users().getProfile(userId="me").execute()
            current_user = profile.get("emailAddress", "me")

            result = gmail_send_email(
                sender=current_user or "me",
                to=to,
                subject=subject,
                body=body,
                service=service,
            )
            return {
                "success": True,
                "message": "Email sent successfully",
                "message_id": result.get("id"),
                "provider": "gmail",
                "account_id": account_id,
            }

        # Legacy behavior (token.json)
        current_user = get_current_user_email()
        result = gmail_send_email(
            sender=current_user or "me",
            to=to,
            subject=subject,
            body=body,
            service=None,
        )
        return {
            "success": True,
            "message": "Email sent successfully",
            "message_id": result.get("id"),
            "provider": "gmail",
        }
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to send email: {str(e)}"
        }


def draft_email(to: str = "", subject: str = "", body: str = "", user_id: str = None) -> Dict:
    """
    Create a draft email in the user's primary account (Gmail or Outlook).
    MANDATORY: Recipient email is required. Body content is optional (can be empty for draft editing later).

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body
        user_id: User ID for multi-account support (optional, uses legacy if None)
    """
    try:
        # CRITICAL: Recipient email is MANDATORY for all drafts
        if not to or not to.strip():
            return {
                "success": False,
                "requires_recipient": True,
                "message": "Recipient email address is required to create a draft",
                "hint": "Please provide the email address of who you want to send this to"
            }

        # Basic email format validation (@ and . check)
        # Gmail API will do full validation
        to_stripped = to.strip()
        if "@" not in to_stripped or "." not in to_stripped.split("@")[-1]:
            return {
                "success": False,
                "requires_recipient": True,
                "message": f"Invalid email format: '{to_stripped}'",
                "invalid_email": to_stripped,
                "hint": "Please provide a valid email address (e.g., john@example.com)"
            }

        if user_id:
            primary = _get_primary_email_account(user_id)
            if not primary:
                return {"success": False, "message": "No email accounts connected"}

            provider = primary.get("provider")
            account_id = primary.get("id")

            import asyncio
            from email_account_service import email_account_service

            if provider == "outlook":
                access_token = asyncio.run(
                    email_account_service.get_outlook_access_token(user_id, account_id)
                )
                if not access_token:
                    return {"success": False, "message": "Invalid or expired Outlook token"}

                from outlook_service import outlook_service

                result = asyncio.run(outlook_service.create_draft(access_token, to, subject, body or ""))
                if not result.get("success"):
                    return {
                        "success": False,
                        "message": result.get("message", "Failed to create Outlook draft"),
                    }

                draft_msg = result.get("draft") or {}
                draft_id = draft_msg.get("message_id") or draft_msg.get("id")
                return {
                    "success": True,
                    "message": "Draft created successfully",
                    "draft_id": draft_id,
                    "provider": "outlook",
                    "account_id": account_id,
                    "draft": {
                        "to": to,
                        "subject": subject,
                        "body": (body or "")[:200] + "..." if len(body or "") > 200 else (body or ""),
                    },
                }

            from gmail_service import get_user_gmail_service

            service = asyncio.run(get_user_gmail_service(user_id, account_id))
            draft = create_draft(to=to, subject=subject, body=body or "", service=service)
            draft_id = draft.get("id")
            return {
                "success": True,
                "message": "Draft created successfully",
                "draft_id": draft_id,
                "provider": "gmail",
                "account_id": account_id,
                "draft": {
                    "to": to,
                    "subject": subject,
                    "body": (body or "")[:200] + "..." if len(body or "") > 200 else (body or ""),
                },
            }

        # Legacy behavior (token.json)
        draft = create_draft(to=to, subject=subject, body=body or "", service=None)
        draft_id = draft.get("id")
        return {
            "success": True,
            "message": "Draft created successfully",
            "draft_id": draft_id,
            "provider": "gmail",
            "draft": {
                "to": to,
                "subject": subject,
                "body": (body or "")[:200] + "..." if len(body or "") > 200 else (body or ""),
            },
        }
    except Exception as e:
        logger.error(f"Error creating draft: {str(e)}")
        return {
            "success": False,
            "message": f"Error creating draft: {str(e)}"
        }


def get_drafts(user_id: str = None) -> List[Dict]:
    """Get all draft emails with multi-account support"""
    try:
        if user_id:
            return fetch_mails(folder="drafts", max_results=50, user_id=user_id)

        drafts = fetch_messages(query="label:DRAFT")
        return [draft.model_dump(mode="json") for draft in drafts]
    except Exception as e:
        logger.error(f"Error fetching drafts: {str(e)}")
        return []


def list_draft_previews(user_id: str = None, max_results: int = 25) -> List[Dict]:
    """
    List drafts with their *draft IDs* (required for send/delete/update).
    Uses the Gmail Drafts API.
    """
    try:
        service = None
        if user_id:
            import asyncio
            from gmail_service import get_primary_account_service
            service = asyncio.run(get_primary_account_service(user_id))

        if service is None:
            draft_refs = get_gmail_drafts(max_results=max_results)
        else:
            draft_refs = (
                service.users()
                .drafts()
                .list(userId="me", maxResults=max_results)
                .execute()
                .get("drafts", [])
            )

        results: List[Dict] = []
        for ref in draft_refs:
            draft_id = ref.get("id")
            if not draft_id:
                continue

            d = get_gmail_draft_by_id(draft_id, service=service)
            if not isinstance(d, dict):
                continue

            msg = d.get("message", {}) if isinstance(d.get("message"), dict) else {}
            headers = (msg.get("payload", {}) or {}).get("headers", []) if isinstance(msg, dict) else []

            def _h(name: str) -> str:
                for h in headers:
                    if (h.get("name") or "").lower() == name.lower():
                        return h.get("value") or ""
                return ""

            results.append(
                {
                    "id": draft_id,
                    "to": _h("To"),
                    "subject": _h("Subject") or "(No subject)",
                    "date": _h("Date") or "Unknown",
                }
            )

        return results
    except Exception as e:
        logger.error(f"Error listing draft previews: {str(e)}")
        return []


def get_draft_by_id(draft_id: str, user_id: str = None) -> Optional[Dict]:
    """Get a specific draft by ID from the user's primary account (Gmail or Outlook)."""
    try:
        if user_id:
            primary = _get_primary_email_account(user_id)
            if not primary:
                return None

            provider = primary.get("provider")
            account_id = primary.get("id")

            import asyncio
            from email_account_service import email_account_service

            if provider == "outlook":
                access_token = asyncio.run(
                    email_account_service.get_outlook_access_token(user_id, account_id)
                )
                if not access_token:
                    return None

                from outlook_service import outlook_service

                msg = asyncio.run(outlook_service.get_message(access_token, draft_id))
                return msg

            from gmail_service import get_user_gmail_service

            service = asyncio.run(get_user_gmail_service(user_id, account_id))
            draft = get_gmail_draft_by_id(draft_id, service=service)
            if draft:
                return draft.model_dump(mode="json") if hasattr(draft, "model_dump") else draft
            return None

        draft = get_gmail_draft_by_id(draft_id, service=None)
        if draft:
            return draft.model_dump(mode="json") if hasattr(draft, "model_dump") else draft
        return None
    except Exception as e:
        logger.error(f"Error getting draft: {str(e)}")
        return None


def get_draft_body(draft_id: str, user_id: str = None) -> Optional[str]:
    """Get the full draft body text from the user's primary account (Gmail or Outlook)."""
    try:
        if user_id:
            primary = _get_primary_email_account(user_id)
            if not primary:
                return None

            provider = primary.get("provider")
            account_id = primary.get("id")

            import asyncio
            from email_account_service import email_account_service

            if provider == "outlook":
                access_token = asyncio.run(
                    email_account_service.get_outlook_access_token(user_id, account_id)
                )
                if not access_token:
                    return None

                from outlook_service import outlook_service

                msg = asyncio.run(outlook_service.get_message(access_token, draft_id))
                if isinstance(msg, dict):
                    return (msg.get("body") or "").strip()
                return None

            from gmail_service import _decode_body, get_user_gmail_service

            service = asyncio.run(get_user_gmail_service(user_id, account_id))
            draft = get_gmail_draft_by_id(draft_id, service=service)
            if not isinstance(draft, dict):
                return None

            msg = draft.get("message", {})
            if not isinstance(msg, dict):
                return None

            msg_id = msg.get("id")
            if not msg_id:
                return None

            full_msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
            return (_decode_body(full_msg.get("payload", {})) or "").strip()

        # Legacy behavior (token.json)
        draft = get_gmail_draft_by_id(draft_id, service=None)
        if not isinstance(draft, dict):
            return None

        msg = draft.get("message", {})
        if not isinstance(msg, dict):
            return None

        msg_id = msg.get("id")
        if not msg_id:
            return None

        from gmail_service import _decode_body, get_gmail_service

        service = get_gmail_service()
        full_msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_id, format="full")
            .execute()
        )
        return (_decode_body(full_msg.get("payload", {})) or "").strip()
    except Exception as e:
        logger.error(f"Error getting draft body: {str(e)}")
        return None


def get_drafts_for_recipient(to_email: str, user_id: str = None) -> List[Dict]:
    """
    Get all draft emails for a specific recipient email address with multi-account support.

    Args:
        to_email: The recipient email address to filter drafts by
        user_id: User ID for multi-account support

    Returns:
        List of draft emails for the specified recipient
    """
    try:
        if user_id:
            primary = _get_primary_email_account(user_id)
            if not primary:
                return []

            provider = primary.get("provider")
            account_id = primary.get("id")

            import asyncio
            from email_account_service import email_account_service

            if provider == "outlook":
                access_token = asyncio.run(
                    email_account_service.get_outlook_access_token(user_id, account_id)
                )
                if not access_token:
                    return []

                from outlook_service import fetch_messages as fetch_outlook_messages

                drafts_raw = asyncio.run(
                    fetch_outlook_messages(access_token, folder="drafts", max_results=50)
                )

                results: List[Dict] = []
                for d in drafts_raw:
                    if to_email.lower() not in (d.get("recipient") or "").lower():
                        continue
                    dt_val = d.get("date")
                    date_str = dt_val.isoformat() if isinstance(dt_val, datetime) else "Unknown"
                    results.append(
                        {
                            "id": d.get("message_id", ""),
                            "subject": d.get("subject", "(No subject)"),
                            "date": date_str,
                            "provider": "outlook",
                            "account_id": account_id,
                        }
                    )
                return results

            from gmail_service import get_user_gmail_service

            service = asyncio.run(get_user_gmail_service(user_id, account_id))
            drafts = get_gmail_drafts_by_recipient(to_email, service=service)
        else:
            drafts = get_gmail_drafts_by_recipient(to_email)

        return [draft if isinstance(draft, dict) else draft.model_dump(mode='json')
                for draft in drafts]
    except Exception as e:
        logger.error(f"Error fetching drafts for recipient {to_email}: {str(e)}")
        return []


def delete_draft(draft_id: str, user_id: str = None) -> Dict:
    """Delete a draft email from the user's primary account (Gmail or Outlook)."""
    try:
        if user_id:
            primary = _get_primary_email_account(user_id)
            if not primary:
                return {"success": False, "message": "No email accounts connected"}

            provider = primary.get("provider")
            account_id = primary.get("id")

            import asyncio
            from email_account_service import email_account_service

            if provider == "outlook":
                access_token = asyncio.run(
                    email_account_service.get_outlook_access_token(user_id, account_id)
                )
                if not access_token:
                    return {"success": False, "message": "Invalid or expired Outlook token"}

                from outlook_service import outlook_service

                result = asyncio.run(outlook_service.delete_message(access_token, draft_id))
                return {
                    "success": bool(result.get("success")),
                    "message": (
                        f"Draft {draft_id} deleted successfully"
                        if result.get("success")
                        else result.get("message", f"Failed to delete draft {draft_id}")
                    ),
                }

            from gmail_service import get_user_gmail_service

            service = asyncio.run(get_user_gmail_service(user_id, account_id))
            success = delete_gmail_draft(draft_id, service=service)
            return {
                "success": bool(success),
                "message": (
                    f"Draft {draft_id} deleted successfully"
                    if success
                    else f"Failed to delete draft {draft_id}"
                ),
            }

        success = delete_gmail_draft(draft_id, service=None)
        if success:
            return {
                "success": True,
                "message": f"Draft {draft_id} deleted successfully"
            }
        else:
            return {
                "success": False,
                "message": f"Failed to delete draft {draft_id}"
            }
    except Exception as e:
        logger.error(f"Error deleting draft: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to delete draft: {str(e)}"
        }


def send_draft(draft_id: str, user_id: str = None) -> Dict:
    """Send a previously created draft from the user's primary account (Gmail or Outlook)."""
    try:
        if user_id:
            primary = _get_primary_email_account(user_id)
            if not primary:
                return {"success": False, "message": "No email accounts connected"}

            provider = primary.get("provider")
            account_id = primary.get("id")

            import asyncio
            from email_account_service import email_account_service

            if provider == "outlook":
                access_token = asyncio.run(
                    email_account_service.get_outlook_access_token(user_id, account_id)
                )
                if not access_token:
                    return {"success": False, "message": "Invalid or expired Outlook token"}

                from outlook_service import outlook_service

                result = asyncio.run(outlook_service.send_draft(access_token, draft_id))
                if result.get("success"):
                    return {
                        "success": True,
                        "message": f"Draft {draft_id} sent successfully",
                        "message_id": draft_id,
                        "provider": "outlook",
                        "account_id": account_id,
                    }
                return {
                    "success": False,
                    "message": result.get("message", f"Failed to send draft {draft_id}"),
                    "provider": "outlook",
                    "account_id": account_id,
                }

            from gmail_service import get_user_gmail_service

            service = asyncio.run(get_user_gmail_service(user_id, account_id))
            sent_msg = send_gmail_draft(draft_id, service=service)
            if sent_msg:
                return {
                    "success": True,
                    "message": f"Draft {draft_id} sent successfully",
                    "message_id": sent_msg.get("id"),
                    "provider": "gmail",
                    "account_id": account_id,
                }
            return {"success": False, "message": f"Failed to send draft {draft_id}"}

        sent_msg = send_gmail_draft(draft_id, service=None)
        if sent_msg:
            return {
                "success": True,
                "message": f"Draft {draft_id} sent successfully",
                "message_id": sent_msg.get("id")
            }
        else:
            return {
                "success": False,
                "message": f"Failed to send draft {draft_id}"
            }
    except Exception as e:
        logger.error(f"Error sending draft: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to send draft: {str(e)}"
        }


def search_emails(
    sender: Optional[str] = None,
    date_filter: Optional[str] = None,
    subject_keyword: Optional[str] = None,
    is_important: Optional[bool] = None,
    is_spam: Optional[bool] = None,
    folder: Optional[str] = None
) -> List[Dict]:
    """
    Advanced email search with multiple filters
    All parameters are optional and can be combined
    """
    try:
        filters = EmailFilters(
            sender=sender,
            subject_contains=subject_keyword
        )
        query = filters.to_gmail_query()

        # Add additional filters
        if is_spam:
            query += ' is:spam'
        if is_important:
            query += ' is:important'
        if folder:
            query += f' in:{folder}'

        emails = fetch_messages(query=query)
        return [email.model_dump(mode='json') for email in emails]
    except Exception as e:
        logger.error(f"Error searching emails: {str(e)}")
        return []


def update_draft(
    draft_id: str,
    to: Optional[str] = None,
    subject: Optional[str] = None,
    body: Optional[str] = None,
    append_to_body: Optional[str] = None,
    remove_from_body: Optional[str] = None,
    instruction: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict:
    """
    Update a draft email in the user's primary account (Gmail or Outlook).

    Parameters:
    - draft_id: Required - The draft ID to update
    - to: Update recipient email (None = keep existing, "" = clear)
    - subject: Update subject line (None = keep existing, "" = clear)
    - body: Update body text (None = keep existing, "" = clear)
    - append_to_body: Complete enhanced body from chat_service (used directly, no further enhancement)
    - remove_from_body: (unused, reserved for future)
    - instruction: AI enhancement instruction (treated as body if body is not provided)

    Note: None vs "" are treated differently. Use None to keep existing value, "" to clear it.
    All enhancement should be done in chat_service BEFORE calling this function.
    """
    try:
        if user_id:
            primary = _get_primary_email_account(user_id)
            if not primary:
                return {"success": False, "message": "No email accounts connected"}

            provider = primary.get("provider")
            account_id = primary.get("id")

            import asyncio
            from email_account_service import email_account_service

            # Handle instruction parameter - treat as body if body is not provided
            if instruction is not None and body is None:
                body = instruction

            # Determine which body to use (None = keep existing, "" = clear, string = use it)
            update_body = None
            if append_to_body is not None:
                update_body = append_to_body
            elif body is not None:
                update_body = body

            if provider == "outlook":
                access_token = asyncio.run(
                    email_account_service.get_outlook_access_token(user_id, account_id)
                )
                if not access_token:
                    return {"success": False, "message": "Invalid or expired Outlook token"}

                from outlook_service import outlook_service

                result = asyncio.run(
                    outlook_service.update_message(
                        access_token,
                        draft_id,
                        to=to,
                        subject=subject,
                        body=update_body,
                    )
                )
                if result.get("success"):
                    return {
                        "success": True,
                        "message": f"Draft {draft_id} updated successfully",
                        "new_draft_id": draft_id,
                        "provider": "outlook",
                        "account_id": account_id,
                    }
                return {
                    "success": False,
                    "message": result.get("message", f"Failed to update draft {draft_id}"),
                    "provider": "outlook",
                    "account_id": account_id,
                }

            from gmail_service import get_user_gmail_service

            service = asyncio.run(get_user_gmail_service(user_id, account_id))
        else:
            service = None

        # Handle instruction parameter - treat as body if body is not provided
        if instruction is not None and body is None:
            body = instruction

        # Get the draft to access old body
        draft = get_gmail_draft_by_id(draft_id, service=service)
        if not draft:
            return {
                "success": False,
                "message": f"Draft {draft_id} not found"
            }

        # Determine which body to use (None = keep existing, "" = clear, string = use it)
        # Priority: append_to_body > body > None (keep existing)
        update_body = None

        if append_to_body is not None:
            # append_to_body is already the complete body from chat_service._smart_enhance_append()
            # It's already enhanced and ready to use, don't do further processing
            update_body = append_to_body
        elif body is not None:
            # body parameter: already enhanced by chat_service._smart_enhance_body_with_instruction()
            # Use it as the new body
            update_body = body
        # else: update_body stays None, meaning keep existing body

        # Update the draft with the processed fields
        # If to/subject/body are None, they won't be modified (Gmail API ignores None values)
        updated_draft = update_gmail_draft(
            draft_id=draft_id,
            to=to,  # None = keep existing
            subject=subject,  # None = keep existing
            body=update_body,  # None = keep existing, or enhanced body string
            service=service
        )

        if updated_draft:
            new_draft_id = updated_draft.get("id")
            return {
                "success": True,
                "message": f"Draft {draft_id} updated successfully",
                "new_draft_id": new_draft_id
            }
        else:
            return {
                "success": False,
                "message": f"Failed to update draft {draft_id}"
            }
    except Exception as e:
        logger.error(f"Error updating draft: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to update draft: {str(e)}"
        }


def delete_spam_emails() -> Dict:
    """Delete all spam emails"""
    try:
        deleted_count = delete_all_gmail_spam()
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"Deleted {deleted_count} spam email(s)"
        }
    except Exception as e:
        logger.error(f"Error deleting spam: {str(e)}")
        return {"success": False, "message": str(e)}


def move_email(email_id: str, folder: str) -> Dict:
    """Move a single email to a specific label/folder"""
    try:
        moved_count = move_gmail_mails(email_ids=[email_id], target_label_name=folder)
        if moved_count > 0:
            return {
                "success": True,
                "message": f"Email moved to '{folder}'"
            }
        else:
            return {
                "success": False,
                "message": f"Failed to move email"
            }
    except Exception as e:
        logger.error(f"Error moving email: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to move email: {str(e)}"
        }


def get_important_emails() -> List[Dict]:
    """Get all important emails"""
    try:
        emails = fetch_messages(query='is:important')
        return [email.model_dump(mode='json') for email in emails]
    except Exception as e:
        logger.error(f"Error fetching important emails: {str(e)}")
        return []


# ============ ADVANCED EMAIL TOOLS ============

def fetch_mails(
    label: Optional[str] = None,
    sender: Optional[str] = None,
    importance: Optional[bool] = None,
    time_period: Optional[str] = None,
    since_date: Optional[str] = None,
    until_date: Optional[str] = None,
    subject_keyword: Optional[str] = None,
    folder: Optional[str] = None,
    max_results: int = 50,
    provider: Optional[str] = None,
    account_id: Optional[str] = None,
    user_id: str = None
) -> List[Dict]:
    """
    Advanced email fetching with multiple filter options

    Parameters:
    - label: Custom label (e.g., 'Work', 'Personal')
    - sender: Sender email or name (partial match)
    - importance: Filter by importance (True for important, False for not important)
    - time_period: 'today', 'yesterday', 'last_week', 'last_month', 'last_3_months'
    - since_date: Start date in ISO format (YYYY-MM-DD)
    - until_date: End date in ISO format (YYYY-MM-DD)
    - subject_keyword: Search keyword in subject line
    - folder: Filter by folder (e.g., 'inbox', 'sent', 'drafts')
    - max_results: Maximum number of emails to return (default: 50)
    - account_id: Specific account ID to fetch from
    - user_id: User ID for multi-account support

    All filters are optional and can be combined together.
    """
    try:
        logger.info(f"[FETCH_MAILS] ===== START FETCH =====")
        logger.info(f"[FETCH_MAILS] Parameters:")
        logger.info(f"  label={label}, sender={sender}, importance={importance}")
        logger.info(f"  time_period={time_period}, since_date={since_date}, until_date={until_date}")
        logger.info(f"  subject_keyword={subject_keyword}, folder={folder}")
        logger.info(f"  max_results={max_results}, provider={provider}")
        logger.info(f"  account_id={account_id}, user_id={user_id}")
        provider_normalized = provider.lower().strip() if isinstance(provider, str) and provider.strip() else None
        if provider_normalized and provider_normalized not in {"gmail", "outlook"}:
            return [{"error": f"Invalid provider '{provider}'. Use 'gmail' or 'outlook'."}]

        # If the sender looks like a connected account email, treat it as an account filter.
        if user_id and sender and not account_id and "@" in sender:
            try:
                accounts = list_email_accounts(user_id)
                sender_lower = sender.lower().strip()
                matched = next(
                    (
                        acc
                        for acc in accounts
                        if (acc.get("email_address") or "").lower() == sender_lower
                    ),
                    None,
                )
                if matched:
                    account_id = matched.get("id")
                    sender = None
                    logger.info(
                        f"[FETCH_MAILS] Resolved sender email to account_id={account_id}"
                    )
            except Exception as account_err:
                logger.warning(
                    f"[FETCH_MAILS] Failed to resolve sender to account: {account_err}"
                )

        # Build date filter if time_period is specified
        calculated_since = None
        if time_period:
            today = date.today()
            if time_period == 'today':
                calculated_since = today
            elif time_period == 'yesterday':
                calculated_since = today - timedelta(days=1)
            elif time_period == 'last_week':
                calculated_since = today - timedelta(days=7)
            elif time_period == 'last_month':
                calculated_since = today - timedelta(days=30)
            elif time_period == 'last_3_months':
                calculated_since = today - timedelta(days=90)

        # Parse string dates to date objects with error handling
        parsed_since = None
        parsed_until = None

        try:
            # Handle since_date (string to date conversion)
            if since_date:
                # since_date is ISO format string like "2025-11-01"
                parsed_since = datetime.fromisoformat(since_date).date()
            elif calculated_since:
                # calculated_since is already a date object
                parsed_since = calculated_since

            # Handle until_date (string to date conversion)
            if until_date:
                # until_date is ISO format string like "2025-11-30"
                parsed_until = datetime.fromisoformat(until_date).date()

        except ValueError as e:
            # Invalid date format provided
            logger.error(f"Invalid date format in fetch_mails: {str(e)}")
            return [{
                "error": f"Invalid date format. Please use YYYY-MM-DD format (e.g., 2025-11-01)",
                "details": str(e)
            }]

        filters = EmailFilters(
            sender=sender,
            subject_contains=subject_keyword,
            since=parsed_since,  # Now always a date object or None
            until=parsed_until   # Now always a date object or None
        )

        query = filters.to_gmail_query()

        # Add label filter
        if label:
            query += f' label:{label}'

        # NOTE: We do NOT add 'is:important' to the Gmail query here anymore
        # because we want to filter by ML prediction, not Gmail's importance label.
        # The importance filtering will be done AFTER fetching, based on ml_prediction field.
        # if importance is True:
        #     query += ' is:important'
        # elif importance is False:
        #     query += ' -is:important'

        # Add folder filter
        if folder:
            query += f' in:{folder}'

        def normalize_date(date_obj: Optional[datetime]) -> datetime:
            """Convert any datetime to timezone-aware UTC for sorting."""
            if date_obj is None:
                return datetime.min.replace(tzinfo=timezone.utc)
            if date_obj.tzinfo is None:
                return date_obj.replace(tzinfo=timezone.utc)
            return date_obj.astimezone(timezone.utc)

        def outlook_folder_to_graph(folder_name: Optional[str]) -> str:
            if not folder_name:
                return "inbox"
            f = folder_name.strip().lower()
            mapping = {
                "inbox": "inbox",
                "sent": "sentitems",
                "sentitems": "sentitems",
                "sent_items": "sentitems",
                "drafts": "drafts",
                "trash": "deleteditems",
                "deleted": "deleteditems",
                "deleteditems": "deleteditems",
                "spam": "junkemail",
                "junk": "junkemail",
                "junkemail": "junkemail",
            }
            return mapping.get(f, "inbox")

        def outlook_matches_filters(msg: Dict) -> bool:
            try:
                if sender:
                    if sender.lower() not in (msg.get("sender") or "").lower():
                        return False
                if subject_keyword:
                    if subject_keyword.lower() not in (msg.get("subject") or "").lower():
                        return False
                if label:
                    label_lower = label.lower()
                    label_ids = [str(x).lower() for x in (msg.get("label_ids") or [])]
                    if label_lower not in label_ids:
                        return False

                if parsed_since or parsed_until:
                    dt_val = msg.get("date")
                    if isinstance(dt_val, datetime):
                        d_val = dt_val.date()
                    else:
                        d_val = None

                    if parsed_since and (not d_val or d_val < parsed_since):
                        return False
                    if parsed_until and (not d_val or d_val > parsed_until):
                        return False

                return True
            except Exception:
                return False

        def is_important_email(email: Dict) -> bool:
            if not isinstance(email, dict):
                return False
            if email.get("is_important") is True:
                return True
            prediction = str(email.get("ml_prediction") or "").lower()
            if prediction == "important":
                return True
            labels = email.get("label_ids") or []
            return any(str(label).upper() == "IMPORTANT" for label in labels)

        # Multi-account unified (Gmail + Outlook)
        if user_id:
            import asyncio
            from email_account_service import email_account_service
            from gmail_service import fetch_messages_with_service, get_user_gmail_service
            from outlook_service import fetch_messages as fetch_outlook_messages

            async def fetch_all() -> List[EmailOut]:
                accounts = await email_account_service.get_all_accounts(user_id)
                if not accounts:
                    return []

                if account_id:
                    accounts = [acc for acc in accounts if acc.get("id") == account_id]
                    if not accounts:
                        raise ValueError("Account not found")

                if provider_normalized:
                    accounts = [acc for acc in accounts if acc.get("provider") == provider_normalized]

                all_emails: List[EmailOut] = []
                gmail_query = query or "in:inbox"
                outlook_folder = outlook_folder_to_graph(folder)
                gmail_fetch_limit = max_results
                outlook_fetch_limit = max(1, min(max_results * 3, 100))
                if importance is not None:
                    gmail_fetch_limit = max(1, min(max_results * 3, 100))

                for account in accounts:
                    acc_provider = account.get("provider")
                    if acc_provider == "gmail":
                        service = await get_user_gmail_service(user_id, account["id"])
                        emails = fetch_messages_with_service(
                            service=service,
                            query=gmail_query,
                            max_results=gmail_fetch_limit,
                        )
                        for email in emails:
                            email.account_id = account["id"]
                            email.account_email = account["email_address"]
                            email.provider = "gmail"
                        all_emails.extend(emails)
                        continue

                    if acc_provider == "outlook":
                        access_token = await email_account_service.get_outlook_access_token(user_id, account["id"])
                        if not access_token:
                            logger.warning(
                                f"Skipping Outlook account {account.get('id')}: missing/expired token"
                            )
                            continue

                        outlook_msgs = await fetch_outlook_messages(
                            access_token,
                            folder=outlook_folder,
                            max_results=outlook_fetch_limit,
                        )
                        for msg in outlook_msgs:
                            if not outlook_matches_filters(msg):
                                continue

                            label_ids = list(msg.get("label_ids", []) or [])
                            if not msg.get("is_read", True) and "UNREAD" not in label_ids:
                                label_ids.append("UNREAD")
                            if msg.get("is_important") and "IMPORTANT" not in label_ids:
                                label_ids.append("IMPORTANT")

                            all_emails.append(
                                EmailOut(
                                    message_id=msg.get("message_id", ""),
                                    sender=msg.get("sender", ""),
                                    recipient=msg.get("recipient", ""),
                                    subject=msg.get("subject", ""),
                                    body=msg.get("body", ""),
                                    date=msg.get("date") or datetime.now(timezone.utc),
                                    label_ids=label_ids,
                                    account_id=account["id"],
                                    account_email=account["email_address"],
                                    provider="outlook",
                                )
                            )
                        continue

                    logger.warning(f"Skipping unknown provider '{acc_provider}' for account {account.get('id')}")

                all_emails.sort(key=lambda x: normalize_date(x.date), reverse=True)
                try:
                    max_n = int(max_results) if max_results is not None else 0
                except (TypeError, ValueError):
                    max_n = 0
                if max_n > 0 and importance is None:
                    all_emails = all_emails[:max_n]
                return all_emails

            try:
                emails = asyncio.run(fetch_all())
                logger.info(f"[FETCH_MAILS] Fetched {len(emails)} emails from accounts (BEFORE importance filter)")
                if emails:
                    for i, email in enumerate(emails[:3]):
                        logger.info(f"[FETCH_MAILS] Email {i+1}: sender={email.sender}, subject={email.subject[:50]}, account_email={email.account_email}, provider={email.provider}, label_ids={email.label_ids}")
            except ValueError:
                logger.error(f"[FETCH_MAILS] Account not found error")
                return [{"error": "Account not found"}]

            # Convert to dicts for filtering
            result = [email.model_dump(mode="json") for email in emails]

            # Ensure ML predictions exist when importance filtering is requested.
            if importance is not None and any(email.get("ml_prediction") is None for email in result):
                try:
                    from ml_service import get_classifier

                    classifier = get_classifier()
                    result = classifier.classify_batch(result)
                except Exception as ml_error:
                    logger.warning(
                        f"[FETCH_MAILS] ML classification skipped/failed: {ml_error}"
                    )

            # Promote ML-important emails into label_ids for consistent downstream filtering.
            for email in result:
                try:
                    prediction = str(email.get("ml_prediction") or "").lower()
                    if prediction == "important":
                        labels = list(email.get("label_ids") or [])
                        if not any(str(label).upper() == "IMPORTANT" for label in labels):
                            labels.append("IMPORTANT")
                            email["label_ids"] = labels
                except Exception:
                    continue

            # CRITICAL: Apply ML-based importance filtering AFTER fetching
            # This is because we classify emails with ML, but we also honor provider "IMPORTANT" labels.
            if importance is True:
                logger.info(
                    "[FETCH_MAILS] Filtering for important emails (ml_prediction or IMPORTANT label)"
                )
                result = [email for email in result if is_important_email(email)]
                logger.info(f"[FETCH_MAILS] After importance filter: {len(result)} emails")
            elif importance is False:
                logger.info(
                    "[FETCH_MAILS] Filtering for non-important emails (not ml_prediction/IMPORTANT)"
                )
                result = [email for email in result if not is_important_email(email)]
                logger.info(f"[FETCH_MAILS] After importance filter: {len(result)} emails")

            try:
                max_n = int(max_results) if max_results is not None else 0
            except (TypeError, ValueError):
                max_n = 0
            if max_n > 0:
                result = result[:max_n]

            logger.info(f"[FETCH_MAILS] Returning {len(result)} emails")
            return result

        # Legacy single-account Gmail (token.json)
        emails = fetch_messages(query=query or None, max_results=max_results)
        return [email.model_dump(mode="json") for email in emails]
    except Exception as e:
        logger.error(f"Error in fetch_mails: {str(e)}")
        return []


def delete_all_spam(user_id: str = None) -> Dict:
    """
    Delete all spam emails from Gmail (query: is:spam) with multi-account support.
    Returns the count of deleted spam emails.
    """
    try:
        if user_id:
            import asyncio
            from gmail_service import get_primary_account_service
            service = asyncio.run(get_primary_account_service(user_id))
            deleted_count = delete_all_gmail_spam(service=service)
        else:
            deleted_count = delete_all_gmail_spam()

        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"Successfully deleted {deleted_count} spam email(s)"
        }
    except Exception as e:
        logger.error(f"Error deleting spam: {str(e)}")
        return {
            "success": False,
            "deleted_count": 0,
            "message": f"Failed to delete spam: {str(e)}"
        }


def move_mails_by_sender(sender: str, target_folder: str, max_results: int = 50, user_id: str = None) -> Dict:
    """
    Move multiple emails from a specific sender to a target folder with multi-account support.

    Parameters:
    - sender: Sender name or email (partial match, case-insensitive)
      Examples: 'playstation', 'amazon', 'john', 'company.com'
    - target_folder: Target label/folder name
      Examples: 'game', 'shopping', 'work'
    - max_results: Maximum emails to fetch and move (default: 50)
    - user_id: User ID for multi-account support

    Returns: Dict with success status and count of moved emails
    """
    try:
        # Find all emails from this sender
        emails = fetch_mails(sender=sender, max_results=max_results, provider="gmail", user_id=user_id)

        if not emails:
            return {
                "success": False,
                "moved_count": 0,
                "message": f"No emails found from sender '{sender}'"
            }

        # Extract email IDs from results
        email_ids = [
            email.get("message_id") or email.get("id")
            for email in emails
            if (email.get("message_id") or email.get("id"))
        ]

        if not email_ids:
            return {
                "success": False,
                "moved_count": 0,
                "message": f"Could not extract email IDs from {len(emails)} emails"
            }

        # Get service for multi-account
        if user_id:
            import asyncio
            from gmail_service import get_primary_account_service
            service = asyncio.run(get_primary_account_service(user_id))
            moved_count = move_gmail_mails(email_ids=email_ids, target_label_name=target_folder, service=service)
        else:
            # Move the emails using the internal function
            moved_count = move_gmail_mails(email_ids=email_ids, target_label_name=target_folder)

        return {
            "success": moved_count > 0,
            "moved_count": moved_count,
            "message": f"Moved {moved_count} email(s) from '{sender}' to '{target_folder}'"
        }

    except Exception as e:
        logger.error(f"Error moving mails by sender: {str(e)}")
        return {
            "success": False,
            "moved_count": 0,
            "message": f"Failed to move emails: {str(e)}"
        }


def query_emails(query: str, user_id: str = None) -> Dict:
    """
    Query emails using natural language.

    This function intelligently searches emails based on natural language queries like:
    - "what did I receive from Google jobs"
    - "is there anything important from Google jobs"
    - "do I have any meetings tomorrow"
    - "show me emails about project updates from last week"

    It uses semantic search (RAG) if enabled, otherwise falls back to intelligent filtering.

    Parameters:
    - query: Natural language query string
    - user_id: User ID for multi-account support

    Returns: Dict with emails and insights
    """
    try:
        import asyncio
        from rag_service import rag_service, EMAIL_EMBEDDINGS_ENABLED

        logger.info(f"[QUERY_EMAILS] ===== START QUERY =====")
        logger.info(f"[QUERY_EMAILS] Query: '{query}'")
        logger.info(f"[QUERY_EMAILS] User ID: {user_id}")

        # Try RAG semantic search first if enabled
        if EMAIL_EMBEDDINGS_ENABLED and user_id:
            logger.info("Using RAG semantic search for query")
            relevant_emails = asyncio.run(rag_service.search(user_id, query, limit=10))

            if relevant_emails:
                # Format RAG results
                formatted_emails = []
                for email in relevant_emails:
                    metadata = email.get('metadata', {})
                    formatted_emails.append({
                        'from': metadata.get('from', 'Unknown'),
                        'subject': metadata.get('subject', 'No subject'),
                        'date': metadata.get('date', 'Unknown'),
                        'content': email.get('content', '')[:500],
                        'relevance': email.get('similarity', 0),
                        'account_id': metadata.get('account_id'),
                        'provider': metadata.get('provider', 'gmail')
                    })

                return {
                    "success": True,
                    "method": "semantic_search",
                    "query": query,
                    "count": len(formatted_emails),
                    "emails": formatted_emails,
                    "insights": _generate_insights(formatted_emails, query)
                }

        # Fallback: Intelligent filtering based on query keywords
        logger.info("[QUERY_EMAILS] Using intelligent filtering for query")
        filters = _extract_filters_from_query(query)
        logger.info(f"[QUERY_EMAILS] Extracted filters: {filters}")

        # Check if user_id is provided and resolve account_email to account_id
        account_id_filter = filters.get('account_id')
        account_email_filter = filters.get('account_email')

        if user_id:
            logger.info(f"[QUERY_EMAILS] Fetching all accounts for user {user_id}")
            accounts = list_email_accounts(user_id)
            logger.info(f"[QUERY_EMAILS] Found {len(accounts)} accounts: {[acc.get('email_address') for acc in accounts]}")

            # If account_email is provided, resolve it to account_id
            if account_email_filter and not account_id_filter:
                logger.info(f"[QUERY_EMAILS] Resolving account_email '{account_email_filter}' to account_id")
                matching_account = None
                for acc in accounts:
                    if acc.get('email_address', '').lower() == account_email_filter.lower():
                        matching_account = acc
                        break

                if matching_account:
                    filters['account_id'] = matching_account.get('id')
                    logger.info(f"[QUERY_EMAILS] Resolved to account_id: {filters['account_id']}")
                    # Remove account_email from filters since we resolved it
                    filters.pop('account_email', None)
                else:
                    logger.warning(f"[QUERY_EMAILS] No account found matching email '{account_email_filter}'")
                    # Maybe it's a sender after all? Let's treat it as sender
                    logger.info(f"[QUERY_EMAILS] Treating '{account_email_filter}' as sender filter instead")
                    filters['sender'] = account_email_filter
                    filters.pop('account_email', None)

        # Fetch emails with extracted filters
        logger.info(f"[QUERY_EMAILS] Calling fetch_mails with:")
        logger.info(f"  - sender: {filters.get('sender')}")
        logger.info(f"  - importance: {filters.get('importance')}")
        logger.info(f"  - time_period: {filters.get('time_period')}")
        logger.info(f"  - subject_keyword: {filters.get('subject_keyword')}")
        logger.info(f"  - account_id: {filters.get('account_id')}")
        logger.info(f"  - max_results: {filters.get('max_results', 25)}")
        logger.info(f"  - user_id: {user_id}")

        emails = fetch_mails(
            sender=filters.get('sender'),
            importance=filters.get('importance'),
            time_period=filters.get('time_period'),
            subject_keyword=filters.get('subject_keyword'),
            account_id=filters.get('account_id'),
            max_results=filters.get('max_results', 25),
            user_id=user_id
        )

        logger.info(f"[QUERY_EMAILS] fetch_mails returned {len(emails) if emails else 0} emails")
        if emails:
            for i, email in enumerate(emails[:3]):  # Log first 3 emails
                logger.info(f"[QUERY_EMAILS] Email {i+1}: from={email.get('sender')}, subject={email.get('subject')}, account_id={email.get('account_id')}, ml_prediction={email.get('ml_prediction')}")

        if not emails:
            return {
                "success": True,
                "method": "intelligent_filtering",
                "query": query,
                "count": 0,
                "emails": [],
                "insights": f"No emails found matching your query: '{query}'"
            }

        # Format results
        formatted_emails = []
        for email in emails:
            formatted_emails.append({
                'from': email.get('sender', 'Unknown'),
                'subject': email.get('subject', 'No subject'),
                'date': str(email.get('date', 'Unknown')),
                'body': email.get('body', '')[:500],
                'message_id': email.get('message_id'),
                'account_id': email.get('account_id'),
                'provider': email.get('provider', 'gmail'),
                'ml_prediction': email.get('ml_prediction')
            })

        return {
            "success": True,
            "method": "intelligent_filtering",
            "query": query,
            "filters_used": filters,
            "count": len(formatted_emails),
            "emails": formatted_emails,
            "insights": _generate_insights(formatted_emails, query)
        }

    except Exception as e:
        logger.error(f"Error querying emails: {str(e)}")
        return {
            "success": False,
            "query": query,
            "error": str(e),
            "message": f"Failed to query emails: {str(e)}"
        }


def _extract_filters_from_query(query: str) -> Dict:
    """
    Extract email filters from natural language query using smart keyword extraction.

    Examples:
    - "emails from Google jobs" -> {'subject_keyword': 'google jobs'} (searches in subject/body)
    - "important emails from boss today" -> {'sender': 'boss', 'importance': True, 'time_period': 'today'}
    - "meetings tomorrow" -> {'subject_keyword': 'meeting', 'time_period': 'today'}
    - "what did I receive from Google jobs" -> {'subject_keyword': 'google jobs'}
    - "important mails from mehmetardagonel@gmail.com" -> {'importance': True, 'account_email': 'mehmetardagonel@gmail.com'}

    IMPROVED LOGIC:
    - Company/service names (Google, Amazon, LinkedIn, etc.) are treated as subject keywords, not senders
    - Only use sender filter when it's clearly a person's name or specific email
    - Partial matching: "Google jobs" will match "Google Careers" emails
    - Email addresses matching user's accounts are treated as account filters, not sender filters
    """
    query_lower = query.lower()
    filters = {}
    import re

    logger.info(f"[EXTRACT_FILTERS] Processing query: '{query}'")

    # Common company/service names that should be searched in subject/body, not sender
    company_keywords = [
        'google', 'amazon', 'microsoft', 'apple', 'meta', 'facebook',
        'linkedin', 'twitter', 'netflix', 'uber', 'airbnb', 'spotify',
        'openai', 'chatgpt', 'github', 'stackoverflow', 'reddit',
        'tesla', 'nvidia', 'intel', 'oracle', 'salesforce'
    ]

    # Extract importance
    if any(word in query_lower for word in ['important', 'urgent', 'priority', 'critical']):
        filters['importance'] = True

    # Extract time period
    if 'today' in query_lower or 'tomorrow' in query_lower:
        filters['time_period'] = 'today'
    elif 'yesterday' in query_lower:
        filters['time_period'] = 'yesterday'
    elif 'last week' in query_lower or 'past week' in query_lower or 'this week' in query_lower:
        filters['time_period'] = 'last_week'
    elif 'last month' in query_lower or 'past month' in query_lower or 'this month' in query_lower:
        filters['time_period'] = 'last_month'
    elif 'last 3 months' in query_lower or 'past 3 months' in query_lower:
        filters['time_period'] = 'last_3_months'

    # Smart extraction of "from X" - check if it's a company or person
    from_patterns = [
        r'from\s+([a-zA-Z0-9\s@._-]+?)(?:\s+about|\s+regarding|\s+in|\s+on|\s+yesterday|\s+today|\s+last|\s+$|\?)',
        r'by\s+([a-zA-Z0-9\s@._-]+?)(?:\s+about|\s+regarding|\s+in|\s+on|\s+yesterday|\s+today|\s+last|\s+$|\?)'
    ]

    from_match = None
    for pattern in from_patterns:
        match = re.search(pattern, query_lower)
        if match:
            from_match = match.group(1).strip()
            break

    if from_match:
        logger.info(f"[EXTRACT_FILTERS] Found 'from' match: '{from_match}'")

        # Check if it's a company/service name
        is_company = any(company in from_match for company in company_keywords)

        if is_company or 'jobs' in from_match or 'careers' in from_match:
            # Treat as subject keyword for broader matching
            logger.info(f"[EXTRACT_FILTERS] Treating as subject keyword (company/service)")
            filters['subject_keyword'] = from_match
        elif '@' in from_match:
            # It's an email address - could be account email or sender email
            # We'll mark it as account_email for now, and the query_emails function
            # will resolve it to account_id if it matches a user's account
            logger.info(f"[EXTRACT_FILTERS] Found email address: '{from_match}' - marking as account_email")
            filters['account_email'] = from_match
        else:
            # Check if it looks like a person's name (short, no special keywords)
            words = from_match.split()
            if len(words) <= 2 and not any(kw in from_match for kw in ['jobs', 'careers', 'team', 'support']):
                logger.info(f"[EXTRACT_FILTERS] Treating as sender (person's name)")
                filters['sender'] = from_match
            else:
                # Treat as subject keyword for broader search
                logger.info(f"[EXTRACT_FILTERS] Treating as subject keyword (generic)")
                filters['subject_keyword'] = from_match

    # Extract "about X" or "regarding X"
    about_patterns = [
        r'about\s+([a-zA-Z0-9\s]+?)(?:\s+from|\s+by|\s+in|\s+on|\s+yesterday|\s+today|\s+last|\s+$|\?)',
        r'regarding\s+([a-zA-Z0-9\s]+?)(?:\s+from|\s+by|\s+in|\s+on|\s+yesterday|\s+today|\s+last|\s+$|\?)'
    ]
    for pattern in about_patterns:
        match = re.search(pattern, query_lower)
        if match:
            filters['subject_keyword'] = match.group(1).strip()
            break

    # Look for specific keywords in the query
    if 'meeting' in query_lower or 'meetings' in query_lower:
        filters['subject_keyword'] = 'meeting'
    elif 'invitation' in query_lower:
        filters['subject_keyword'] = 'invitation'

    # Set reasonable max results
    filters['max_results'] = 25

    logger.info(f"[EXTRACT_FILTERS] Final extracted filters: {filters}")
    return filters


def _generate_insights(emails: List[Dict], query: str) -> str:
    """
    Generate insights from the email results based on the query.

    This provides a natural language summary of the results.
    """
    if not emails:
        return f"No emails found matching: '{query}'"

    insights = []
    count = len(emails)

    # Count by sender
    senders = {}
    for email in emails:
        sender = email.get('from', 'Unknown')
        senders[sender] = senders.get(sender, 0) + 1

    # Check for important emails
    important_count = sum(1 for email in emails if email.get('ml_prediction') == 'important')

    # Build insights
    insights.append(f"Found {count} email(s) matching your query.")

    if senders:
        top_senders = sorted(senders.items(), key=lambda x: x[1], reverse=True)[:3]
        sender_summary = ", ".join([f"{sender} ({count})" for sender, count in top_senders])
        insights.append(f"Top senders: {sender_summary}")

    if important_count > 0:
        insights.append(f"{important_count} of these are marked as important.")

    # Check for meetings in subject
    meeting_emails = [
        email for email in emails
        if 'meeting' in email.get('subject', '').lower() or
           'invitation' in email.get('subject', '').lower() or
           'event' in email.get('subject', '').lower()
    ]
    if meeting_emails:
        insights.append(f"{len(meeting_emails)} email(s) appear to be about meetings or events.")
        # Extract first meeting details
        first_meeting = meeting_emails[0]
        insights.append(f"Most recent: '{first_meeting.get('subject')}' from {first_meeting.get('from')}")

    return "\n".join(insights)
