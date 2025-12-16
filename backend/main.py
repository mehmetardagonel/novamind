# Set protobuf to use pure Python implementation for Python 3.14 compatibility
# This MUST be done before any protobuf-using modules are imported
import os
os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'

from typing import List, Dict, Optional
import uuid
import asyncio
from datetime import datetime
from supabase import create_client, Client

from fastapi import FastAPI, Depends, HTTPException, Request, Header, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from dotenv import load_dotenv
from urllib.parse import urlsplit
from google_auth_oauthlib.flow import Flow
from pydantic import BaseModel

from models import (
    EmailOut,
    EmailRequest,
    LabelOut,
    LabelCreate,
    LabelUpdateRequest,
    GmailAccountOut,
    EmailAccountOut,
)
from filters import EmailFilters
# Import our refactored service and its config
from gmail_service import (
    fetch_messages,
    send_email,
    get_current_user_email,
    fetch_drafts,
    fetch_messages_by_label,
    trash_message,
    untrash_message,
    set_star,
    revoke_gmail_token,
    list_labels as gmail_list_labels,
    create_label as gmail_create_label,
    delete_label as gmail_delete_label,
    modify_message_labels,
    get_gmail_service,
    get_user_gmail_service,
    fetch_messages_with_service,
    # Multi-account functions
    fetch_messages_multi_account,
    fetch_messages_by_label_multi,
    fetch_drafts_multi,
    trash_message_multi,
    untrash_message_multi,
    set_star_multi,
    modify_message_labels_multi,
    list_labels_multi,
    create_label_multi,
    delete_label_multi,
    CLIENT_CONFIG,
    SCOPES
)
# Import AI Chat Service
from chat_service import ChatService
# Import ML Service
from ml_service import get_classifier
# Import Gmail Account Service
from gmail_account_service import gmail_account_service

# Import new unified services
from email_account_service import email_account_service
from outlook_service import outlook_service
from rag_service import rag_service

import logging

# Fix: Enable nested event loop for asyncio.run() calls in sync context
import nest_asyncio
nest_asyncio.apply()


# Email indexing removed - using direct Gmail API for email queries
# Only chat memory RAG is used for conversation history


async def _store_chat_embedding_background(user_id: str, session_id: str, role: str, content: str, message_id: str) -> None:
    try:
        await rag_service.index_chat_message(
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            message_id=message_id,
        )
    except Exception as e:
        logger.error(f"Background chat embedding failed for user {user_id}: {e}")


def _schedule_store_chat_embedding(user_id: str, session_id: str, role: str, content: str, message_id: str) -> None:
    try:
        asyncio.create_task(_store_chat_embedding_background(user_id, session_id, role, content, message_id))
    except Exception as e:
        logger.error(f"Failed to schedule chat embedding for user {user_id}: {e}")


def apply_ml_classification(emails: List[EmailOut]) -> List[EmailOut]:
    """
    Apply ML classification to a list of emails.
    Returns classified emails, or original emails if ML fails.
    """
    if not emails:
        return emails

    try:
        classifier = get_classifier()
        emails_dict = [email.model_dump(mode='json') for email in emails]
        classified_emails = classifier.classify_batch(emails_dict)
        logger.info(f"Successfully classified {len(classified_emails)} emails")
        return classified_emails
    except Exception as ml_error:
        logger.warning(f"ML classification failed: {ml_error}. Returning emails without classification.")
        return emails

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# Initialize Supabase client for chat history persistence
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()

# Get redirect URI and frontend URL from config/env
# This ensures it matches your .env file
REDIRECT_URI = CLIENT_CONFIG["installed"]["redirect_uris"][0]

# FRONTEND_URL can be provided as either an origin (recommended) or an origin+path.
# We normalize to an origin for CORS and compute the /app base for redirects.
_frontend_url_raw = os.getenv("FRONTEND_URL", "http://localhost:5173")
_frontend_split = urlsplit(_frontend_url_raw)
FRONTEND_ORIGIN = (
    f"{_frontend_split.scheme}://{_frontend_split.netloc}"
    if _frontend_split.scheme and _frontend_split.netloc
    else _frontend_url_raw.rstrip("/")
)
FRONTEND_APP_URL = f"{FRONTEND_ORIGIN}/app"

origins = [
    "http://localhost:5173",  # Vite dev server default
    "http://localhost:5179",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5179",
    "http://127.0.0.1:3000"
]

if FRONTEND_ORIGIN not in origins:
    origins.append(FRONTEND_ORIGIN)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session management for ChatService instances
# Each user/session gets its own ChatService instance to maintain pending_selection state
chat_sessions: Dict[str, ChatService] = {}
chat_session_locks: Dict[str, asyncio.Lock] = {}

# Startup event to preload ML models
@app.on_event("startup")
async def startup_event():
    """
    Preload ML models and initialize services on server startup.
    """
    logger.info("=" * 60)
    logger.info("Starting Novamind Backend Server...")
    logger.info("=" * 60)

    try:
        logger.info("Loading ML classification models...")
        classifier = get_classifier()
        logger.info("ML Classifier initialized successfully!")
    except Exception as e:
        logger.error(f"Failed to initialize ML classifier: {str(e)}")
        logger.warning("Server will use rule-based classification as fallback")

    try:
        logger.info("Loading RAG embedding model...")
        rag_service.initialize()
        logger.info("RAG Service initialized successfully!")
    except Exception as e:
        logger.error(f"Failed to initialize RAG service: {str(e)}")
        logger.warning("AI search will be unavailable")

    # Check Outlook configuration
    if outlook_service.is_configured:
        logger.info("Outlook integration: ENABLED")
    else:
        logger.info("Outlook integration: DISABLED (missing credentials)")

    logger.info("=" * 60)

# Chat Request/Response Models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None  # Optional session ID, generated if not provided

class ChatResponse(BaseModel):
    response: str
    session_id: str  # Return session ID to client


@app.get("/read-email", response_model=List[EmailOut])
async def get_emails(
    user_id: str = Header(..., alias="X-User-Id"),
    filters: EmailFilters = Depends()
):
    """
    Fetch emails using Gmail API with ML classification.
    Multi-account support: fetches from all connected accounts and merges results.
    """
    logger.info(f"Endpoint called: /read-email for user {user_id} with filters: {filters}")
    try:
        query = filters.to_gmail_query()

        if query:
            query = f"in:inbox {query}"
        else:
            query = "in:inbox"

        emails = await fetch_messages_multi_account(user_id, query, max_per_account=25)

        # Apply ML classification to all emails
        try:
            classifier = get_classifier()
            emails_dict = [email.model_dump(mode='json') for email in emails]
            classified_emails = classifier.classify_batch(emails_dict)
            logger.info(f"Successfully fetched and classified {len(emails)} emails")
            return classified_emails
        except Exception as ml_error:
            logger.warning(f"ML classification failed: {ml_error}. Returning emails without classification.")
            return emails

    except Exception as e:
        logger.error(f"Error in /read-email: {str(e)}")
        # Catch the specific error from gmail_service.py
        if str(e) == "AUTH_REQUIRED":
            # Create the Auth Flow using the imported config
            flow = Flow.from_client_config(
                CLIENT_CONFIG,
                scopes=SCOPES
            )
            # Set the redirect_uri to match your config
            flow.redirect_uri = REDIRECT_URI
            
            # Generate the URL for the user to visit
            auth_url, _ = flow.authorization_url(prompt='consent')
            
            logger.info("Auth required, returning 401 with auth_url")
            # Return 401 (Unauthorized) with the auth_url
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required", "auth_url": auth_url}
            )
        
        # Raise other errors normally
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/gmail/auth/status")
async def get_auth_status():
    """
    Check if the user is authenticated with Gmail.
    Returns JSON with authenticated status and email address.
    """
    logger.info("Endpoint called: /gmail/auth/status")
    try:
        # Try to get the current user's email
        # This will trigger the token validation logic in gmail_service
        email = get_current_user_email()
        return {"authenticated": True, "email": email}
    except Exception as e:
        logger.warning(f"Auth check failed: {str(e)}")
        return {"authenticated": False, "email": None}


@app.get("/auth/callback")
async def auth_callback(code: str, state: Optional[str] = None):
    """
    OAuth callback - saves token to database (multi-account) or token.json (legacy).
    State parameter contains user_id for multi-account flow.
    """
    logger.info("Endpoint called: /auth/callback")

    try:
        import json

        # Check if this is a multi-account flow (state contains user_id)
        user_id = None
        if state:
            try:
                state_data = json.loads(state)
                user_id = state_data.get("user_id")
            except:
                pass

        flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
        flow.redirect_uri = REDIRECT_URI
        flow.fetch_token(code=code)
        creds = flow.credentials

        if user_id:
            # Multi-account flow: save to database
            service = get_gmail_service(credentials=creds)
            profile = service.users().getProfile(userId="me").execute()
            email_address = profile.get("emailAddress")

            saved = await gmail_account_service.save_account(
                user_id=user_id,
                email_address=email_address,
                credentials=creds
            )

            logger.info(f"Connected Gmail account {email_address} for user {user_id}")
            return RedirectResponse(url=f"{FRONTEND_APP_URL}/accounts?connected={email_address}&provider=gmail")
        else:
            # Legacy flow: save to token.json (backward compatibility)
            with open("token.json", "w") as token:
                token.write(creds.to_json())

            logger.info("Successfully exchanged code for token and saved to token.json")
            return RedirectResponse(url=FRONTEND_APP_URL)

    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        return RedirectResponse(url=f"{FRONTEND_APP_URL}/accounts?error=connection_failed&provider=gmail")


@app.post("/send-email")
async def send_email_endpoint(req: EmailRequest):
    """
    Send an email using Gmail API.
    """
    logger.info(f"Endpoint called: /send-email with subject: '{req.subject}' to: '{req.to}'")
    try:
        sender_email = get_current_user_email()
        result = send_email(
            sender=sender_email or "me",
            to=req.to,
            subject=req.subject,
            body=req.body,
        )
        logger.info(f"Email sent successfully. Message ID: {result.get('id')}")
        return {
            "status": "sent",
            "message_id": result.get("id"),
        }
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        # Handle auth error here too
        if str(e) == "AUTH_REQUIRED":
            # This shouldn't happen if /read-email was called first,
            # but it's good practice.
             raise HTTPException(status_code=401, detail="Authentication required")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/logout")
async def logout_endpoint():
    """
    Logout endpoint that cleans up all session data:
    1. Revokes Gmail OAuth token with Google API
    2. Deletes token.json file
    3. Clears in-memory chat sessions

    This endpoint is idempotent and always returns 200 OK, even if cleanup fails.
    The frontend can safely call this multiple times without errors.

    Returns:
        JSONResponse with cleanup status and details
    """
    logger.info("Endpoint called: /logout")

    cleanup_status = {
        "gmail_token_revoked": False,
        "chat_sessions_cleared": False,
        "sessions_cleared_count": 0,
        "message": ""
    }

    try:
        # Step 1: Revoke and delete Gmail OAuth token
        token_revoked = revoke_gmail_token("token.json")
        cleanup_status["gmail_token_revoked"] = token_revoked

        # Step 2: Clear all chat sessions from memory
        global chat_sessions, chat_session_locks
        sessions_count = len(chat_sessions)
        chat_sessions.clear()
        chat_session_locks.clear()
        cleanup_status["chat_sessions_cleared"] = True
        cleanup_status["sessions_cleared_count"] = sessions_count

        # Success message
        cleanup_status["message"] = (
            f"Logout successful. "
            f"Token revoked: {token_revoked}, "
            f"Cleared {sessions_count} chat session(s)."
        )

        logger.info(cleanup_status["message"])

        return JSONResponse(
            status_code=200,
            content=cleanup_status
        )

    except Exception as e:
        logger.error(f"Logout error: {str(e)}", exc_info=True)

        # Still return 200 - logout should not fail from user perspective
        cleanup_status["message"] = f"Logout completed with errors: {str(e)}"

        return JSONResponse(
            status_code=200,
            content=cleanup_status
        )


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user_id: str = Header(..., alias="X-User-Id")
):
    """
    AI Chat endpoint for email assistance.
    Maintains session state for multi-turn conversations.
    """
    logger.info(f"Endpoint called: /chat with session_id: {request.session_id}, user_id: {user_id}")
    try:
        # Validate input
        if not request.message or not request.message.strip():
            raise ValueError("Message cannot be empty")

        # Get or create session ID (client-scoped identifier)
        session_id = request.session_id if request.session_id else str(uuid.uuid4())
        # Prevent cross-user collisions by namespacing in-memory sessions
        session_key = f"{user_id}:{session_id}"

        # Get or create ChatService instance for this session
        if session_key not in chat_sessions:
            logger.info(f"Creating new ChatService for session_id: {session_id}, user_id: {user_id}")
            chat_sessions[session_key] = ChatService(user_id=user_id)

        chat_service = chat_sessions[session_key]

        # RAG: pull relevant context from previous chats + emails and prepend it.
        context = ""
        try:
            context = await rag_service.get_combined_context(
                user_id=user_id,
                query=request.message,
                session_id=session_id,
            )
        except Exception as e:
            logger.error(f"Failed to build RAG context for chat: {e}")

        context_message = ""
        if context:
            context_message = (
                f"{context}\n\n"
                f"Use the context above if it is relevant. "
                f"Do not mention it explicitly unless asked."
            )

        # Get AI response (run in a thread to avoid blocking the event loop).
        # This also allows sync tool functions to safely use asyncio.run().
        lock = chat_session_locks.get(session_key)
        if lock is None:
            lock = asyncio.Lock()
            chat_session_locks[session_key] = lock

        async with lock:
            ai_response = await asyncio.to_thread(chat_service.chat, request.message, context_message)
        logger.info("Successfully generated AI response")
        logger.info(f"AI response length: {len(ai_response) if ai_response else 0}")
        logger.info(f"AI response preview: {ai_response[:500] if ai_response else 'Empty'}...")

        # RAG memory: store this exchange for future retrieval (best-effort).
        try:
            import re
            user_msg_id = str(uuid.uuid4())
            assistant_msg_id = str(uuid.uuid4())

            _schedule_store_chat_embedding(
                user_id=user_id,
                session_id=session_id,
                role="user",
                content=request.message,
                message_id=user_msg_id,
            )

            # Strip fenced code blocks from assistant text to avoid embedding huge JSON payloads.
            assistant_clean = re.sub(r"```[\\s\\S]*?```", "", ai_response).strip()
            _schedule_store_chat_embedding(
                user_id=user_id,
                session_id=session_id,
                role="assistant",
                content=assistant_clean[:2000],
                message_id=assistant_msg_id,
            )
        except Exception as e:
            logger.error(f"Failed to schedule chat memory embeddings: {e}")

        return ChatResponse(response=ai_response, session_id=session_id)
    except ValueError as e:
        logger.warning(f"Invalid chat input: {str(e)}")
        # User input validation error
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        # Server-side error
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error. Please try again later.")
    
@app.get("/emails/drafts", response_model=List[EmailOut])
async def list_drafts(user_id: str = Header(..., alias="X-User-Id")):
    try:
        emails = await fetch_drafts_multi(user_id, max_per_account=50)
        return emails
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emails/sent", response_model=List[EmailOut])
async def list_sent(user_id: str = Header(..., alias="X-User-Id")):
    try:
        emails = await fetch_messages_by_label_multi(user_id, "SENT", max_per_account=50)
        return emails
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emails/favorites", response_model=List[EmailOut])
async def list_starred(user_id: str = Header(..., alias="X-User-Id")):
    try:
        emails = await fetch_messages_by_label_multi(user_id, "STARRED", max_per_account=50)
        return emails
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emails/important", response_model=List[EmailOut])
async def list_important(user_id: str = Header(..., alias="X-User-Id")):
    try:
        emails = await fetch_messages_by_label_multi(user_id, "IMPORTANT", max_per_account=50)
        return emails
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emails/spam", response_model=List[EmailOut])
async def list_spam(user_id: str = Header(..., alias="X-User-Id")):
    try:
        emails = await fetch_messages_by_label_multi(user_id, "SPAM", max_per_account=50, include_spam_trash=True)
        return emails
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emails/trash", response_model=List[EmailOut])
async def list_trash(user_id: str = Header(..., alias="X-User-Id")):
    """
    Retrieve deleted emails (Trash folder).
    """
    try:
        emails = await fetch_messages_by_label_multi(user_id, "TRASH", max_per_account=50, include_spam_trash=True)
        return emails
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/emails/{message_id}")
async def delete_email(message_id: str, user_id: str = Header(..., alias="X-User-Id")):
    """
    Move an email to Trash.
    """
    try:
        resp = await trash_message_multi(user_id, message_id)
        return {
            "status": "trashed",
            "message_id": resp.get("id", message_id),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/emails/{message_id}/restore")
async def restore_email(message_id: str, user_id: str = Header(..., alias="X-User-Id")):
    """
    Restore an email from Trash back to the mailbox (Inbox).
    """
    try:
        resp = await untrash_message_multi(user_id, message_id)
        return {
            "status": "restored",
            "message_id": resp.get("id", message_id),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/emails/{message_id}/star")
async def star_email(message_id: str, starred: bool = Body(True), user_id: str = Header(..., alias="X-User-Id")):
    """
    Star or unstar an email.

    Request body (examples):
    { "starred": true }    -> add star
    { "starred": false }   -> remove star
    """
    try:
        resp = await set_star_multi(user_id, message_id, starred)
        return {
            "status": "starred" if starred else "unstarred",
            "message_id": resp.get("id", message_id),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emails/by-label/{label_id}", response_model=List[EmailOut])
async def list_by_label(
    label_id: str,
    user_id: str = Header(..., alias="X-User-Id"),
):
    """
    Retrieve emails for a specific Gmail label (by label ID, e.g. 'Label_20').
    This returns all messages having that label, like Gmail's label view.
    """
    try:
        emails = await fetch_messages_by_label_multi(user_id, label_id, max_per_account=50)
        return emails
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/labels", response_model=List[LabelOut])
async def list_user_labels(user_id: str = Header(..., alias="X-User-Id")):
    """
    Return only user-created labels from primary account (not system labels like INBOX, SENT).
    """
    try:
        raw_labels = await list_labels_multi(user_id)

        result: List[LabelOut] = []
        for lab in raw_labels:
            # Gmail returns 'type': 'system' | 'user'
            if lab.get("type") == "user":
                result.append(
                    LabelOut(
                        id=lab.get("id"),
                        name=lab.get("name", ""),
                        type=lab.get("type"),
                    )
                )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/labels", response_model=LabelOut)
async def create_user_label(
    payload: LabelCreate,
    user_id: str = Header(..., alias="X-User-Id"),
):
    """
    Create a new user label in the primary Gmail account.
    """
    try:
        created = await create_label_multi(user_id, payload.name)
        return LabelOut(
            id=created.get("id"),
            name=created.get("name", payload.name),
            type=created.get("type"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/labels/{label_id}", status_code=204)
async def delete_user_label(
    label_id: str,
    user_id: str = Header(..., alias="X-User-Id"),
):
    """
    Delete a user label by its id from the primary account.
    """
    try:
        await delete_label_multi(user_id, label_id)
        return JSONResponse(status_code=204, content=None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/emails/{message_id}/labels")
async def update_email_labels(
    message_id: str,
    payload: LabelUpdateRequest,
    user_id: str = Header(..., alias="X-User-Id"),
):
    """
    Add/remove labels on a specific email.

    Body example:
    {
      "add_label_ids": ["Label_123"],
      "remove_label_ids": ["Label_456"]
    }
    """
    try:
        resp = await modify_message_labels_multi(
            user_id=user_id,
            message_id=message_id,
            add_label_ids=payload.add_label_ids,
            remove_label_ids=payload.remove_label_ids
        )
        return {
            "status": "ok",
            "message_id": resp.get("id", message_id),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== Multi-Account Gmail Management Endpoints =====

@app.get("/gmail/accounts", response_model=List[GmailAccountOut])
async def list_gmail_accounts(user_id: str = Header(..., alias="X-User-Id")):
    """List all connected Gmail accounts for the user"""
    try:
        accounts = await gmail_account_service.get_all_accounts(user_id)
        return accounts
    except Exception as e:
        logger.error(f"Error listing Gmail accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/gmail/accounts/{account_id}/set-primary")
async def set_primary_account(
    account_id: str,
    user_id: str = Header(..., alias="X-User-Id")
):
    """Set an account as primary"""
    try:
        success = await gmail_account_service.set_primary(user_id, account_id)
        if not success:
            raise HTTPException(status_code=404, detail="Account not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting primary account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/gmail/accounts/{account_id}")
async def delete_gmail_account(
    account_id: str,
    user_id: str = Header(..., alias="X-User-Id")
):
    """Disconnect a Gmail account"""
    try:
        success = await email_account_service.hard_delete_account(user_id, account_id)
        if not success:
            raise HTTPException(status_code=404, detail="Account not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting Gmail account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/gmail/auth/connect")
async def initiate_gmail_connect(user_id: str = Header(..., alias="X-User-Id")):
    """
    Initiate Gmail OAuth flow for connecting a new account.
    Returns auth URL that includes user_id in state parameter.
    """
    try:
        import json
        flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
        flow.redirect_uri = REDIRECT_URI

        # Include user_id in state to identify user after OAuth callback
        state = json.dumps({"user_id": user_id})
        auth_url, _ = flow.authorization_url(prompt='consent', state=state)

        return {"auth_url": auth_url}
    except Exception as e:
        logger.error(f"Error initiating Gmail connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/read-email/unified", response_model=List[EmailOut])
async def get_unified_emails(
    user_id: str = Header(..., alias="X-User-Id"),
    account_id: Optional[str] = None,
    max_per_account: int = 25,
    filters: EmailFilters = Depends()
):
    """
    Fetch emails from connected email accounts (Gmail + Outlook).
    If account_id is provided, fetch only from that account.
    Otherwise, fetch from all accounts (unified view).
    Sorted by date (newest first).
    """
    logger.info(f"Unified inbox request for user {user_id}")

    try:
        # Get all connected accounts (Gmail + Outlook)
        accounts = await email_account_service.get_all_accounts(user_id)

        if not accounts:
            # Return empty array instead of 401 to avoid triggering logout
            logger.info(f"No email accounts found for user {user_id}")
            return []

        # Filter to specific account if requested
        if account_id:
            accounts = [acc for acc in accounts if acc["id"] == account_id]
            if not accounts:
                raise HTTPException(status_code=404, detail="Account not found")
            logger.info(f"Filtering emails for account: {account_id}")

        all_emails = []
        gmail_query = filters.to_gmail_query()
        if gmail_query:
            gmail_query = f"in:inbox {gmail_query}"
        else:
            gmail_query = "in:inbox"

        # Fetch emails from each account
        for account in accounts:
            try:
                provider = account.get("provider")

                if provider == "gmail":
                    service = await get_user_gmail_service(user_id, account["id"])

                    # Use existing fetch logic but with specific service
                    emails = fetch_messages_with_service(
                        service=service,
                        query=gmail_query,
                        max_results=max_per_account
                    )

                    # Add account information to each email
                    for email in emails:
                        email.account_id = account["id"]
                        email.account_email = account["email_address"]
                        email.provider = "gmail"

                    all_emails.extend(emails)

                elif provider == "outlook":
                    access_token = await email_account_service.get_outlook_access_token(
                        user_id, account["id"]
                    )
                    if not access_token:
                        logger.warning(f"Skipping Outlook account {account['id']}: missing/expired token")
                        continue

                    # Graph API approach (docs): GET /me/mailFolders/{folder-id}/messages
                    outlook_emails = await outlook_service.fetch_inbox(access_token, max_per_account)

                    for e in outlook_emails:
                        label_ids = list(e.get("label_ids", []) or [])
                        if not e.get("is_read", True) and "UNREAD" not in label_ids:
                            label_ids.append("UNREAD")
                        all_emails.append(
                            EmailOut(
                                message_id=e.get("message_id", ""),
                                sender=e.get("sender", ""),
                                recipient=e.get("recipient", ""),
                                subject=e.get("subject", ""),
                                body=e.get("body", ""),
                                date=e.get("date"),
                                label_ids=label_ids,
                                account_id=account["id"],
                                account_email=account["email_address"],
                                provider="outlook",
                            )
                        )

                else:
                    logger.warning(f"Skipping unknown provider '{provider}' for account {account.get('id')}")
                    continue

            except Exception as e:
                logger.error(f"Failed to fetch from account {account['id']}: {e}")
                # Continue with other accounts even if one fails
                continue

        # Sort all emails by date (newest first)
        # Normalize all dates to timezone-aware UTC for comparison
        from datetime import datetime as dt_class, timezone

        def normalize_date(date_obj):
            """Convert any datetime to timezone-aware UTC for comparison."""
            if date_obj is None:
                return dt_class.min.replace(tzinfo=timezone.utc)
            if date_obj.tzinfo is None:
                # Assume UTC if no timezone info
                return date_obj.replace(tzinfo=timezone.utc)
            # Convert to UTC
            return date_obj.astimezone(timezone.utc)

        all_emails.sort(key=lambda x: normalize_date(x.date), reverse=True)

        # Apply ML classification
        all_emails = apply_ml_classification(all_emails)

        logger.info(f"Unified inbox: fetched {len(all_emails)} emails from {len(accounts)} accounts")
        return all_emails

    except Exception as e:
        logger.error(f"Error fetching unified emails: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== Unified Email Account Management (Gmail + Outlook) =====

@app.get("/email/accounts", response_model=List[EmailAccountOut])
async def list_email_accounts(user_id: str = Header(..., alias="X-User-Id")):
    """
    List all connected email accounts (Gmail and Outlook) for the user.
    """
    try:
        accounts = await email_account_service.get_all_accounts(user_id)
        return accounts
    except Exception as e:
        logger.error(f"Error listing email accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/email/accounts/{account_id}/set-primary")
async def set_primary_email_account(
    account_id: str,
    user_id: str = Header(..., alias="X-User-Id")
):
    """Set an email account as primary."""
    try:
        success = await email_account_service.set_primary(user_id, account_id)
        if not success:
            raise HTTPException(status_code=404, detail="Account not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting primary account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/email/accounts/{account_id}")
async def disconnect_email_account(
    account_id: str,
    user_id: str = Header(..., alias="X-User-Id")
):
    """Disconnect an email account."""
    try:
        success = await email_account_service.hard_delete_account(user_id, account_id)
        if not success:
            raise HTTPException(status_code=404, detail="Account not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disconnecting account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== Outlook OAuth Endpoints =====

@app.get("/auth/outlook/connect")
async def initiate_outlook_connect(user_id: str = Header(..., alias="X-User-Id")):
    """
    Initiate Outlook OAuth flow for connecting an account.
    Returns auth URL that includes user_id in state parameter.
    """
    try:
        if not outlook_service.is_configured:
            raise HTTPException(
                status_code=503,
                detail="Outlook integration is not configured. Add OUTLOOK_CLIENT_ID and OUTLOOK_CLIENT_SECRET to .env"
            )

        import json
        state = json.dumps({"user_id": user_id})
        auth_url = outlook_service.get_auth_url(state=state)

        return {"auth_url": auth_url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating Outlook connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/outlook/callback")
async def outlook_auth_callback(code: str, state: Optional[str] = None):
    """
    OAuth callback for Outlook authentication.
    Saves token to database and redirects to frontend.
    """
    logger.info("Endpoint called: /auth/outlook/callback")

    try:
        import json

        # Parse user_id from state
        user_id = None
        if state:
            try:
                state_data = json.loads(state)
                user_id = state_data.get("user_id")
            except:
                pass

        if not user_id:
            logger.error("Missing user_id in Outlook OAuth state")
            return RedirectResponse(url=f"{FRONTEND_APP_URL}/accounts?error=missing_user_id&provider=outlook")

        # Exchange code for tokens
        token_response = outlook_service.exchange_code(code)

        # Get user's email address
        access_token = token_response.get("access_token")
        email_address = outlook_service.get_user_email(access_token)

        # Save account to database
        saved = await email_account_service.save_outlook_account(
            user_id=user_id,
            email_address=email_address,
            token_response=token_response,
            display_name=email_address
        )

        logger.info(f"Connected Outlook account {email_address} for user {user_id}")
        return RedirectResponse(url=f"{FRONTEND_APP_URL}/accounts?connected={email_address}&provider=outlook")

    except Exception as e:
        logger.error(f"Outlook authentication failed: {str(e)}")
        return RedirectResponse(url=f"{FRONTEND_APP_URL}/accounts?error=outlook_connection_failed&provider=outlook")


# ===== RAG / AI Search Endpoints =====

class SearchRequest(BaseModel):
    query: str
    limit: int = 5


class SearchResult(BaseModel):
    id: str
    content: str
    metadata: dict
    similarity: float


# Email search endpoints removed - using direct Gmail API instead of RAG for email queries
# Chat memory RAG is still active for conversation history


# ===== Outlook Email Operations =====

@app.get("/outlook/inbox", response_model=List[EmailOut])
async def get_outlook_inbox(
    user_id: str = Header(..., alias="X-User-Id"),
    account_id: str = Header(..., alias="X-Account-Id"),
    max_results: int = 25
):
    """Fetch inbox emails from a specific Outlook account."""
    try:
        access_token = await email_account_service.get_outlook_access_token(user_id, account_id)
        if not access_token:
            raise HTTPException(status_code=401, detail="Invalid or expired Outlook token")

        emails = await outlook_service.fetch_inbox(access_token, max_results)

        # Convert to EmailOut format
        return [
            EmailOut(
                message_id=e["message_id"],
                sender=e["sender"],
                recipient=e["recipient"],
                subject=e["subject"],
                body=e["body"],
                date=e["date"],
                label_ids=e.get("label_ids", []),
                account_id=account_id,
                provider="outlook"
            )
            for e in emails
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching Outlook inbox: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/outlook/send")
async def send_outlook_email(
    req: EmailRequest,
    user_id: str = Header(..., alias="X-User-Id"),
    account_id: str = Header(..., alias="X-Account-Id")
):
    """Send email via Outlook."""
    try:
        access_token = await email_account_service.get_outlook_access_token(user_id, account_id)
        if not access_token:
            raise HTTPException(status_code=401, detail="Invalid or expired Outlook token")

        result = await outlook_service.send(access_token, req.to, req.subject, req.body)

        if result.get("success"):
            return {"status": "sent", "provider": "outlook"}
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "Send failed"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending Outlook email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/outlook/emails/{message_id}")
async def delete_outlook_email(
    message_id: str,
    user_id: str = Header(..., alias="X-User-Id"),
    account_id: str = Header(..., alias="X-Account-Id")
):
    """Move Outlook email to trash."""
    try:
        access_token = await email_account_service.get_outlook_access_token(user_id, account_id)
        if not access_token:
            raise HTTPException(status_code=401, detail="Invalid or expired Outlook token")

        result = await outlook_service.trash(access_token, message_id)

        if result.get("success"):
            return {"status": "trashed", "message_id": message_id}
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "Delete failed"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting Outlook email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/outlook/emails/{message_id}/star")
async def star_outlook_email(
    message_id: str,
    starred: bool = Body(True),
    user_id: str = Header(..., alias="X-User-Id"),
    account_id: str = Header(..., alias="X-Account-Id")
):
    """Star/flag or unstar/unflag an Outlook email."""
    try:
        access_token = await email_account_service.get_outlook_access_token(user_id, account_id)
        if not access_token:
            raise HTTPException(status_code=401, detail="Invalid or expired Outlook token")

        result = await outlook_service.star(access_token, message_id, starred)

        if result.get("success"):
            return {"status": "starred" if starred else "unstarred", "message_id": message_id}
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "Star operation failed"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starring Outlook email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ CHAT HISTORY PERSISTENCE API ============

class ChatSessionCreate(BaseModel):
    title: Optional[str] = "New chat"
    backend_session_id: Optional[str] = None

class ChatSessionUpdate(BaseModel):
    title: Optional[str] = None
    backend_session_id: Optional[str] = None

class ChatMessageCreate(BaseModel):
    role: str  # 'user' or 'bot'
    text: Optional[str] = None
    emails: Optional[List[Dict]] = None

class ChatSessionOut(BaseModel):
    id: str
    title: str
    backend_session_id: Optional[str]
    created_at: str
    updated_at: str

class ChatMessageOut(BaseModel):
    id: str
    role: str
    text: Optional[str]
    emails: Optional[List[Dict]]
    created_at: str

class ChatSessionWithMessages(ChatSessionOut):
    messages: List[ChatMessageOut]


@app.get("/chat/sessions", response_model=List[ChatSessionOut])
async def list_chat_sessions(user_id: str = Header(..., alias="X-User-Id")):
    """Get all chat sessions for the current user, ordered by most recent."""
    try:
        result = supabase.table("chat_sessions")\
            .select("id,title,backend_session_id,created_at,updated_at")\
            .eq("user_id", user_id)\
            .order("updated_at", desc=True)\
            .execute()

        sessions = []
        for row in (result.data or []):
            sessions.append(ChatSessionOut(
                id=row["id"],
                title=row["title"],
                backend_session_id=row.get("backend_session_id"),
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            ))
        return sessions
    except Exception as e:
        logger.error(f"Error listing chat sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/sessions", response_model=ChatSessionOut)
async def create_chat_session(
    data: ChatSessionCreate,
    user_id: str = Header(..., alias="X-User-Id")
):
    """Create a new chat session."""
    try:
        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        result = supabase.table("chat_sessions").insert({
            "id": session_id,
            "user_id": user_id,
            "title": data.title or "New chat",
            "backend_session_id": data.backend_session_id,
            "created_at": now,
            "updated_at": now
        }).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create chat session")

        row = result.data[0]
        return ChatSessionOut(
            id=row["id"],
            title=row["title"],
            backend_session_id=row.get("backend_session_id"),
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/sessions/{session_id}", response_model=ChatSessionWithMessages)
async def get_chat_session(
    session_id: str,
    user_id: str = Header(..., alias="X-User-Id")
):
    """Get a chat session with all its messages."""
    try:
        # Get session
        session_result = supabase.table("chat_sessions")\
            .select("id,title,backend_session_id,created_at,updated_at")\
            .eq("id", session_id)\
            .eq("user_id", user_id)\
            .execute()

        if not session_result.data:
            raise HTTPException(status_code=404, detail="Chat session not found")

        session = session_result.data[0]

        # Get messages
        messages_result = supabase.table("chat_messages")\
            .select("id,role,text,emails,created_at")\
            .eq("session_id", session_id)\
            .order("created_at", desc=False)\
            .execute()

        messages = []
        for row in (messages_result.data or []):
            messages.append(ChatMessageOut(
                id=row["id"],
                role=row["role"],
                text=row.get("text"),
                emails=row.get("emails"),
                created_at=row["created_at"]
            ))

        return ChatSessionWithMessages(
            id=session["id"],
            title=session["title"],
            backend_session_id=session.get("backend_session_id"),
            created_at=session["created_at"],
            updated_at=session["updated_at"],
            messages=messages
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/chat/sessions/{session_id}", response_model=ChatSessionOut)
async def update_chat_session(
    session_id: str,
    data: ChatSessionUpdate,
    user_id: str = Header(..., alias="X-User-Id")
):
    """Update a chat session (title or backend_session_id)."""
    try:
        # Check ownership
        check = supabase.table("chat_sessions")\
            .select("id")\
            .eq("id", session_id)\
            .eq("user_id", user_id)\
            .execute()

        if not check.data:
            raise HTTPException(status_code=404, detail="Chat session not found")

        update_data = {"updated_at": datetime.utcnow().isoformat()}
        if data.title is not None:
            update_data["title"] = data.title
        if data.backend_session_id is not None:
            update_data["backend_session_id"] = data.backend_session_id

        result = supabase.table("chat_sessions")\
            .update(update_data)\
            .eq("id", session_id)\
            .execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to update session")

        row = result.data[0]
        return ChatSessionOut(
            id=row["id"],
            title=row["title"],
            backend_session_id=row.get("backend_session_id"),
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/chat/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    user_id: str = Header(..., alias="X-User-Id")
):
    """Delete a chat session and all its messages."""
    try:
        # Check ownership
        check = supabase.table("chat_sessions")\
            .select("id")\
            .eq("id", session_id)\
            .eq("user_id", user_id)\
            .execute()

        if not check.data:
            raise HTTPException(status_code=404, detail="Chat session not found")

        # Delete session (messages are cascade deleted)
        supabase.table("chat_sessions")\
            .delete()\
            .eq("id", session_id)\
            .execute()

        return {"status": "deleted", "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/sessions/{session_id}/messages", response_model=ChatMessageOut)
async def add_chat_message(
    session_id: str,
    data: ChatMessageCreate,
    user_id: str = Header(..., alias="X-User-Id")
):
    """Add a message to a chat session."""
    try:
        # Check ownership
        check = supabase.table("chat_sessions")\
            .select("id,title")\
            .eq("id", session_id)\
            .eq("user_id", user_id)\
            .execute()

        if not check.data:
            raise HTTPException(status_code=404, detail="Chat session not found")

        session = check.data[0]

        message_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        result = supabase.table("chat_messages").insert({
            "id": message_id,
            "session_id": session_id,
            "role": data.role,
            "text": data.text,
            "emails": data.emails,
            "created_at": now
        }).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to add message")

        # Update session title if it's the first user message and title is "New chat"
        if data.role == "user" and data.text and session["title"] == "New chat":
            title = data.text[:40] + "..." if len(data.text) > 40 else data.text
            supabase.table("chat_sessions")\
                .update({"title": title, "updated_at": now})\
                .eq("id", session_id)\
                .execute()

        row = result.data[0]
        return ChatMessageOut(
            id=row["id"],
            role=row["role"],
            text=row.get("text"),
            emails=row.get("emails"),
            created_at=row["created_at"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding chat message: {e}")
        raise HTTPException(status_code=500, detail=str(e))
