"""
State definitions for the multi-agent email assistant.

This module defines the shared state that flows through the LangGraph workflow,
including conversation history, pending operations, and routing decisions.
"""

from typing import Annotated, Optional, Literal
from typing_extensions import TypedDict
from dataclasses import dataclass, field
from datetime import datetime


def add_messages(left: list, right: list) -> list:
    """Reducer function that appends new messages to existing list."""
    if not left:
        left = []
    if not right:
        right = []
    return left + right


@dataclass
class ConversationMessage:
    """A single message in the conversation."""
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tool_name: Optional[str] = None
    tool_result: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "tool_name": self.tool_name,
            "tool_result": self.tool_result,
        }


class DraftPendingInfo(TypedDict, total=False):
    """Information about a pending draft operation."""
    recipient: Optional[str]
    subject: Optional[str]
    body: Optional[str]
    context_hint: Optional[str]
    auto_generate: bool

    # DEPRECATED - will be phased out after full migration to interrupt()
    awaiting: Literal["recipient", "subject", "body", "confirmation", "selection", "ai_generation_choice", "subject_and_body", "update_instruction", "reply_content"]

    # NEW: Interrupt-based state management (LangGraph best practices)
    interrupt_reason: Optional[Literal["need_recipient", "need_subject_body", "need_ai_choice", "need_draft_selection", "need_update_details", "need_confirmation"]]
    selected_draft_id: Optional[str]  # Preserve draft ID being updated/sent/deleted
    selected_draft_recipient: Optional[str]  # Preserve recipient context across interrupts
    selected_account_id: Optional[str]  # Preserve account ID for multi-account scenarios

    drafts_list: Optional[list]  # For multi-draft selection
    operation: Optional[Literal["send", "delete", "update"]]
    update_instruction: Optional[str]
    reply_to_email: Optional[dict]  # Original email being replied to


class AccountSelectionInfo(TypedDict, total=False):
    """Information about pending account selection."""
    provider: Literal["gmail", "outlook"]
    accounts: list
    payload: dict
    mode: Literal["fetch", "summary", "send"]


class EmailAgentState(TypedDict, total=False):
    """
    Shared state for the email agent workflow.

    This state is passed between all nodes in the LangGraph and maintains:
    - Conversation history
    - Current user input
    - Pending operations that need user input
    - Routing decisions
    - Tool execution results
    """
    # Core conversation
    messages: Annotated[list[dict], add_messages]
    current_input: str
    user_id: Optional[str]

    # Response to return to user
    response: str

    # Routing
    next_agent: Optional[Literal["inbox", "draft", "send", "supervisor", "human", "__end__"]]

    # Pending operations (for multi-turn interactions)
    draft_pending: Optional[DraftPendingInfo]
    account_selection: Optional[AccountSelectionInfo]

    # Context from previous turns
    context: Optional[str]

    # Tool execution tracking
    last_tool_result: Optional[dict]
    intermediate_steps: Optional[list]

    # Optional email payload for UI rendering
    display_emails: Optional[list]

    # Error handling
    error: Optional[str]

    # Human-in-the-loop
    requires_human_input: bool
    human_input_type: Optional[str]
    human_prompt: Optional[str]

    # Listed emails for numbered reference (reply by number)
    listed_emails: Optional[dict]  # {emails: list, listed_at: str, list_type: "emails"|"drafts"}


def create_initial_state(
    user_message: str,
    user_id: Optional[str] = None,
    context: Optional[str] = None,
    existing_messages: Optional[list] = None,
    listed_emails: Optional[dict] = None,
    draft_pending: Optional[DraftPendingInfo] = None,
) -> EmailAgentState:
    """Create initial state for a new conversation turn."""
    messages = existing_messages or []
    messages.append({
        "role": "user",
        "content": user_message,
        "timestamp": datetime.now().isoformat(),
    })

    return EmailAgentState(
        messages=messages,
        current_input=user_message,
        user_id=user_id,
        response="",
        next_agent=None,
        draft_pending=draft_pending,
        account_selection=None,
        context=context,
        last_tool_result=None,
        intermediate_steps=[],
        error=None,
        requires_human_input=False,
        human_input_type=None,
        human_prompt=None,
        listed_emails=listed_emails,
    )
