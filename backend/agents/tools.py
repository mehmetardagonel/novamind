"""
Tool definitions for specialized email agents.

These tools use Pydantic schemas for structured inputs, eliminating the
fragile pipe-separated string parsing that caused LLM hallucinations.
"""

import json
import logging
import re
from typing import Optional
from datetime import datetime

from langchain_core.tools import tool, StructuredTool
from pydantic import BaseModel, Field

# Import from parent directory
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from email_tools import (
    list_email_accounts as _list_accounts,
    fetch_mails as _fetch_mails,
    delete_all_spam as _delete_spam,
    move_mails_by_sender as _move_mails,
    send_email as _send_email,
    draft_email as _draft_email,
    get_drafts as _get_drafts,
    get_drafts_for_recipient as _get_drafts_for_recipient,
    send_draft as _send_draft,
    delete_draft as _delete_draft,
    update_draft as _update_draft,
    get_draft_body as _get_draft_body,
    query_emails as _query_emails,
)
from schemas import (
    DraftEmailInput,
    SendEmailInput,
    UpdateDraftInput,
    FetchMailsInput,
    QueryEmailsInput,
    MoveMailsInput,
    DraftOperationInput,
)

logger = logging.getLogger(__name__)

IMG_SRC_RE = re.compile(r"<img[^>]+src=['\"]?([^'\" >]+)", re.IGNORECASE)


def _extract_image_urls(body: Optional[str]) -> list:
    if not body:
        return []
    urls = []
    for match in IMG_SRC_RE.findall(str(body)):
        if not match:
            continue
        cleaned = match.strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered.startswith("cid:") or lowered.startswith("data:"):
            continue
        urls.append(cleaned)
    seen = set()
    deduped = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def _filter_images(images: Optional[list]) -> list:
    if not isinstance(images, list):
        return []
    filtered = []
    for src in images:
        if not isinstance(src, str):
            continue
        lowered = src.lower()
        if lowered.startswith("cid:") or lowered.startswith("data:"):
            continue
        filtered.append(src)
    return filtered


def _apply_images(email: dict) -> dict:
    if not isinstance(email, dict):
        return email
    images = _extract_image_urls(email.get("body"))
    if not images:
        images = _filter_images(email.get("images"))
    if images:
        email["images"] = images
    return email


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


# =============================================================================
# INBOX AGENT TOOLS (Read-only operations)
# =============================================================================

def create_inbox_tools(user_id: Optional[str] = None):
    """Create tools for the Inbox Agent (read-only operations)."""

    @tool
    def list_email_accounts() -> str:
        """List all connected email accounts (Gmail and Outlook) for the current user."""
        try:
            result = _list_accounts(user_id=user_id)
            return json.dumps(result, indent=2, cls=DateTimeEncoder)
        except Exception as e:
            logger.error(f"Error listing accounts: {e}")
            return json.dumps({"error": str(e)})

    @tool
    def fetch_emails(
        label: Optional[str] = None,
        sender: Optional[str] = None,
        importance: Optional[bool] = None,
        subject_keyword: Optional[str] = None,
        folder: str = "inbox",
        max_results: int = 25,
        provider: Optional[str] = None,
        account_id: Optional[str] = None,
        time_period: Optional[str] = None,
        since_date: Optional[str] = None,
        until_date: Optional[str] = None,
    ) -> str:
        """
        Fetch emails with optional filters.

        Args:
            label: Filter by email label (e.g., 'Work', 'Personal')
            sender: Filter by sender name or email (partial match)
            importance: True to filter important emails only
            subject_keyword: Filter by keyword in subject
            folder: Email folder (default: 'inbox')
            max_results: Max emails to return (1-50, default: 25)
            provider: 'gmail' or 'outlook'
            account_id: Specific account ID
            time_period: 'today', 'yesterday', 'last_week', 'last_month', 'last_3_months'
            since_date: Filter since date (YYYY-MM-DD)
            until_date: Filter until date (YYYY-MM-DD)
        """
        try:
            # Clamp max_results
            max_results = max(1, min(50, max_results))

            result = _fetch_mails(
                label=label,
                sender=sender,
                importance=importance,
                subject_keyword=subject_keyword,
                folder=folder,
                max_results=max_results,
                provider=provider,
                account_id=account_id,
                time_period=time_period,
                since_date=since_date,
                until_date=until_date,
                user_id=user_id,
            )

            # Format for UI rendering
            if isinstance(result, list):
                # Truncate long bodies for display
                emails_for_json = []
                for email in result:
                    e_copy = email.copy() if isinstance(email, dict) else email
                    if isinstance(e_copy, dict):
                        _apply_images(e_copy)
                        if e_copy.get("body") and len(e_copy["body"]) > 200:
                            e_copy["body"] = e_copy["body"][:200] + "..."
                    emails_for_json.append(e_copy)

                json_str = json.dumps(emails_for_json, indent=2, cls=DateTimeEncoder)
                return f"```json\n{json_str}\n```"

            return json.dumps(result, indent=2, cls=DateTimeEncoder)
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return json.dumps({"error": str(e)})

    @tool
    def query_emails(query: str) -> str:
        """
        Search emails using natural language query.

        Args:
            query: Natural language search query (e.g., 'emails from Google about jobs')
        """
        try:
            result = _query_emails(query=query, user_id=user_id)
            return json.dumps(result, indent=2, cls=DateTimeEncoder)
        except Exception as e:
            logger.error(f"Error querying emails: {e}")
            return json.dumps({"error": str(e)})

    @tool
    def get_all_drafts() -> str:
        """Get all draft emails from the user's account."""
        try:
            result = _get_drafts(user_id=user_id)
            if isinstance(result, list):
                drafts_for_json = []
                for draft in result:
                    d_copy = draft.copy() if isinstance(draft, dict) else draft
                    if isinstance(d_copy, dict):
                        _apply_images(d_copy)
                        if d_copy.get("body") and len(d_copy["body"]) > 200:
                            d_copy["body"] = d_copy["body"][:200] + "..."
                    drafts_for_json.append(d_copy)
                return json.dumps(drafts_for_json, indent=2, cls=DateTimeEncoder)
            return json.dumps(result, indent=2, cls=DateTimeEncoder)
        except Exception as e:
            logger.error(f"Error getting drafts: {e}")
            return json.dumps({"error": str(e)})

    @tool
    def get_drafts_for_recipient(recipient_email: str) -> str:
        """
        Get all draft emails for a specific recipient.

        Args:
            recipient_email: The email address of the recipient
        """
        try:
            result = _get_drafts_for_recipient(recipient_email, user_id=user_id)
            if isinstance(result, list):
                drafts_for_json = []
                for draft in result:
                    d_copy = draft.copy() if isinstance(draft, dict) else draft
                    if isinstance(d_copy, dict):
                        _apply_images(d_copy)
                        if d_copy.get("body") and len(d_copy["body"]) > 200:
                            d_copy["body"] = d_copy["body"][:200] + "..."
                    drafts_for_json.append(d_copy)
                return json.dumps(drafts_for_json, indent=2, cls=DateTimeEncoder)
            return json.dumps(result, indent=2, cls=DateTimeEncoder)
        except Exception as e:
            logger.error(f"Error getting drafts for {recipient_email}: {e}")
            return json.dumps({"error": str(e)})

    @tool
    def summarize_emails(
        time_period: str = "today",
        importance: bool = False,
        max_emails: int = 25,
    ) -> str:
        """
        Generate an AI summary of emails from a specific time period.

        Args:
            time_period: Time period to summarize (today, yesterday, last_week, last_month)
            importance: If True, only summarize important emails
            max_emails: Maximum number of emails to include in summary (default 25)

        Returns:
            JSON string with summary and email details
        """
        try:
            # Get LLM instance
            from agents.supervisor import get_llm
            llm = get_llm()

            # Fetch emails based on criteria
            emails = _fetch_mails(
                time_period=time_period,
                importance=importance,
                max_results=max_emails,
                user_id=user_id,
            )

            if not emails or not isinstance(emails, list):
                return json.dumps({
                    "success": False,
                    "message": f"No emails found for {time_period}",
                })

            # Prepare email data for LLM summarization
            email_items = []
            emails_for_display = []
            for email in emails[:max_emails]:
                sender = email.get("sender", "Unknown sender")
                subject = email.get("subject", "(No subject)")
                body = email.get("body", "")
                date = email.get("date", "")

                # Truncate body for summary
                snippet = " ".join(body.split())[:200]
                if len(snippet) >= 200:
                    snippet = snippet + "..."

                email_items.append(
                    f"- **{subject}** from {sender}\n"
                    f"  Date: {date}\n"
                    f"  Preview: {snippet}"
                )

                if isinstance(email, dict):
                    email_copy = email.copy()
                    _apply_images(email_copy)
                    if email_copy.get("body") and len(email_copy["body"]) > 300:
                        email_copy["body"] = email_copy["body"][:300] + "..."
                    emails_for_display.append(email_copy)
                else:
                    emails_for_display.append({
                        "sender": sender,
                        "subject": subject,
                        "body": snippet,
                        "date": date,
                    })

            # Create LLM prompt for summarization
            emails_text = "\n\n".join(email_items)
            importance_label = "important " if importance else ""
            period_label = time_period.replace("_", " ")

            prompt = (
                f"You are an email assistant. Create a concise, helpful summary of the user's "
                f"{importance_label}emails from {period_label}.\n\n"
                f"Guidelines:\n"
                f"- Write 2-4 sentences in natural, conversational language\n"
                f"- Highlight key topics, action items, and important senders\n"
                f"- Group similar emails together (e.g., 'several updates from the team')\n"
                f"- Mention any urgent or time-sensitive matters\n"
                f"- Do NOT use bullet points, JSON, or code formatting\n\n"
                f"Emails to summarize ({len(emails)} total):\n\n"
                f"{emails_text}"
            )

            # Generate summary with LLM
            summary_text = llm.invoke(prompt).content.strip()

            # Clean up any code fences or JSON that might have leaked through
            import re
            summary_text = re.sub(r'```[\s\S]*?```', '', summary_text).strip()

            return json.dumps({
                "success": True,
                "summary": summary_text,
                "email_count": len(emails),
                "time_period": time_period,
                "importance": importance,
                "emails": emails_for_display,
            }, cls=DateTimeEncoder)

        except Exception as e:
            logger.error(f"Error summarizing emails: {e}")
            return json.dumps({
                "success": False,
                "message": f"Failed to summarize emails: {str(e)}",
            })

    return [list_email_accounts, fetch_emails, query_emails, get_all_drafts, get_drafts_for_recipient, summarize_emails]


# =============================================================================
# DRAFT AGENT TOOLS (Draft composition and management)
# =============================================================================

def create_draft_tools(user_id: Optional[str] = None, llm=None):
    """Create tools for the Draft Agent (composition operations)."""

    @tool
    def create_draft(
        recipient: Optional[str] = None,
        subject: Optional[str] = None,
        body: Optional[str] = None,
    ) -> str:
        """
        Create a new email draft.

        IMPORTANT: If recipient is not provided, the tool will indicate that
        the user needs to provide the recipient email address.

        Args:
            recipient: Email address of the recipient (optional - will ask if missing)
            subject: Subject line of the email (optional - can be auto-generated)
            body: Body content of the email (optional - can be auto-generated)
        """
        try:
            result = _draft_email(
                to=recipient or "",
                subject=subject or "",
                body=body or "",
                user_id=user_id,
            )
            return json.dumps(result, indent=2, cls=DateTimeEncoder)
        except Exception as e:
            logger.error(f"Error creating draft: {e}")
            return json.dumps({"error": str(e)})

    @tool
    def update_draft(
        recipient_email: Optional[str] = None,
        draft_id: Optional[str] = None,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        instruction: Optional[str] = None,
    ) -> str:
        """
        Update an existing draft with direct subject/body OR natural language instruction.

        MODES:
        1. Direct Update: Provide subject and/or body to update specific fields
        2. AI Enhancement: Provide instruction for LLM-based body modification

        Args:
            recipient_email: Email address to identify the draft (used when draft_id not provided)
            draft_id: Direct draft ID (takes priority over recipient_email)
            subject: New subject line (optional - only updates if provided)
            body: New body content (optional - only updates if provided)
            instruction: Natural language instruction for AI enhancement (ignored if body provided)

        Examples:
            - update_draft(recipient_email="test@example.com", subject="New Subject", body="New Body")
            - update_draft(draft_id="12345", subject="Updated Subject")
            - update_draft(recipient_email="test@example.com", instruction="make it more formal")
        """
        try:
            # Determine which draft to update
            target_draft = None
            target_draft_id = draft_id

            if not target_draft_id and recipient_email:
                # Get drafts for this recipient
                drafts = _get_drafts_for_recipient(recipient_email, user_id=user_id)

                if not drafts:
                    return json.dumps({
                        "success": False,
                        "message": f"No drafts found for {recipient_email}"
                    })

                if len(drafts) > 1:
                    # Need selection
                    draft_list = "\n".join([
                        f"{i+1}. {d.get('subject', '(No subject)')[:40]}... ({d.get('date', 'Unknown')[:10]})"
                        for i, d in enumerate(drafts)
                    ])
                    return json.dumps({
                        "success": False,
                        "requires_selection": True,
                        "drafts": drafts,
                        "message": f"Found {len(drafts)} drafts for {recipient_email}:\n{draft_list}\nWhich one would you like to update?"
                    })

                # Single draft
                target_draft = drafts[0]
                target_draft_id = target_draft.get("id")

            if not target_draft_id:
                return json.dumps({
                    "success": False,
                    "message": "Please provide either draft_id or recipient_email to identify the draft"
                })

            # Determine update mode: Direct vs. AI Enhancement
            update_subject = subject
            update_body = body

            # MODE 1: Direct subject/body update
            if subject is not None or body is not None:
                # Direct update - use provided values as-is
                pass

            # MODE 2: AI Enhancement via instruction
            elif instruction is not None:
                current_body = _get_draft_body(target_draft_id, user_id=user_id) or ""

                # Use LLM to enhance the body
                if llm and current_body.strip():
                    enhancement_prompt = f"""Update this email draft based on the instruction.

Current draft body:
{current_body}

Instruction: {instruction}

Return the COMPLETE updated email body (greeting + content + closing).
Maintain professional tone and structure."""

                    try:
                        response = llm.invoke(enhancement_prompt)
                        update_body = response.content.strip() if hasattr(response, "content") else str(response).strip()
                    except Exception as e:
                        logger.warning(f"LLM enhancement failed: {e}")
                        update_body = instruction
                else:
                    update_body = instruction

            else:
                return json.dumps({
                    "success": False,
                    "message": "Please provide subject, body, or instruction to update the draft"
                })

            # Call the underlying update function
            result = _update_draft(
                draft_id=target_draft_id,
                subject=update_subject,
                body=update_body,
                user_id=user_id
            )

            if result.get("success"):
                updated_fields = []
                if update_subject is not None:
                    updated_fields.append(f"subject: '{update_subject}'")
                if update_body is not None:
                    body_preview = update_body[:100] + "..." if len(update_body) > 100 else update_body
                    updated_fields.append(f"body: {body_preview}")

                return json.dumps({
                    "success": True,
                    "message": f"Draft updated ({', '.join(updated_fields)})",
                    "draft_id": target_draft_id,
                    "updated_subject": update_subject,
                    "updated_body": update_body[:200] + "..." if update_body and len(update_body) > 200 else update_body
                })

            return json.dumps(result)

        except Exception as e:
            logger.error(f"Error updating draft: {e}")
            return json.dumps({"error": str(e)})

    @tool
    def send_draft_to_recipient(recipient_email: str) -> str:
        """
        Send an existing draft to a recipient.

        Args:
            recipient_email: Email address to identify the draft to send
        """
        try:
            drafts = _get_drafts_for_recipient(recipient_email, user_id=user_id)

            if not drafts:
                return json.dumps({
                    "success": False,
                    "message": f"No drafts found for {recipient_email}"
                })

            if len(drafts) > 1:
                draft_list = "\n".join([
                    f"{i+1}. {d.get('subject', '(No subject)')[:40]}... ({d.get('date', 'Unknown')[:10]})"
                    for i, d in enumerate(drafts)
                ])
                return json.dumps({
                    "success": False,
                    "requires_selection": True,
                    "requires_confirmation": True,
                    "drafts": drafts,
                    "message": f"Found {len(drafts)} drafts for {recipient_email}:\n{draft_list}\nWhich one would you like to send?"
                })

            # Single draft - ask for confirmation
            draft = drafts[0]
            return json.dumps({
                "success": False,
                "requires_confirmation": True,
                "draft_id": draft.get("id"),
                "recipient": recipient_email,
                "subject": draft.get("subject", "(No subject)"),
                "message": f"Are you sure you want to send the draft '{draft.get('subject', '(No subject)')}' to {recipient_email}?\n\nReply with 'Yes' or 'No'"
            })

        except Exception as e:
            logger.error(f"Error preparing to send draft: {e}")
            return json.dumps({"error": str(e)})

    @tool
    def delete_draft_for_recipient(recipient_email: str) -> str:
        """
        Delete a draft for a specific recipient.

        Args:
            recipient_email: Email address to identify the draft to delete
        """
        try:
            drafts = _get_drafts_for_recipient(recipient_email, user_id=user_id)

            if not drafts:
                return json.dumps({
                    "success": False,
                    "message": f"No drafts found for {recipient_email}"
                })

            if len(drafts) > 1:
                draft_list = "\n".join([
                    f"{i+1}. {d.get('subject', '(No subject)')[:40]}... ({d.get('date', 'Unknown')[:10]})"
                    for i, d in enumerate(drafts)
                ])
                return json.dumps({
                    "success": False,
                    "requires_selection": True,
                    "drafts": drafts,
                    "message": f"Found {len(drafts)} drafts for {recipient_email}:\n{draft_list}\nWhich one would you like to delete?"
                })

            # Single draft - delete it
            draft = drafts[0]
            _delete_draft(draft.get("id"), user_id=user_id)
            return json.dumps({
                "success": True,
                "message": f"Draft deleted: '{draft.get('subject', '(No subject)')}'"
            })

        except Exception as e:
            logger.error(f"Error deleting draft: {e}")
            return json.dumps({"error": str(e)})

    return [create_draft, update_draft, send_draft_to_recipient, delete_draft_for_recipient]


# =============================================================================
# SEND AGENT TOOLS (Immediate send operations)
# =============================================================================

def create_send_tools(user_id: Optional[str] = None):
    """Create tools for the Send Agent (immediate send operations)."""

    @tool
    def send_email_now(
        recipient: str,
        subject: str,
        body: str,
    ) -> str:
        """
        Send an email immediately (not as draft).

        Args:
            recipient: Email address of the recipient (required)
            subject: Subject line (required)
            body: Email body content (required)
        """
        try:
            result = _send_email(
                to=recipient,
                subject=subject,
                body=body,
                user_id=user_id,
            )
            return json.dumps(result, indent=2, cls=DateTimeEncoder)
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return json.dumps({"error": str(e)})

    @tool
    def confirm_and_send_draft(draft_id: str) -> str:
        """
        Confirm and send a specific draft by ID.

        Args:
            draft_id: The ID of the draft to send
        """
        try:
            result = _send_draft(draft_id, user_id=user_id)
            return json.dumps(result, indent=2, cls=DateTimeEncoder)
        except Exception as e:
            logger.error(f"Error sending draft: {e}")
            return json.dumps({"error": str(e)})

    return [send_email_now, confirm_and_send_draft]


# =============================================================================
# ORGANIZATION AGENT TOOLS (Inbox management)
# =============================================================================

def create_organization_tools(user_id: Optional[str] = None):
    """Create tools for inbox organization operations."""

    @tool
    def move_emails_by_sender(sender: str, target_folder: str) -> str:
        """
        Move all emails from a specific sender to a folder.

        Args:
            sender: Sender name or email to match (partial match)
            target_folder: Target folder/label name (created if doesn't exist)
        """
        try:
            result = _move_mails(sender, target_folder, user_id=user_id)
            return json.dumps(result, indent=2, cls=DateTimeEncoder)
        except Exception as e:
            logger.error(f"Error moving emails: {e}")
            return json.dumps({"error": str(e)})

    @tool
    def delete_spam_emails() -> str:
        """Delete all emails in the spam folder."""
        try:
            result = _delete_spam(user_id=user_id)
            return json.dumps(result, indent=2, cls=DateTimeEncoder)
        except Exception as e:
            logger.error(f"Error deleting spam: {e}")
            return json.dumps({"error": str(e)})

    return [move_emails_by_sender, delete_spam_emails]
