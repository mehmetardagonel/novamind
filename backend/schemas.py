"""
Pydantic schemas for email agent tools.

These schemas replace the fragile pipe-separated string inputs with proper
structured JSON inputs that LLMs (especially Gemini) can reliably generate.
"""

from typing import Optional, Literal, List
from pydantic import BaseModel, Field, EmailStr


# =============================================================================
# Email Draft Schemas
# =============================================================================

class DraftEmailInput(BaseModel):
    """Schema for creating a draft email."""
    recipient: Optional[str] = Field(
        default=None,
        description="The email address of the recipient. If not provided, the system will ask for it."
    )
    subject: Optional[str] = Field(
        default=None,
        description="The email subject line. If not provided and user wants auto-generation, it will be created automatically."
    )
    body: Optional[str] = Field(
        default=None,
        description="The email body content. If not provided and user wants auto-generation, it will be created automatically."
    )
    auto_generate: bool = Field(
        default=False,
        description="Set to True if the user wants subject and body to be generated automatically based on context."
    )
    context_hint: Optional[str] = Field(
        default=None,
        description="Optional context from user message to help auto-generate subject/body (e.g., 'about the grocery list')."
    )


class SendEmailInput(BaseModel):
    """Schema for sending an email immediately."""
    recipient: str = Field(
        ...,
        description="The email address of the recipient (required)."
    )
    subject: str = Field(
        ...,
        description="The email subject line (required)."
    )
    body: str = Field(
        ...,
        description="The email body content (required)."
    )


class UpdateDraftInput(BaseModel):
    """Schema for updating an existing draft."""
    recipient_email: str = Field(
        ...,
        description="The recipient email address to identify the draft."
    )
    instruction: str = Field(
        ...,
        description="Natural language instruction for how to update the draft (e.g., 'make it more formal', 'add a greeting')."
    )


class DraftOperationInput(BaseModel):
    """Schema for draft operations (send/delete)."""
    recipient_email: str = Field(
        ...,
        description="The recipient email address to identify the draft."
    )


# =============================================================================
# Email Fetch/Query Schemas
# =============================================================================

class FetchMailsInput(BaseModel):
    """Schema for fetching emails with filters."""
    label: Optional[str] = Field(
        default=None,
        description="Filter by email label (e.g., 'Work', 'Personal')."
    )
    sender: Optional[str] = Field(
        default=None,
        description="Filter by sender name or email address (partial match)."
    )
    importance: Optional[bool] = Field(
        default=None,
        description="Filter by importance (True for important emails only)."
    )
    subject_keyword: Optional[str] = Field(
        default=None,
        description="Filter by keyword in subject line."
    )
    folder: Optional[str] = Field(
        default="inbox",
        description="Email folder to search (default: 'inbox')."
    )
    max_results: int = Field(
        default=25,
        ge=1,
        le=50,
        description="Maximum number of emails to return (1-50, default: 25)."
    )
    provider: Optional[Literal["gmail", "outlook"]] = Field(
        default=None,
        description="Email provider to fetch from ('gmail' or 'outlook')."
    )
    account_id: Optional[str] = Field(
        default=None,
        description="Specific account ID when multiple accounts are connected."
    )
    time_period: Optional[Literal["today", "yesterday", "last_week", "last_month", "last_3_months"]] = Field(
        default=None,
        description="Predefined time period filter."
    )
    since_date: Optional[str] = Field(
        default=None,
        description="Filter emails since this date (ISO format: YYYY-MM-DD)."
    )
    until_date: Optional[str] = Field(
        default=None,
        description="Filter emails until this date (ISO format: YYYY-MM-DD)."
    )


class QueryEmailsInput(BaseModel):
    """Schema for natural language email queries."""
    query: str = Field(
        ...,
        description="Natural language query to search emails (e.g., 'emails from Google about jobs')."
    )


# =============================================================================
# Email Organization Schemas
# =============================================================================

class MoveMailsInput(BaseModel):
    """Schema for moving emails by sender to a folder."""
    sender: str = Field(
        ...,
        description="Sender name or email to match (partial match, case-insensitive)."
    )
    target_folder: str = Field(
        ...,
        description="Target label/folder to move emails to (will be created if doesn't exist)."
    )


# =============================================================================
# Agent State Schemas (for LangGraph)
# =============================================================================

class DraftPendingState(BaseModel):
    """State for draft creation that needs more information."""
    action: Literal["awaiting_recipient", "awaiting_subject", "awaiting_body", "awaiting_confirmation"]
    recipient: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    context_hint: Optional[str] = None


class AgentResponse(BaseModel):
    """Standardized response from agent operations."""
    success: bool
    message: str
    data: Optional[dict] = None
    requires_input: bool = False
    input_type: Optional[str] = None
    pending_state: Optional[DraftPendingState] = None
