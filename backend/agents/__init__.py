"""
Multi-Agent Email Assistant using LangGraph.

This module implements a supervisor-based multi-agent architecture that routes
user requests to specialized agents, eliminating tool confusion and improving
reliability.
"""

from .supervisor import create_email_assistant_graph
from .state import EmailAgentState, ConversationMessage

__all__ = [
    "create_email_assistant_graph",
    "EmailAgentState",
    "ConversationMessage",
]
