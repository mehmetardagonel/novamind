"""
RAG Service - 0 Cost AI Email Search using Local Embeddings

Uses sentence-transformers (all-MiniLM-L6-v2) for free, local CPU embeddings.
Model is ~80MB and downloads automatically on first run.
"""

import os
import logging
from typing import List, Dict, Optional
from datetime import datetime

from sentence_transformers import SentenceTransformer
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# By default, do NOT store email embeddings (user requested).
# Chat-memory embeddings remain enabled.
EMAIL_EMBEDDINGS_ENABLED = os.getenv("ENABLE_EMAIL_EMBEDDINGS", "false").lower() in (
    "1",
    "true",
    "yes",
    "on",
)

# Free and fast embedding model
# Downloads automatically on first run (~80MB)
# No API keys required, runs locally on CPU
_model = None

def get_embedding_model() -> SentenceTransformer:
    """Lazy load the embedding model to avoid startup delays."""
    global _model
    if _model is None:
        logger.info("Loading embedding model (all-MiniLM-L6-v2)...")
        _model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Embedding model loaded successfully!")
    return _model


def generate_embedding(text: str) -> List[float]:
    """
    Convert text into a 384-dimensional vector.

    Args:
        text: The text to convert to embedding

    Returns:
        List of 384 floats representing the text embedding
    """
    model = get_embedding_model()
    # Truncate text if too long (model handles ~256 tokens effectively)
    # Taking first 1000 characters as safe approximation
    truncated_text = text[:1000] if len(text) > 1000 else text
    return model.encode(truncated_text).tolist()

def _is_memory_query(query: str) -> bool:
    q = (query or "").lower()
    keywords = [
        "remember",
        "previous",
        "prior",
        "earlier",
        "last time",
        "our conversation",
        "prior convo",
        "previous convo",
        "previous conversation",
        "previous chat",
        "what did i ask",
        "what have i asked",
        # Turkish keywords
        "hatırl",
        "hatir",
        "önce",
        "once",
        "önceki",
        "onceki",
        "daha önce",
        "sohbet",
        "konuştuk",
        "konustuk",
    ]
    return any(k in q for k in keywords)


async def store_email_embedding(user_id: str, email_data: Dict) -> Optional[Dict]:
    """
    Convert an email to a vector and store it in the database.

    Args:
        user_id: The user's ID (from Supabase auth)
        email_data: Dictionary containing email fields:
            - id: Email message ID
            - subject: Email subject
            - snippet/body: Email body preview or full body
            - from/sender: Sender email/name
            - date: Email date

    Returns:
        The stored embedding record or None if failed
    """
    try:
        if not EMAIL_EMBEDDINGS_ENABLED:
            return None

        # Combine content for embedding (Subject + Body)
        subject = email_data.get('subject', '')
        body = email_data.get('snippet') or email_data.get('body', '')
        content = f"Subject: {subject}\nBody: {body}"

        # Generate embedding vector
        vector = generate_embedding(content)

        # Prepare metadata
        metadata = {
            "subject": subject,
            "from": email_data.get('from') or email_data.get('sender', ''),
            "date": str(email_data.get('date', '')),
            "account_id": email_data.get('account_id'),
            "provider": email_data.get('provider', 'gmail')
        }

        data = {
            "user_id": user_id,
            "email_id": email_data.get('id') or email_data.get('message_id'),
            "content": content[:2000],  # Limit content stored
            "metadata": metadata,
            "embedding": vector
        }

        # Upsert to handle duplicates
        result = supabase.table("email_embeddings")\
            .upsert(data, on_conflict="user_id,email_id")\
            .execute()

        logger.debug(f"Stored embedding for email {data['email_id']}")
        return result.data[0] if result.data else None

    except Exception as e:
        logger.error(f"Error storing embedding for email {email_data.get('id')}: {e}")
        return None


async def store_emails_batch(user_id: str, emails: List[Dict]) -> int:
    """
    Store embeddings for multiple emails.

    Args:
        user_id: The user's ID
        emails: List of email dictionaries

    Returns:
        Number of successfully stored embeddings
    """
    if not EMAIL_EMBEDDINGS_ENABLED:
        return 0

    success_count = 0
    for email in emails:
        result = await store_email_embedding(user_id, email)
        if result:
            success_count += 1

    logger.info(f"Stored {success_count}/{len(emails)} email embeddings for user {user_id}")
    return success_count


async def search_relevant_emails(
    user_id: str,
    query: str,
    limit: int = 5,
    threshold: float = 0.5
) -> List[Dict]:
    """
    Find the most relevant emails for a user's query using vector similarity.

    Args:
        user_id: The user's ID (ensures users only search their own emails)
        query: The search query text
        limit: Maximum number of results to return
        threshold: Minimum similarity score (0-1)

    Returns:
        List of relevant emails with similarity scores
    """
    try:
        # If we are not storing embeddings, email RAG will be empty (chat-memory RAG still works).
        if not EMAIL_EMBEDDINGS_ENABLED:
            return []

        # Convert query to vector
        query_vector = generate_embedding(query)

        # Call Supabase RPC function for vector search
        # This function must be created in Supabase (see SQL in plan)
        response = supabase.rpc(
            "match_emails",
            {
                "query_embedding": query_vector,
                "match_threshold": threshold,
                "match_count": limit,
                "p_user_id": user_id
            }
        ).execute()

        results = response.data or []
        logger.info(f"Found {len(results)} relevant emails for query: '{query[:50]}...'")
        return results

    except Exception as e:
        logger.error(f"Error searching emails: {e}")
        return []


async def delete_email_embedding(user_id: str, email_id: str) -> bool:
    """
    Delete an email's embedding when email is deleted.

    Args:
        user_id: The user's ID
        email_id: The email message ID

    Returns:
        True if deleted, False otherwise
    """
    try:
        result = supabase.table("email_embeddings")\
            .delete()\
            .eq("user_id", user_id)\
            .eq("email_id", email_id)\
            .execute()

        return len(result.data) > 0 if result.data else False

    except Exception as e:
        logger.error(f"Error deleting embedding for email {email_id}: {e}")
        return False


async def store_chat_embedding(
    user_id: str,
    session_id: str,
    role: str,
    content: str,
    message_id: str,
) -> Optional[Dict]:
    """
    Store a chat message embedding for conversation RAG.
    Requires a `chat_embeddings` table in Supabase (see SQL in README/notes).
    """
    try:
        if not content:
            return None

        vector = generate_embedding(content)

        data = {
            "id": message_id,
            "user_id": user_id,
            "session_id": session_id,
            "role": role,
            "content": content[:2000],
            "metadata": {
                "role": role,
                "session_id": session_id,
                "created_at": datetime.utcnow().isoformat(),
            },
            "embedding": vector,
        }

        result = (
            supabase.table("chat_embeddings")
            .upsert(data, on_conflict="id")
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error storing chat embedding: {e}")
        return None


async def search_relevant_chat_messages(
    user_id: str,
    query: str,
    limit: int = 6,
    threshold: float = 0.4,
) -> List[Dict]:
    """
    Search relevant chat messages using vector similarity.
    Requires `match_chat_messages` RPC in Supabase.
    """
    try:
        query_vector = generate_embedding(query)
        response = supabase.rpc(
            "match_chat_messages",
            {
                "query_embedding": query_vector,
                "match_threshold": threshold,
                "match_count": limit,
                "p_user_id": user_id,
            },
        ).execute()

        results = response.data or []
        return results
    except Exception as e:
        logger.error(f"Error searching chat messages: {e}")
        return []

async def fetch_recent_chat_messages(
    user_id: str,
    session_id: Optional[str] = None,
    limit: int = 12,
) -> List[Dict]:
    """Fetch the most recent chat messages for a user (optionally per session)."""
    try:
        q = (
            supabase.table("chat_embeddings")
            .select("id,user_id,session_id,role,content,metadata,created_at")
            .eq("user_id", user_id)
        )
        if session_id:
            q = q.eq("session_id", session_id)
        res = q.order("created_at", desc=True).limit(limit).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Error fetching recent chat messages: {e}")
        return []

async def get_chat_memory_context(
    user_id: str,
    query: str,
    limit: int = 4,
    session_id: Optional[str] = None,
) -> str:
    """Return formatted relevant chat snippets for prompt injection."""
    try:
        # If user explicitly asks about prior conversation, use recent chat history
        # instead of similarity search (generic queries often don't match well).
        if _is_memory_query(query):
            used_session_scope = bool(session_id)
            recent = await fetch_recent_chat_messages(
                user_id=user_id,
                session_id=session_id,
                limit=max(limit * 3, 10),
            )
            # If this is a brand-new session (no stored messages yet), fall back to
            # the user's most recent chats so we can still answer "what did I ask before?"
            if not recent and session_id:
                used_session_scope = False
                recent = await fetch_recent_chat_messages(
                    user_id=user_id,
                    session_id=None,
                    limit=max(limit * 3, 10),
                )
            if not recent:
                return ""

            recent = list(reversed(recent))  # chronological for readability
            header = (
                "Here are the most recent messages from this chat:\n"
                if used_session_scope
                else "Here are the most recent messages from your chats:\n"
            )
            parts = [header]
            for row in recent:
                role = row.get("role") or (row.get("metadata", {}) or {}).get("role") or "unknown"
                content = (row.get("content") or "").strip()
                if len(content) > 260:
                    content = content[:260] + "..."
                parts.append(f"- {role}: {content}")
            return "\n".join(parts)

        raw_limit = max(limit * 4, 12) if session_id else limit
        matches = await search_relevant_chat_messages(user_id, query, limit=raw_limit)
        if session_id:
            matches = [
                m
                for m in matches
                if (m.get("session_id") == session_id)
                or ((m.get("metadata", {}) or {}).get("session_id") == session_id)
            ]
        matches = matches[:limit]
        if not matches:
            return ""

        parts = ["Here are relevant snippets from your previous chats:\n"]
        for i, row in enumerate(matches, 1):
            md = row.get("metadata", {}) or {}
            role = md.get("role") or "unknown"
            similarity = row.get("similarity", 0)
            content = (row.get("content") or "").strip()
            if len(content) > 300:
                content = content[:300] + "..."
            parts.append(f"{i}. ({role}, relevance {similarity:.0%}) {content}")

        return "\n".join(parts)
    except Exception as e:
        logger.error(f"Error building chat memory context: {e}")
        return ""


async def get_context_for_chat(user_id: str, query: str, limit: int = 3) -> str:
    """
    Get relevant email context for AI chat responses.
    Returns formatted context string for LLM prompts.

    Args:
        user_id: The user's ID
        query: The user's question/query
        limit: Number of relevant emails to include

    Returns:
        Formatted context string with relevant emails
    """
    try:
        relevant_emails = await search_relevant_emails(user_id, query, limit=limit)

        if not relevant_emails:
            return ""

        context_parts = ["Here are relevant emails from your inbox:\n"]

        for i, email in enumerate(relevant_emails, 1):
            metadata = email.get('metadata', {})
            similarity = email.get('similarity', 0)

            context_parts.append(f"""
Email {i} (Relevance: {similarity:.0%}):
From: {metadata.get('from', 'Unknown')}
Subject: {metadata.get('subject', 'No subject')}
Date: {metadata.get('date', 'Unknown')}
Content: {email.get('content', '')[:500]}...
---""")

        return "\n".join(context_parts)

    except Exception as e:
        logger.error(f"Error getting chat context: {e}")
        return ""


# Singleton instance for easy import
class RAGService:
    """Singleton RAG Service for email + chat search."""

    def __init__(self):
        self._initialized = False

    def initialize(self):
        """Pre-load the embedding model."""
        if not self._initialized:
            get_embedding_model()
            self._initialized = True
            logger.info("RAG Service initialized")

    async def index_email(self, user_id: str, email: Dict) -> bool:
        """Index a single email."""
        result = await store_email_embedding(user_id, email)
        return result is not None

    async def index_emails(self, user_id: str, emails: List[Dict]) -> int:
        """Index multiple emails."""
        return await store_emails_batch(user_id, emails)

    async def search(self, user_id: str, query: str, limit: int = 5) -> List[Dict]:
        """Search for relevant emails."""
        return await search_relevant_emails(user_id, query, limit)

    async def get_chat_context(self, user_id: str, query: str) -> str:
        """Get context for AI chat."""
        return await get_context_for_chat(user_id, query)

    async def get_chat_memory_context(self, user_id: str, query: str, session_id: Optional[str] = None) -> str:
        """Get relevant chat snippets for AI chat."""
        return await get_chat_memory_context(user_id, query, session_id=session_id)

    async def get_combined_context(self, user_id: str, query: str, session_id: Optional[str] = None) -> str:
        """Get chat-memory RAG context only (email RAG removed - using direct API)."""
        chat_ctx = await get_chat_memory_context(user_id, query, limit=4, session_id=session_id)
        return chat_ctx.strip()

    async def index_chat_message(self, user_id: str, session_id: str, role: str, content: str, message_id: str) -> bool:
        """Index a single chat message."""
        result = await store_chat_embedding(
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            message_id=message_id,
        )
        return result is not None

    async def remove_email(self, user_id: str, email_id: str) -> bool:
        """Remove email from index."""
        return await delete_email_embedding(user_id, email_id)


# Global instance
rag_service = RAGService()
