# session_store.py
from typing import Dict
from chat_service import ChatService
import asyncio

# Shared session store for BOTH /chat and /voice/chat
chat_sessions: Dict[str, ChatService] = {}
chat_session_locks: Dict[str, asyncio.Lock] = {}
