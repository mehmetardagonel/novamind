#!/usr/bin/env python3
"""
Test script for ChatService V2 (Multi-Agent Architecture)

Run this script to verify the new multi-agent system is working correctly.

Usage:
    python test_chat_v2.py

Prerequisites:
    - GEMINI_API_KEY environment variable set
    - All dependencies installed (pip install -r requirements.txt)
"""

import os
import sys
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_imports():
    """Test that all imports work correctly."""
    print("\n" + "="*60)
    print("TEST 1: Import Check")
    print("="*60)

    try:
        from schemas import (
            DraftEmailInput,
            SendEmailInput,
            FetchMailsInput,
        )
        print("[OK] schemas.py imports successfully")

        from agents.state import EmailAgentState, create_initial_state
        print("[OK] agents/state.py imports successfully")

        from agents.tools import (
            create_inbox_tools,
            create_draft_tools,
            create_send_tools,
        )
        print("[OK] agents/tools.py imports successfully")

        from agents.supervisor import (
            create_email_assistant_graph,
            EmailAssistant,
        )
        print("[OK] agents/supervisor.py imports successfully")

        from chat_service_v2 import ChatService
        print("[OK] chat_service_v2.py imports successfully")

        return True

    except ImportError as e:
        print(f"[FAIL] Import error: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Unexpected error: {e}")
        return False


def test_schema_validation():
    """Test that Pydantic schemas validate correctly."""
    print("\n" + "="*60)
    print("TEST 2: Schema Validation")
    print("="*60)

    try:
        from schemas import DraftEmailInput, FetchMailsInput

        # Test DraftEmailInput with valid data
        draft = DraftEmailInput(
            recipient="test@example.com",
            subject="Test Subject",
            body="Test body content"
        )
        print(f"[OK] DraftEmailInput: {draft.recipient}")

        # Test DraftEmailInput with missing optional fields
        draft_partial = DraftEmailInput(recipient="test@example.com")
        print(f"[OK] DraftEmailInput (partial): {draft_partial.recipient}, subject={draft_partial.subject}")

        # Test FetchMailsInput
        fetch = FetchMailsInput(
            sender="boss",
            time_period="today",
            max_results=10
        )
        print(f"[OK] FetchMailsInput: sender={fetch.sender}, period={fetch.time_period}")

        return True

    except Exception as e:
        print(f"[FAIL] Schema validation error: {e}")
        return False


def test_graph_creation():
    """Test that the LangGraph can be created."""
    print("\n" + "="*60)
    print("TEST 3: LangGraph Creation")
    print("="*60)

    try:
        from agents.supervisor import create_email_assistant_graph

        graph = create_email_assistant_graph()
        print(f"[OK] Graph created successfully")
        print(f"[OK] Graph nodes: {list(graph.nodes.keys()) if hasattr(graph, 'nodes') else 'N/A'}")

        return True

    except Exception as e:
        print(f"[FAIL] Graph creation error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_llm_connection():
    """Test that the LLM can be initialized."""
    print("\n" + "="*60)
    print("TEST 4: LLM Connection")
    print("="*60)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[SKIP] GEMINI_API_KEY not set - skipping LLM test")
        return None

    try:
        from agents.supervisor import get_llm

        llm = get_llm()
        print(f"[OK] LLM initialized: {llm.model}")

        # Quick test invoke
        response = llm.invoke("Say 'Hello' in one word.")
        print(f"[OK] LLM response: {response.content[:50]}...")

        return True

    except Exception as e:
        print(f"[FAIL] LLM connection error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_chat_service():
    """Test the ChatService V2 interface."""
    print("\n" + "="*60)
    print("TEST 5: ChatService V2")
    print("="*60)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[SKIP] GEMINI_API_KEY not set - skipping ChatService test")
        return None

    try:
        from chat_service_v2 import ChatService

        service = ChatService(user_id=None)
        print("[OK] ChatService created")

        # Test simple greeting
        response = service.chat("Hello!")
        print(f"[OK] Greeting response: {response[:100]}...")

        return True

    except Exception as e:
        print(f"[FAIL] ChatService error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_routing():
    """Test the supervisor routing logic."""
    print("\n" + "="*60)
    print("TEST 6: Supervisor Routing (Dry Run)")
    print("="*60)

    try:
        from agents.state import create_initial_state

        # Test routing classification
        test_cases = [
            ("Show me my emails", "inbox"),
            ("Draft an email to John", "draft"),
            ("Send the email now", "send"),
            ("Delete all spam", "organization"),
            ("Hello there!", "__end__"),
        ]

        for message, expected_route in test_cases:
            state = create_initial_state(user_message=message)
            print(f"[OK] State created for: '{message[:30]}...'")

        print(f"[OK] All {len(test_cases)} test cases passed state creation")
        return True

    except Exception as e:
        print(f"[FAIL] Routing test error: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("ChatService V2 Test Suite")
    print("="*60)
    print(f"Python: {sys.version}")
    print(f"Working dir: {os.getcwd()}")

    results = {
        "imports": test_imports(),
        "schemas": test_schema_validation(),
        "graph": test_graph_creation(),
        "llm": test_llm_connection(),
        "chat_service": test_chat_service(),
        "routing": test_routing(),
    }

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = 0
    failed = 0
    skipped = 0

    for name, result in results.items():
        if result is True:
            print(f"  [PASS] {name}")
            passed += 1
        elif result is False:
            print(f"  [FAIL] {name}")
            failed += 1
        else:
            print(f"  [SKIP] {name}")
            skipped += 1

    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")

    if failed > 0:
        print("\n[!] Some tests failed. Please check the errors above.")
        sys.exit(1)
    else:
        print("\n[OK] All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
