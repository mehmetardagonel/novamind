
import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.supervisor import EmailAssistant

# =============================================================================
# THE INPUTS (Use these to test the agent)
# =============================================================================

TEST_SCENARIOS = {
    "INBOX_OPERATIONS": [
        "List my connected email accounts",
        "Show me my latest 5 emails",
        "Show important emails from yesterday",
        "Find emails from 'john@example.com'",
        "Search for emails about 'project deadline'",
        "Show all my drafts",
        "Show drafts for 'client@example.com'"
    ],
    "DRAFT_OPERATIONS": [
        # Scenario 1: One-shot creation
        "Draft an email to 'bob@example.com' with subject 'Meeting' and body 'Let's meet at 2pm'",
        
        # Scenario 2: Interactive creation (Agent should ask for missing info)
        "Draft an email to 'alice@example.com'", 
        
        # Scenario 3: Update existing draft
        "Update the draft to 'bob@example.com' and change the body to say 'Let's meet at 3pm instead'",
        
        # Scenario 4: Delete draft
        "Delete the draft to 'bob@example.com'"
    ],
    "SEND_OPERATIONS": [
        # Scenario 1: Immediate send
        "Send an email to 'urgent@example.com' saying 'Call me' immediately",
        
        # Scenario 2: Send draft (triggers confirmation flow)
        "Send the draft to 'bob@example.com'",
        # (The next input would be 'Yes' to confirm, but we test single turns here)
    ],
    "ORGANIZATION_OPERATIONS": [
        "Move all emails from 'newsletter@marketing.com' to 'Promotions'",
        "Delete all spam emails"
    ]
}

# =============================================================================
# TEST RUNNER (Simulates the agent processing these inputs)
# =============================================================================

def run_agent_test():
    """
    Runs the agent against the defined inputs with MOCKED tools.
    This shows how the agent interprets the commands without sending real emails.
    """
    print("=== INITIALIZING AGENT (WITH MOCKED BACKEND) ===\n")
    
    # Initialize the assistant
    # We mock the internal tool execution to avoid side effects
    with patch('agents.tools._list_accounts') as mock_list, \
         patch('agents.tools._fetch_mails') as mock_fetch, \
         patch('agents.tools._query_emails') as mock_query, \
         patch('agents.tools._draft_email') as mock_draft, \
         patch('agents.tools._update_draft') as mock_update, \
         patch('agents.tools._get_drafts_for_recipient') as mock_get_drafts, \
         patch('agents.tools._send_email') as mock_send, \
         patch('agents.tools._move_mails') as mock_move, \
         patch('agents.tools._delete_spam') as mock_delete, \
         patch('agents.tools._delete_draft') as mock_delete_draft:

        # --- SETUP MOCK RETURNS ---
        mock_list.return_value = [{"id": "1", "email": "me@test.com", "provider": "gmail"}]
        mock_fetch.return_value = [{"subject": "Test Email", "sender": "sender@test.com", "body": "Hello"}]
        mock_query.return_value = {"emails": [], "insights": "Found some emails."}
        mock_draft.return_value = {"success": True, "message": "Draft created", "draft_id": "d1"}
        mock_update.return_value = {"success": True, "message": "Draft updated"}
        # Return a single draft so we don't get stuck in a selection loop
        mock_get_drafts.return_value = [{"id": "d1", "subject": "Meeting", "date": "2023-01-01"}] 
        mock_send.return_value = {"success": True, "message": "Email sent"}
        mock_move.return_value = {"success": True, "moved_count": 5}
        mock_delete.return_value = {"success": True, "deleted_count": 10}
        mock_delete_draft.return_value = {"success": True}

        assistant = EmailAssistant(user_id="test_user")

        for category, inputs in TEST_SCENARIOS.items():
            print(f"\n--- TESTING {category} ---")
            for user_input in inputs:
                print(f"\nUser Input: \"{user_input}\" ")
                try:
                    # Run the chat
                    response = assistant.chat(user_input)
                    print(f"Agent Response: {response}")
                except Exception as e:
                    print(f"Error: {e}")
            
            # Clear history between categories to keep context clean
            assistant.clear_history()

if __name__ == "__main__":
    run_agent_test()
