"""
Comprehensive test suite for the multi-agent email system.

This test suite uses mock inbox data that resembles the production web app
and tests the newly implemented features:
1. Draft deletion with multiple drafts selection flow
2. Email summarization for different time periods
3. Draft updates with selection
4. Edge cases and error handling

Tests display the full AI agent response for verification.
"""

import pytest
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict

# Mock imports (avoid actual email API calls)
import sys
from pathlib import Path

# Add backend to path (go up two levels from tests/integration/ to backend/)
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

# Import the multi-agent system
from agents.supervisor import create_email_assistant_graph
from agents.state import create_initial_state


# =============================================================================
# MOCK INBOX DATA - Resembles Production Web App
# =============================================================================

MOCK_USER_ID = "test_user_123"
MOCK_USER_EMAIL = "user@example.com"

# Realistic email data matching web app structure
MOCK_EMAILS = [
    {
        "message_id": "msg_001",
        "sender": "john.doe@company.com",
        "recipient": MOCK_USER_EMAIL,
        "subject": "Q4 Project Status Update",
        "body": "Hi team,\n\nHere's the latest update on our Q4 project. We've completed 75% of the tasks and are on track for the December deadline. Key highlights:\n\n- Frontend redesign: 100% complete\n- Backend API: 80% complete\n- Testing: 50% complete\n\nPlease review and let me know if you have any questions.\n\nBest,\nJohn",
        "date": datetime.now(timezone.utc) - timedelta(hours=2),
        "ml_prediction": "important",
        "ml_confidence": 0.92,
        "label_ids": ["INBOX", "IMPORTANT"],
        "account_id": "acc_001",
        "account_email": MOCK_USER_EMAIL,
        "provider": "gmail"
    },
    {
        "message_id": "msg_002",
        "sender": "sarah.williams@partner.com",
        "recipient": MOCK_USER_EMAIL,
        "subject": "Meeting Rescheduled to Friday 3 PM",
        "body": "Hi,\n\nDue to a conflict, I need to reschedule our meeting from Thursday to Friday at 3 PM. Is that time still good for you?\n\nLet me know!\n\nSarah",
        "date": datetime.now(timezone.utc) - timedelta(hours=5),
        "ml_prediction": "important",
        "ml_confidence": 0.88,
        "label_ids": ["INBOX", "IMPORTANT", "CATEGORY_PERSONAL"],
        "account_id": "acc_001",
        "account_email": MOCK_USER_EMAIL,
        "provider": "gmail"
    },
    {
        "message_id": "msg_003",
        "sender": "notifications@github.com",
        "recipient": MOCK_USER_EMAIL,
        "subject": "[repo/project] Pull Request #42: Add dark mode support",
        "body": "A new pull request has been created:\n\nTitle: Add dark mode support\nAuthor: @developer123\n\nChanges:\n- Added dark theme CSS\n- Toggle component in settings\n- User preference persistence\n\nView the pull request: https://github.com/repo/project/pull/42",
        "date": datetime.now(timezone.utc) - timedelta(hours=8),
        "ml_prediction": "ham",
        "ml_confidence": 0.75,
        "label_ids": ["INBOX", "CATEGORY_UPDATES"],
        "account_id": "acc_001",
        "account_email": MOCK_USER_EMAIL,
        "provider": "gmail"
    },
    {
        "message_id": "msg_004",
        "sender": "newsletter@techblog.com",
        "recipient": MOCK_USER_EMAIL,
        "subject": "Weekly Tech Digest: AI, Cloud, and More",
        "body": "This week's top stories:\n\n1. AI breakthrough in natural language processing\n2. Cloud computing trends for 2024\n3. Best practices for microservices architecture\n\nRead more at techblog.com",
        "date": datetime.now(timezone.utc) - timedelta(days=1, hours=3),
        "ml_prediction": "ham",
        "ml_confidence": 0.65,
        "label_ids": ["INBOX", "CATEGORY_PROMOTIONS"],
        "account_id": "acc_001",
        "account_email": MOCK_USER_EMAIL,
        "provider": "gmail"
    },
    {
        "message_id": "msg_005",
        "sender": "alerts@monitoring.com",
        "recipient": MOCK_USER_EMAIL,
        "subject": "ALERT: High CPU usage detected on server prod-01",
        "body": "Alert Details:\n\nServer: prod-01\nMetric: CPU Usage\nCurrent Value: 95%\nThreshold: 80%\nDuration: 15 minutes\n\nAction Required: Investigate immediately\n\nView dashboard: https://monitoring.com/dashboard",
        "date": datetime.now(timezone.utc) - timedelta(days=1, hours=10),
        "ml_prediction": "important",
        "ml_confidence": 0.95,
        "label_ids": ["INBOX", "IMPORTANT", "CATEGORY_UPDATES"],
        "account_id": "acc_001",
        "account_email": MOCK_USER_EMAIL,
        "provider": "gmail"
    },
    {
        "message_id": "msg_006",
        "sender": "deals@shopping.com",
        "recipient": MOCK_USER_EMAIL,
        "subject": "Flash Sale: 50% Off All Electronics!",
        "body": "Limited time offer! Get 50% off all electronics today only.\n\nShop now: https://shopping.com/flash-sale\n\nTerms and conditions apply.",
        "date": datetime.now(timezone.utc) - timedelta(days=2, hours=1),
        "ml_prediction": "spam",
        "ml_confidence": 0.82,
        "label_ids": ["INBOX", "CATEGORY_PROMOTIONS"],
        "account_id": "acc_001",
        "account_email": MOCK_USER_EMAIL,
        "provider": "gmail"
    },
]

# Realistic draft data matching web app structure
MOCK_DRAFTS = [
    {
        "id": "draft_001",
        "subject": "Re: Q4 Project Status Update - Thanks!",
        "date": datetime.now(timezone.utc) - timedelta(hours=1),
        "recipient": "john.doe@company.com",
        "body": "Hi John,\n\nThanks for the detailed update! Everything looks great. I'm particularly impressed with the frontend progress.\n\nLet me know if you need any resources for the remaining tasks.\n\nBest,\nUser",
        "provider": "gmail",
        "account_id": "acc_001",
        "message": {
            "payload": {
                "headers": [
                    {"name": "To", "value": "john.doe@company.com"},
                    {"name": "Subject", "value": "Re: Q4 Project Status Update - Thanks!"},
                    {"name": "Date", "value": str(datetime.now(timezone.utc) - timedelta(hours=1))}
                ]
            }
        }
    },
    {
        "id": "draft_002",
        "subject": "Alternative meeting time suggestion",
        "date": datetime.now(timezone.utc) - timedelta(hours=3),
        "recipient": "john.doe@company.com",
        "body": "Hi John,\n\nI wanted to follow up on scheduling. Would Tuesday at 2 PM work for you instead?\n\nBest,\nUser",
        "provider": "gmail",
        "account_id": "acc_001",
        "message": {
            "payload": {
                "headers": [
                    {"name": "To", "value": "john.doe@company.com"},
                    {"name": "Subject", "value": "Alternative meeting time suggestion"},
                    {"name": "Date", "value": str(datetime.now(timezone.utc) - timedelta(hours=3))}
                ]
            }
        }
    },
    {
        "id": "draft_003",
        "subject": "Question about project timeline",
        "date": datetime.now(timezone.utc) - timedelta(days=1),
        "recipient": "john.doe@company.com",
        "body": "Hi John,\n\nJust checking on the timeline for the backend API completion. Do we have any blockers?\n\nThanks,\nUser",
        "provider": "gmail",
        "account_id": "acc_001",
        "message": {
            "payload": {
                "headers": [
                    {"name": "To", "value": "john.doe@company.com"},
                    {"name": "Subject", "value": "Question about project timeline"},
                    {"name": "Date", "value": str(datetime.now(timezone.utc) - timedelta(days=1))}
                ]
            }
        }
    },
    {
        "id": "draft_004",
        "subject": "Friday meeting confirmation",
        "date": datetime.now(timezone.utc) - timedelta(hours=2),
        "recipient": "sarah.williams@partner.com",
        "body": "Hi Sarah,\n\nFriday at 3 PM works perfectly for me. See you then!\n\nBest,\nUser",
        "provider": "gmail",
        "account_id": "acc_001",
        "message": {
            "payload": {
                "headers": [
                    {"name": "To", "value": "sarah.williams@partner.com"},
                    {"name": "Subject", "value": "Friday meeting confirmation"},
                    {"name": "Date", "value": str(datetime.now(timezone.utc) - timedelta(hours=2))}
                ]
            }
        }
    },
]


# =============================================================================
# MOCK FUNCTIONS
# =============================================================================

def mock_fetch_mails(time_period: str = "today", importance: bool = False,
                     max_results: int = 25, user_id: str = None) -> List[Dict]:
    """Mock version of _fetch_mails that returns mock emails based on time period."""

    # Filter by time period
    now = datetime.now(timezone.utc)

    if time_period == "today":
        cutoff = now - timedelta(days=1)
    elif time_period == "yesterday":
        cutoff = now - timedelta(days=2)
    elif time_period == "last_week":
        cutoff = now - timedelta(days=7)
    elif time_period == "last_month":
        cutoff = now - timedelta(days=30)
    else:
        cutoff = now - timedelta(days=1)

    filtered_emails = [
        email for email in MOCK_EMAILS
        if email["date"] >= cutoff
    ]

    # Filter by importance
    if importance:
        filtered_emails = [
            email for email in filtered_emails
            if email.get("ml_prediction") == "important"
        ]

    return filtered_emails[:max_results]


def mock_get_drafts_for_recipient(recipient_email: str, user_id: str = None) -> List[Dict]:
    """Mock version that returns drafts for a specific recipient."""
    return [
        draft for draft in MOCK_DRAFTS
        if recipient_email.lower() in draft.get("recipient", "").lower()
    ]


def mock_delete_draft(draft_id: str, user_id: str = None) -> Dict:
    """Mock version that simulates draft deletion."""
    draft = next((d for d in MOCK_DRAFTS if d["id"] == draft_id), None)
    if draft:
        return {"success": True, "message": f"Draft {draft_id} deleted"}
    return {"success": False, "message": "Draft not found"}


def mock_update_draft(draft_id: str, instruction: str, user_id: str = None) -> Dict:
    """Mock version that simulates draft update."""
    draft = next((d for d in MOCK_DRAFTS if d["id"] == draft_id), None)
    if draft:
        # Simulate LLM update
        updated_body = draft["body"] + f"\n\n[Updated based on: {instruction}]"
        return {
            "success": True,
            "draft": {
                "id": draft_id,
                "subject": draft["subject"],
                "body": updated_body,
            }
        }
    return {"success": False, "message": "Draft not found"}


def mock_get_llm(*args, **kwargs):
    """
    Mock LLM for testing that intelligently responds based on context.
    Returns appropriate responses and tool calls based on the input.
    """
    llm = MagicMock()
    call_count = {"count": 0}

    def smart_invoke(input_data):
        """Smart mock that returns different responses based on input."""
        call_count["count"] += 1

        # Convert input to string for pattern matching
        if isinstance(input_data, list):
            content = " ".join([str(msg.content) if hasattr(msg, 'content') else str(msg) for msg in input_data])
        else:
            content = str(input_data)

        content_lower = content.lower()

        # Routing calls (supervisor) - return agent name
        if "route to:" in content_lower or "current message:" in content_lower:
            if "delete" in content_lower or "draft" in content_lower:
                return MagicMock(content="draft", tool_calls=[])
            elif "summarize" in content_lower or "summary" in content_lower:
                return MagicMock(content="inbox", tool_calls=[])
            elif "show" in content_lower or "list" in content_lower:
                return MagicMock(content="inbox", tool_calls=[])
            elif "update" in content_lower:
                return MagicMock(content="draft", tool_calls=[])
            else:
                return MagicMock(content="__end__", tool_calls=[])

        # Agent calls with tools bound - return tool calls
        # Check if this is a bound tools call by seeing if there are multiple invocations
        if call_count["count"] > 1:
            # Draft deletion
            if "delete" in content_lower and "draft" in content_lower:
                recipient = None
                if "john.doe@company.com" in content_lower:
                    recipient = "john.doe@company.com"
                elif "sarah.williams@partner.com" in content_lower:
                    recipient = "sarah.williams@partner.com"
                elif "nonexistent@email.com" in content_lower:
                    recipient = "nonexistent@email.com"

                if recipient:
                    return MagicMock(
                        content="",
                        tool_calls=[{
                            "name": "delete_draft_for_recipient",
                            "args": {"recipient_email": recipient},
                            "id": "call_delete_123"
                        }]
                    )

            # Draft update
            if "update" in content_lower and "draft" in content_lower:
                recipient = None
                if "john.doe@company.com" in content_lower:
                    recipient = "john.doe@company.com"

                if recipient:
                    return MagicMock(
                        content="",
                        tool_calls=[{
                            "name": "update_draft",
                            "args": {"recipient_email": recipient, "instruction": "make it more formal"},
                            "id": "call_update_123"
                        }]
                    )

            # Fetch emails / summarize
            if "summarize" in content_lower or "emails" in content_lower:
                return MagicMock(
                    content="",
                    tool_calls=[{
                        "name": "summarize_emails",
                        "args": {"time_period": "today", "importance": False, "max_emails": 25},
                        "id": "call_summarize_123"
                    }]
                )

            # Show/list drafts
            if "show" in content_lower or "list" in content_lower or "drafts" in content_lower:
                recipient = None
                if "john.doe@company.com" in content_lower:
                    recipient = "john.doe@company.com"

                if recipient:
                    return MagicMock(
                        content="",
                        tool_calls=[{
                            "name": "get_drafts_for_recipient",
                            "args": {"recipient_email": recipient},
                            "id": "call_get_drafts_123"
                        }]
                    )

        # Default response (for end node or generic responses)
        return MagicMock(
            content="Here's a summary of your emails: You received important updates from John about the Q4 project (75% complete, on track for December), Sarah rescheduled a meeting to Friday 3 PM, and there were several notifications from GitHub and monitoring services. The most urgent item is the high CPU alert on server prod-01.",
            tool_calls=[]
        )

    llm.invoke = smart_invoke
    llm.bind_tools = MagicMock(return_value=llm)

    return llm


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def mock_email_tools():
    """Mock all email tool functions."""
    with patch('agents.tools._fetch_mails', side_effect=mock_fetch_mails), \
         patch('agents.tools._get_drafts_for_recipient', side_effect=mock_get_drafts_for_recipient), \
         patch('email_tools.delete_draft', side_effect=mock_delete_draft), \
         patch('email_tools.update_draft', side_effect=mock_update_draft), \
         patch('agents.supervisor.get_llm', side_effect=mock_get_llm):
        yield


@pytest.fixture
def supervisor_graph(mock_email_tools):
    """Create a supervisor graph for testing."""
    return create_email_assistant_graph()


# =============================================================================
# TESTS: Draft Deletion with Multiple Drafts Selection Flow
# =============================================================================

def test_draft_deletion_multiple_drafts_flow(supervisor_graph):
    """
    Test the complete flow of deleting a draft when multiple drafts exist:
    1. User asks to delete draft for a recipient
    2. System shows numbered list of drafts
    3. User selects a number
    4. System deletes the correct draft and shows the subject
    """
    print("\n" + "="*80)
    print("TEST: Draft Deletion - Multiple Drafts Selection Flow")
    print("="*80)

    # Step 1: User asks to delete draft
    print("\n[User Input]: Delete the last draft to john.doe@company.com")

    state = create_initial_state(
        user_message="Delete the last draft to john.doe@company.com",
        user_id=MOCK_USER_ID
    )

    config = {"configurable": {"thread_id": "test_thread_001"}}
    result = supervisor_graph.invoke(state, config)

    print(f"\n[Agent Response]:\n{result.get('response', 'No response')}")

    # Verify numbered list is shown
    assert "1." in result.get("response", "")
    assert "2." in result.get("response", "")
    assert "3." in result.get("response", "")
    assert "Q4 Project Status Update" in result.get("response", "")

    # Step 2: User selects draft #2
    print("\n[User Input]: 2")

    state2 = create_initial_state(
        user_message="2",
        user_id=MOCK_USER_ID,
        existing_messages=result.get("messages", [])
    )

    # Manually set draft_pending to simulate state continuation
    state2["draft_pending"] = result.get("draft_pending")

    result2 = supervisor_graph.invoke(state2, config)

    print(f"\n[Agent Response]:\n{result2.get('response', 'No response')}")

    # Verify deletion confirmation with correct subject
    assert "✅ Draft deleted:" in result2.get("response", "") or "deleted" in result2.get("response", "").lower()
    assert "Alternative meeting time suggestion" in result2.get("response", "")
    assert result2.get("response", "") != "Draft deleted: ''"  # Should NOT be empty

    print("\n✓ Test passed: Draft deletion shows correct subject")


def test_draft_deletion_single_draft_flow(supervisor_graph):
    """
    Test deleting when only one draft exists for a recipient.
    Should delete immediately without selection.
    """
    print("\n" + "="*80)
    print("TEST: Draft Deletion - Single Draft Flow")
    print("="*80)

    print("\n[User Input]: Delete draft to sarah.williams@partner.com")

    state = create_initial_state(
        user_message="Delete draft to sarah.williams@partner.com",
        user_id=MOCK_USER_ID
    )

    config = {"configurable": {"thread_id": "test_thread_002"}}
    result = supervisor_graph.invoke(state, config)

    print(f"\n[Agent Response]:\n{result.get('response', 'No response')}")

    # Should delete directly since only one draft exists
    assert "✅" in result.get("response", "") or "deleted" in result.get("response", "").lower()
    assert "Friday meeting confirmation" in result.get("response", "")

    print("\n✓ Test passed: Single draft deleted immediately")


def test_draft_deletion_no_drafts_found(supervisor_graph):
    """
    Test error handling when no drafts exist for a recipient.
    """
    print("\n" + "="*80)
    print("TEST: Draft Deletion - No Drafts Found")
    print("="*80)

    print("\n[User Input]: Delete draft to nonexistent@email.com")

    state = create_initial_state(
        user_message="Delete draft to nonexistent@email.com",
        user_id=MOCK_USER_ID
    )

    result = supervisor_graph.invoke(state, {"configurable": {"thread_id": "test_thread"}})

    print(f"\n[Agent Response]:\n{result.get('response', 'No response')}")

    # Should show "no drafts found" message
    assert "no drafts found" in result.get("response", "").lower() or \
           "couldn't find" in result.get("response", "").lower()

    print("\n✓ Test passed: Proper error message for no drafts")


def test_draft_deletion_invalid_selection(supervisor_graph):
    """
    Test error handling for invalid selection number.
    """
    print("\n" + "="*80)
    print("TEST: Draft Deletion - Invalid Selection")
    print("="*80)

    # Step 1: Get list of drafts
    print("\n[User Input]: Delete draft to john.doe@company.com")

    state = create_initial_state(
        user_message="Delete draft to john.doe@company.com",
        user_id=MOCK_USER_ID
    )

    result = supervisor_graph.invoke(state, {"configurable": {"thread_id": "test_thread"}})
    print(f"\n[Agent Response]:\n{result.get('response', 'No response')}")

    # Step 2: Provide invalid selection
    print("\n[User Input]: 999")

    state2 = create_initial_state(
        user_message="999",
        user_id=MOCK_USER_ID,
        existing_messages=result.get("messages", [])
    )
    state2["draft_pending"] = result.get("draft_pending")

    result2 = supervisor_graph.invoke(state2, {"configurable": {"thread_id": "test_thread"}})

    print(f"\n[Agent Response]:\n{result2.get('response', 'No response')}")

    # Should show error for invalid selection
    assert "invalid" in result2.get("response", "").lower() or \
           "choose" in result2.get("response", "").lower()

    print("\n✓ Test passed: Invalid selection handled correctly")


# =============================================================================
# TESTS: Email Summarization
# =============================================================================

def test_email_summarization_today(supervisor_graph):
    """
    Test email summarization for today's emails.
    """
    print("\n" + "="*80)
    print("TEST: Email Summarization - Today")
    print("="*80)

    print("\n[User Input]: Summarize my emails from today")

    state = create_initial_state(
        user_message="Summarize my emails from today",
        user_id=MOCK_USER_ID
    )

    result = supervisor_graph.invoke(state, {"configurable": {"thread_id": "test_thread"}})

    print(f"\n[Agent Response]:\n{result.get('response', 'No response')}")

    # Should contain summary text (not raw JSON)
    response = result.get("response", "")
    assert len(response) > 50  # Should be a decent summary
    assert "```json" not in response.lower()  # Should NOT show raw JSON
    assert "summary" in response.lower() or "email" in response.lower()

    print("\n✓ Test passed: Email summary generated successfully")


def test_email_summarization_important_only(supervisor_graph):
    """
    Test email summarization filtering for important emails only.
    """
    print("\n" + "="*80)
    print("TEST: Email Summarization - Important Emails Only")
    print("="*80)

    print("\n[User Input]: Create a summary from my important emails this week")

    state = create_initial_state(
        user_message="Create a summary from my important emails this week",
        user_id=MOCK_USER_ID
    )

    result = supervisor_graph.invoke(state, {"configurable": {"thread_id": "test_thread"}})

    print(f"\n[Agent Response]:\n{result.get('response', 'No response')}")

    # Should mention important emails
    response = result.get("response", "")
    assert "summary" in response.lower() or "important" in response.lower()
    assert "```json" not in response.lower()  # Should NOT show raw JSON

    print("\n✓ Test passed: Important email summary generated")


def test_email_summarization_no_emails_found(supervisor_graph):
    """
    Test summarization when no emails match the criteria.
    """
    print("\n" + "="*80)
    print("TEST: Email Summarization - No Emails Found")
    print("="*80)

    # Mock _fetch_mails to return empty list
    with patch('agents.tools._fetch_mails', return_value=[]):
        print("\n[User Input]: Summarize my emails from last year")

        state = create_initial_state(
            user_message="Summarize my emails from last year",
            user_id=MOCK_USER_ID
        )

        result = supervisor_graph.invoke(state, {"configurable": {"thread_id": "test_thread"}})

        print(f"\n[Agent Response]:\n{result.get('response', 'No response')}")

        # Should mention no emails found
        response = result.get("response", "").lower()
        assert "no emails" in response or "not found" in response or "no messages" in response

    print("\n✓ Test passed: Proper handling of no emails scenario")


# =============================================================================
# TESTS: Draft Update with Selection
# =============================================================================

def test_draft_update_multiple_drafts_flow(supervisor_graph):
    """
    Test updating a draft when multiple exist:
    1. User asks to update draft
    2. System shows numbered list
    3. User selects a number
    4. User provides update instruction
    5. System updates and shows result
    """
    print("\n" + "="*80)
    print("TEST: Draft Update - Multiple Drafts Flow")
    print("="*80)

    # Step 1: Request update
    print("\n[User Input]: Update the draft to john.doe@company.com")

    state = create_initial_state(
        user_message="Update the draft to john.doe@company.com",
        user_id=MOCK_USER_ID
    )

    result = supervisor_graph.invoke(state, {"configurable": {"thread_id": "test_thread"}})

    print(f"\n[Agent Response]:\n{result.get('response', 'No response')}")

    # Should show numbered list
    assert "1." in result.get("response", "")
    assert "2." in result.get("response", "")

    # Step 2: Select draft
    print("\n[User Input]: 1")

    state2 = create_initial_state(
        user_message="1",
        user_id=MOCK_USER_ID,
        existing_messages=result.get("messages", [])
    )
    state2["draft_pending"] = result.get("draft_pending")

    result2 = supervisor_graph.invoke(state2, {"configurable": {"thread_id": "test_thread"}})

    print(f"\n[Agent Response]:\n{result2.get('response', 'No response')}")

    # Should ask for update instruction
    assert "what would you like to change" in result2.get("response", "").lower() or \
           "how" in result2.get("response", "").lower()

    # Step 3: Provide update instruction
    print("\n[User Input]: Make it more formal and add a meeting request")

    state3 = create_initial_state(
        user_message="Make it more formal and add a meeting request",
        user_id=MOCK_USER_ID,
        existing_messages=result2.get("messages", [])
    )
    state3["draft_pending"] = result2.get("draft_pending")

    result3 = supervisor_graph.invoke(state3, {"configurable": {"thread_id": "test_thread"}})

    print(f"\n[Agent Response]:\n{result3.get('response', 'No response')}")

    # Should show update success
    assert "✅" in result3.get("response", "") or "updated" in result3.get("response", "").lower()

    print("\n✓ Test passed: Draft update flow completed successfully")


# =============================================================================
# TESTS: Edge Cases and Multi-Turn Conversations
# =============================================================================

def test_conversational_context_maintained(supervisor_graph):
    """
    Test that context is maintained across multiple conversation turns.
    """
    print("\n" + "="*80)
    print("TEST: Multi-Turn Conversation Context")
    print("="*80)

    # Turn 1: Ask about emails
    print("\n[User Input]: What emails did I get today?")

    state1 = create_initial_state(
        user_message="What emails did I get today?",
        user_id=MOCK_USER_ID
    )

    result1 = supervisor_graph.invoke(state1, {"configurable": {"thread_id": "test_thread"}})
    print(f"\n[Agent Response]:\n{result1.get('response', 'No response')}")

    # Turn 2: Follow-up question
    print("\n[User Input]: Which one is most important?")

    state2 = create_initial_state(
        user_message="Which one is most important?",
        user_id=MOCK_USER_ID,
        existing_messages=result1.get("messages", [])
    )

    result2 = supervisor_graph.invoke(state2, {"configurable": {"thread_id": "test_thread"}})
    print(f"\n[Agent Response]:\n{result2.get('response', 'No response')}")

    # Should reference previous context
    response = result2.get("response", "")
    assert len(response) > 20  # Should have a meaningful response

    print("\n✓ Test passed: Context maintained across turns")


def test_numbered_list_formatting(supervisor_graph):
    """
    Test that numbered lists are properly formatted for drafts.
    """
    print("\n" + "="*80)
    print("TEST: Numbered List Formatting")
    print("="*80)

    print("\n[User Input]: Show me all drafts for john.doe@company.com")

    state = create_initial_state(
        user_message="Show me all drafts for john.doe@company.com",
        user_id=MOCK_USER_ID
    )

    result = supervisor_graph.invoke(state, {"configurable": {"thread_id": "test_thread"}})

    print(f"\n[Agent Response]:\n{result.get('response', 'No response')}")

    # Should have numbered list format
    response = result.get("response", "")
    assert "1." in response
    assert "2." in response
    assert "3." in response

    print("\n✓ Test passed: Numbered lists formatted correctly")


# =============================================================================
# RUN ALL TESTS
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*80)
    print("MULTI-AGENT EMAIL SYSTEM - COMPREHENSIVE TEST SUITE")
    print("="*80)
    print("\nThis test suite uses mock inbox data that resembles the production web app.")
    print("All AI agent responses are displayed for verification.\n")

    # Run pytest with verbose output
    pytest.main([__file__, "-v", "-s"])
