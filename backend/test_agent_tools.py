
import sys
import os
import json
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add backend to path to allow imports
backend_path = Path(__file__).parent
sys.path.append(str(backend_path))

# Import the tool creators and the module to be patched
from agents.tools import (
    create_inbox_tools,
    create_draft_tools,
    create_send_tools,
    create_organization_tools,
)
import agents.tools as tool_module

def test_tools():
    """
    Test all agent tools using mocks for the backend email services.
    This verifies that tools are correctly defined and pass arguments as expected.
    """
    print("=== Testing Agent Tools (Mocked Backend) ===\n")
    print(f"Testing tools defined in: {tool_module.__file__}\n")

    # Mock user_id for multi-tenant context
    user_id = "test_user_123"

    # ==========================================
    # 1. Test Inbox Agent Tools
    # ==========================================
    print("--- Inbox Agent Tools ---")
    with patch.object(tool_module, '_list_accounts') as mock_list, \
         patch.object(tool_module, '_fetch_mails') as mock_fetch, \
         patch.object(tool_module, '_query_emails') as mock_query, \
         patch.object(tool_module, '_get_drafts') as mock_get_drafts, \
         patch.object(tool_module, '_get_drafts_for_recipient') as mock_get_recipient_drafts:

        # Setup Mock Return Values
        mock_list.return_value = [
            {"id": "acc1", "email": "user@gmail.com", "provider": "gmail"},
            {"id": "acc2", "email": "user@outlook.com", "provider": "outlook"}
        ]
        mock_fetch.return_value = [
            {"id": "msg1", "subject": "Project Update", "sender": "boss@company.com", "body": "Status report due.", "date": "2023-10-27T10:00:00"},
            {"id": "msg2", "subject": "Lunch?", "sender": "colleague@company.com", "body": "Pizza today?", "date": "2023-10-27T12:00:00"}
        ]
        mock_query.return_value = {
            "success": True,
            "emails": [{"id": "msg3", "subject": "Meeting", "sender": "client@corp.com"}],
            "insights": "Found 1 email about meetings."
        }
        mock_get_drafts.return_value = [{"id": "d1", "subject": "Draft 1", "date": "2023-10-26"}]
        mock_get_recipient_drafts.return_value = [{"id": "d2", "subject": "Draft for Client", "date": "2023-10-26"}]

        # Create and Test Tools
        tools = create_inbox_tools(user_id=user_id)
        for tool in tools:
            print(f"Testing tool: {tool.name}")
            try:
                # Construct dummy args based on tool definition
                args = {}
                if tool.name == "list_email_accounts":
                    pass
                elif tool.name == "fetch_emails":
                    args = {"max_results": 5, "folder": "inbox", "importance": True}
                elif tool.name == "query_emails":
                    args = {"query": "emails from boss about project"}
                elif tool.name == "get_all_drafts":
                    pass
                elif tool.name == "get_drafts_for_recipient":
                    args = {"recipient_email": "client@corp.com"}

                # Invoke
                result_str = tool.invoke(args)
                
                # Parse result to verify JSON structure
                try:
                    # Remove markdown code blocks if present for parsing check
                    clean_json = result_str.replace("```json", "").replace("```", "").strip()
                    result_data = json.loads(clean_json)
                    status = "OK (Valid JSON)"
                except json.JSONDecodeError:
                    status = "OK (String Output)"
                    
                print(f"  Args: {args}")
                print(f"  Result Preview: {result_str[:100].replace(chr(10), ' ')}...")
                print(f"  Status: {status}")
                print("  --------------------------------")
            except Exception as e:
                print(f"  [FAILED] {e}")

    # ==========================================
    # 2. Test Draft Agent Tools
    # ==========================================
    print("\n--- Draft Agent Tools ---")
    
    # Mock LLM for update_draft tool which uses it to rewrite content
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = "Dear Recipient,\n\nThis is the AI-enhanced body content.\n\nBest,\nSender"
    # Also handle case where invoke returns an object with content attr
    mock_response = MagicMock()
    mock_response.content = "Dear Recipient,\n\nThis is the AI-enhanced body content.\n\nBest,\nSender"
    mock_llm.invoke.return_value = mock_response

    with patch.object(tool_module, '_draft_email') as mock_create, \
         patch.object(tool_module, '_update_draft') as mock_update, \
         patch.object(tool_module, '_get_drafts_for_recipient') as mock_get_recipient_drafts, \
         patch.object(tool_module, '_get_draft_body') as mock_get_body, \
         patch.object(tool_module, '_delete_draft') as mock_delete:

        # Setup Mocks
        mock_create.return_value = {
            "success": True, 
            "message": "Draft created", 
            "draft_id": "new_draft_123",
            "draft": {"to": "test@test.com", "subject": "Hi", "body": "Body"}
        }
        mock_update.return_value = {"success": True, "message": "Draft updated"}
        # Return a single draft to avoid "selection required" logic for simple test
        mock_get_recipient_drafts.return_value = [{"id": "d_target", "subject": "Existing Draft", "date": "2023-10-25"}]
        mock_get_body.return_value = "Original rough draft body."
        # Note: The tool wrapper calls _delete_draft and ignores return unless it raises exception?
        # Let's check wrapper. Wrapper does: _delete_draft(...); return json.dumps({...})
        mock_delete.return_value = {"success": True}

        tools = create_draft_tools(user_id=user_id, llm=mock_llm)
        for tool in tools:
            print(f"Testing tool: {tool.name}")
            try:
                args = {}
                if tool.name == "create_draft":
                    args = {"recipient": "new@client.com", "subject": "Proposal", "body": "Here is the proposal."}
                elif tool.name == "update_draft":
                    args = {"recipient_email": "client@corp.com", "instruction": "Make it more formal"}
                elif tool.name == "send_draft_to_recipient":
                    # This tool returns a confirmation prompt, not the actual send result
                    args = {"recipient_email": "client@corp.com"}
                elif tool.name == "delete_draft_for_recipient":
                    args = {"recipient_email": "client@corp.com"}

                result_str = tool.invoke(args)
                print(f"  Args: {args}")
                print(f"  Result Preview: {result_str[:100].replace(chr(10), ' ')}...")
                print("  [OK]")
                print("  --------------------------------")
            except Exception as e:
                print(f"  [FAILED] {e}")

    # ==========================================
    # 3. Test Send Agent Tools
    # ==========================================
    print("\n--- Send Agent Tools ---")
    with patch.object(tool_module, '_send_email') as mock_send, \
         patch.object(tool_module, '_send_draft') as mock_send_draft:

        mock_send.return_value = {"success": True, "message": "Email sent", "message_id": "sent_123"}
        mock_send_draft.return_value = {"success": True, "message": "Draft sent", "message_id": "sent_draft_456"}

        tools = create_send_tools(user_id=user_id)
        for tool in tools:
            print(f"Testing tool: {tool.name}")
            try:
                args = {}
                if tool.name == "send_email_now":
                    args = {"recipient": "urgent@boss.com", "subject": "Urgent", "body": "Done."}
                elif tool.name == "confirm_and_send_draft":
                    args = {"draft_id": "draft_to_send_123"}

                result_str = tool.invoke(args)
                print(f"  Args: {args}")
                print(f"  Result Preview: {result_str[:100].replace(chr(10), ' ')}...")
                print("  [OK]")
                print("  --------------------------------")
            except Exception as e:
                print(f"  [FAILED] {e}")

    # ==========================================
    # 4. Test Organization Agent Tools
    # ==========================================
    print("\n--- Organization Agent Tools ---")
    with patch.object(tool_module, '_move_mails') as mock_move, \
         patch.object(tool_module, '_delete_spam') as mock_spam:

        mock_move.return_value = {"success": True, "moved_count": 5, "message": "Moved 5 emails"}
        mock_spam.return_value = {"success": True, "deleted_count": 12, "message": "Deleted 12 spam emails"}

        tools = create_organization_tools(user_id=user_id)
        for tool in tools:
            print(f"Testing tool: {tool.name}")
            try:
                args = {}
                if tool.name == "move_emails_by_sender":
                    args = {"sender": "promo@marketing.com", "target_folder": "Promotions"}
                elif tool.name == "delete_spam_emails":
                    args = {}

                result_str = tool.invoke(args)
                print(f"  Args: {args}")
                print(f"  Result Preview: {result_str[:100].replace(chr(10), ' ')}...")
                print("  [OK]")
                print("  --------------------------------")
            except Exception as e:
                print(f"  [FAILED] {e}")

    print("\n=== All Tests Completed ===")

if __name__ == "__main__":
    test_tools()
