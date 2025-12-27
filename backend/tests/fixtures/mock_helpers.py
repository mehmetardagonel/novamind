"""
Mock helper functions for testing the email system.
Contains mocks for email tools, LLM, and other dependencies.
"""
from unittest.mock import MagicMock
from typing import Dict, List, Optional
from .mock_data import MOCK_EMAILS, MOCK_DRAFTS


def mock_fetch_mails(
    label: Optional[str] = None,
    sender: Optional[str] = None,
    importance: Optional[bool] = None,
    subject_keyword: Optional[str] = None,
    folder: str = "inbox",
    max_results: int = 50,
    provider: Optional[str] = None,
    account_id: Optional[str] = None,
    time_period: Optional[str] = None,
    since_date: Optional[str] = None,
    until_date: Optional[str] = None,
    user_id: str = None,
) -> List[Dict]:
    """Mock fetch_mails to return test data."""
    # Filter based on importance
    if importance is True:
        return [email for email in MOCK_EMAILS if email.get("ml_prediction") == "important"]
    elif importance is False:
        return [email for email in MOCK_EMAILS if email.get("ml_prediction") != "important"]

    # Filter by time period (simplified - just return empty for 'last year')
    if time_period and 'year' in time_period.lower():
        return []

    return MOCK_EMAILS[:max_results]


def mock_get_drafts_for_recipient(recipient_email: str, user_id: str = None) -> List[Dict]:
    """Mock get_drafts_for_recipient to return test drafts."""
    return [d for d in MOCK_DRAFTS if d.get("to", "").lower() == recipient_email.lower()]


def mock_delete_draft(draft_id: str, user_id: str = None) -> Dict:
    """Mock delete_draft to simulate deletion."""
    draft = next((d for d in MOCK_DRAFTS if d["id"] == draft_id), None)
    if draft:
        return {
            "success": True,
            "message": f"Draft '{draft['subject']}' deleted successfully"
        }
    return {"success": False, "message": "Draft not found"}


def mock_update_draft(
    draft_id: str,
    to: Optional[str] = None,
    subject: Optional[str] = None,
    body: Optional[str] = None,
    append_to_body: Optional[str] = None,
    remove_from_body: Optional[str] = None,
    instruction: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict:
    """Mock update_draft to simulate draft update."""
    draft = next((d for d in MOCK_DRAFTS if d["id"] == draft_id), None)
    if draft:
        # Simulate LLM update
        updated_body = draft["body"] + f"\n\n[Updated based on: {instruction}]"
        return {
            "success": True,
            "new_draft_id": draft_id,
            "draft": {
                "id": draft_id,
                "subject": draft["subject"],
                "body": updated_body,
            }
        }
    return {"success": False, "message": "Draft not found"}


def create_mock_llm_for_routing(route: str = "draft"):
    """
    Create a mock LLM that returns specific routing decisions.

    Args:
        route: The route to return (inbox, draft, send, organization, human, __end__)
    """
    llm = MagicMock()

    # Mock response with routing decision
    mock_response = MagicMock(
        content=route,
        tool_calls=[]
    )

    llm.invoke = MagicMock(return_value=mock_response)
    llm.bind_tools = MagicMock(return_value=llm)

    return llm


def create_mock_llm_with_tool_calls(tool_name: str, tool_args: Dict):
    """
    Create a mock LLM that triggers specific tool calls.

    Args:
        tool_name: Name of the tool to call
        tool_args: Arguments to pass to the tool
    """
    llm = MagicMock()

    # Mock response with tool call
    mock_response = MagicMock(
        content="",
        tool_calls=[{
            "name": tool_name,
            "args": tool_args,
            "id": "call_123"
        }]
    )

    llm.invoke = MagicMock(return_value=mock_response)
    llm.bind_tools = MagicMock(return_value=llm)

    return llm


def create_mock_llm_generic():
    """
    Create a generic mock LLM for basic testing.
    """
    llm = MagicMock()

    # Mock response with generic content and no tool_calls
    mock_response = MagicMock(
        content="Here's a summary of your emails: You received important updates from John about the Q4 project (75% complete, on track for December), Sarah rescheduled a meeting to Friday 3 PM, and there were several notifications from GitHub and monitoring services. The most urgent item is the high CPU alert on server prod-01.",
        tool_calls=[]
    )

    llm.invoke = MagicMock(return_value=mock_response)
    llm.bind_tools = MagicMock(return_value=llm)

    return llm
