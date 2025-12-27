"""
ChatService V2 - Multi-Agent Email Assistant

This module provides a drop-in replacement for the original ChatService,
using the new LangGraph-based multi-agent architecture for improved
reliability and reduced hallucinations.

Key Improvements:
1. Multi-agent architecture isolates tools to prevent confusion
2. Pydantic schemas replace fragile pipe-separated strings
3. Interactive draft flow handles missing information gracefully
4. Proper state management for multi-turn conversations
5. Compatible with Gemini 2.0 Flash (avoids Gemini 3 thought_signature issues)
"""

import os
import json
import logging
from typing import Optional
from datetime import datetime

# Set protobuf to use pure Python implementation for compatibility
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

from agents.supervisor import EmailAssistant, get_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChatService:
    """
    Multi-agent email assistant service.

    This is a drop-in replacement for the original ChatService that uses
    the new LangGraph-based architecture with specialized agents.

    Usage:
        service = ChatService(user_id="user123")
        response = service.chat("Show me my latest emails")
    """

    def __init__(self, user_id: Optional[str] = None):
        """
        Initialize the chat service.

        Args:
            user_id: User ID for multi-account support.
                     If None, falls back to legacy token.json.
        """
        self.user_id = user_id
        self._assistant = EmailAssistant(user_id=user_id)
        self.last_result = None

        # For backward compatibility
        self.pending_selection = None
        self.chat_history = []

        logger.info(f"ChatService V2 initialized for user: {user_id or 'default'}")

    def chat(self, user_message: str, context: str = "") -> str:
        """
        Process a user message and return the assistant's response.

        This method provides the same interface as the original ChatService
        for backward compatibility.

        Args:
            user_message: The user's input message
            context: Optional additional context (e.g., from RAG)

        Returns:
            The assistant's response string
        """
        try:
            if not user_message or not user_message.strip():
                return "Please provide a message to get started."

            # Extract raw message if RAG context is prepended
            raw_message = self._extract_raw_user_message(user_message)

            # Use the multi-agent assistant
            response = self._assistant.chat(raw_message, context)
            self.last_result = getattr(self._assistant, "last_result", None)

            # Update legacy chat history for compatibility
            self._update_legacy_history(raw_message, response)

            return response

        except Exception as e:
            logger.error(f"Chat error: {e}", exc_info=True)
            return f"Sorry, I encountered an error processing your request: {str(e)}"

    def _extract_raw_user_message(self, user_message: str) -> str:
        """Extract the actual user text when RAG context is prepended."""
        if not user_message:
            return ""

        marker = "User message:"
        if marker in user_message:
            return user_message.split(marker, 1)[1].strip()
        return user_message.strip()

    def _update_legacy_history(self, user_text: str, assistant_text: str) -> None:
        """Update legacy chat history for backward compatibility."""
        try:
            from langchain_core.messages import HumanMessage, AIMessage

            if user_text and user_text.strip():
                self.chat_history.append(HumanMessage(content=user_text.strip()))

            assistant_clean = (assistant_text or "").strip()
            if assistant_clean:
                # Remove code blocks from history to save context
                import re
                assistant_clean = re.sub(r"```[\s\S]*?```", "", assistant_clean).strip()
                self.chat_history.append(AIMessage(content=assistant_clean[:2000]))

            # Keep history manageable
            max_history = 12
            if len(self.chat_history) > max_history:
                self.chat_history = self.chat_history[-max_history:]

        except Exception:
            pass  # History is best-effort

    def clear_history(self):
        """Clear conversation history."""
        self.chat_history = []
        self._assistant.clear_history()


# =============================================================================
# Factory Function
# =============================================================================

def create_chat_service(user_id: Optional[str] = None) -> ChatService:
    """
    Factory function to create a ChatService instance.

    Args:
        user_id: Optional user ID for multi-account support

    Returns:
        ChatService instance
    """
    return ChatService(user_id=user_id)


# =============================================================================
# Backward Compatibility Layer
# =============================================================================

class LegacyChatServiceAdapter(ChatService):
    """
    Adapter that provides full backward compatibility with the original
    ChatService interface, including deprecated methods and attributes.

    Use this if you need access to internal methods like:
    - _parse_fetch_mails
    - _format_email_list_json_block
    - _maybe_handle_summary_request
    """

    def __init__(self, user_id: Optional[str] = None):
        super().__init__(user_id=user_id)

        # Initialize LLM for direct use
        self.llm = get_llm()

        # Import legacy tools for compatibility
        try:
            from email_tools import (
                fetch_mails,
                list_email_accounts,
                query_emails,
            )
            self._fetch_mails = fetch_mails
            self._list_accounts = list_email_accounts
            self._query_emails = query_emails
        except ImportError as e:
            logger.warning(f"Could not import legacy tools: {e}")

    def _parse_fetch_mails(self, input_str) -> dict:
        """Legacy method for parsing fetch_mails input."""
        if not hasattr(self, '_fetch_mails'):
            return {"error": "fetch_mails not available"}

        try:
            if isinstance(input_str, dict):
                filters = input_str
            elif isinstance(input_str, str) and input_str.strip().startswith("{"):
                filters = json.loads(input_str)
            else:
                filters = {}

            return self._fetch_mails(**filters, user_id=self.user_id)
        except Exception as e:
            return {"error": str(e)}

    def _format_email_list_json_block(self, emails: list) -> str:
        """Legacy method for formatting email list as JSON block."""
        emails_for_json = []
        for email in emails:
            try:
                e_copy = email.copy() if isinstance(email, dict) else email
                if isinstance(e_copy, dict) and "body" in e_copy:
                    if e_copy["body"] and len(e_copy["body"]) > 200:
                        e_copy["body"] = e_copy["body"][:200] + "..."
                emails_for_json.append(e_copy)
            except Exception:
                emails_for_json.append(email)

        class DateTimeEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return super().default(obj)

        json_str = json.dumps(emails_for_json, indent=2, cls=DateTimeEncoder)
        return f"```json\n{json_str}\n```"

    def _maybe_handle_summary_request(self, raw_user_message: str) -> Optional[str]:
        """Legacy method for handling summary requests."""
        # Delegate to the multi-agent system
        return None  # Let the multi-agent handle it

    def _maybe_handle_direct_inbox_fetch(self, raw_user_message: str) -> Optional[str]:
        """Legacy method for handling direct inbox fetches."""
        # Delegate to the multi-agent system
        return None  # Let the multi-agent handle it
