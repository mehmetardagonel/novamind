"""
Email Tools - Wrapper functions for email operations
These functions use Gmail API directly for email operations.
"""

from typing import List, Dict, Optional
import logging
from dotenv import load_dotenv
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
from datetime import timedelta, date, datetime

load_dotenv()
logger = logging.getLogger(__name__)

# ============ BASIC EMAIL OPERATIONS ============

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
    Send an email via Gmail with multi-account support.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body
        user_id: User ID for multi-account support (optional, uses legacy if None)
    """
    try:
        import asyncio
        from gmail_service import get_primary_account_service

        # Get service based on user_id
        if user_id:
            # Multi-account: primary account kullan
            service = asyncio.run(get_primary_account_service(user_id))
            profile = service.users().getProfile(userId="me").execute()
            current_user = profile.get("emailAddress", "me")
        else:
            # Legacy behavior
            current_user = get_current_user_email()
            service = None

        result = gmail_send_email(
            sender=current_user or "me",
            to=to,
            subject=subject,
            body=body,
            service=service
        )
        return {
            "success": True,
            "message": "Email sent successfully",
            "message_id": result.get("id")
        }
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to send email: {str(e)}"
        }


def draft_email(to: str = "", subject: str = "", body: str = "", user_id: str = None) -> Dict:
    """
    Create a draft email without sending it with multi-account support.
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

        # Get service based on user_id
        if user_id:
            import asyncio
            from gmail_service import get_primary_account_service
            service = asyncio.run(get_primary_account_service(user_id))
        else:
            service = None  # create_draft uses legacy

        # Body is optional - drafts can be created with empty body for later editing
        draft = create_draft(to=to, subject=subject, body=body or "", service=service)
        draft_id = draft.get("id")

        return {
            "success": True,
            "message": "Draft created successfully",
            "draft_id": draft_id,
            "draft": {
            "to": to,
            "subject": subject,
            "body": body[:200] + "..." if len(body) > 200 else body  # Preview
    }
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
            import asyncio
            from gmail_service import fetch_drafts_multi
            drafts = asyncio.run(fetch_drafts_multi(user_id, max_per_account=50))
        else:
            # Query for drafts label (legacy)
            drafts = fetch_messages(query='label:DRAFT')

        return [draft.model_dump(mode='json') for draft in drafts]
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
    """Get a specific draft by ID from Gmail (supports multi-account)."""
    try:
        service = None
        if user_id:
            import asyncio
            from gmail_service import get_primary_account_service
            service = asyncio.run(get_primary_account_service(user_id))

        draft = get_gmail_draft_by_id(draft_id, service=service)
        if draft:
            return draft.model_dump(mode='json') if hasattr(draft, 'model_dump') else draft
        return None
    except Exception as e:
        logger.error(f"Error getting draft: {str(e)}")
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
            import asyncio
            from gmail_service import get_primary_account_service
            service = asyncio.run(get_primary_account_service(user_id))
            drafts = get_gmail_drafts_by_recipient(to_email, service=service)
        else:
            drafts = get_gmail_drafts_by_recipient(to_email)

        return [draft if isinstance(draft, dict) else draft.model_dump(mode='json')
                for draft in drafts]
    except Exception as e:
        logger.error(f"Error fetching drafts for recipient {to_email}: {str(e)}")
        return []


def delete_draft(draft_id: str, user_id: str = None) -> Dict:
    """Delete a draft email from Gmail (supports multi-account)."""
    try:
        service = None
        if user_id:
            import asyncio
            from gmail_service import get_primary_account_service
            service = asyncio.run(get_primary_account_service(user_id))

        success = delete_gmail_draft(draft_id, service=service)
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
    """Send a previously created draft from Gmail (supports multi-account)."""
    try:
        service = None
        if user_id:
            import asyncio
            from gmail_service import get_primary_account_service
            service = asyncio.run(get_primary_account_service(user_id))

        sent_msg = send_gmail_draft(draft_id, service=service)
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
    Update a draft email in Gmail.

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
        service = None
        if user_id:
            import asyncio
            from gmail_service import get_primary_account_service
            service = asyncio.run(get_primary_account_service(user_id))

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

    All filters are optional and can be combined together.
    """
    try:
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

        # Add importance filter
        if importance is True:
            query += ' is:important'
        elif importance is False:
            query += ' -is:important'

        # Add folder filter
        if folder:
            query += f' in:{folder}'

        # Pass max_results to fetch_messages so Gmail API respects the limit
        if user_id:
            import asyncio
            from gmail_service import fetch_messages_multi_account
            emails = asyncio.run(fetch_messages_multi_account(
                user_id,
                query=query or "in:inbox",
                max_per_account=max_results
            ))
        else:
            emails = fetch_messages(query=query or None, max_results=max_results)

        return [email.model_dump(mode='json') for email in emails]
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
        emails = fetch_mails(sender=sender, max_results=max_results, user_id=user_id)

        if not emails:
            return {
                "success": False,
                "moved_count": 0,
                "message": f"No emails found from sender '{sender}'"
            }

        # Extract email IDs from results
        email_ids = [email.get("id") for email in emails if email.get("id")]

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
    
