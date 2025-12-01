# Set protobuf to use pure Python implementation for Python 3.14 compatibility
# This MUST be done before any protobuf-using modules are imported
import os
os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'

from typing import List, Dict, Optional
import uuid

from fastapi import FastAPI, Depends, HTTPException, Request, Header, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow
from pydantic import BaseModel

from models import EmailOut, EmailRequest
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
    CLIENT_CONFIG,
    SCOPES
)
# Import AI Chat Service
from chat_service import ChatService

import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()

# Get redirect URI and frontend URL from config/env
# This ensures it matches your .env file
REDIRECT_URI = CLIENT_CONFIG["installed"]["redirect_uris"][0]
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173/app") # Set this in your .env!

origins = [
    "http://localhost:5173",  # Vite dev server default
    "http://localhost:5179",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5179",
    "http://127.0.0.1:3000"
]

if FRONTEND_URL not in origins:
    origins.append(FRONTEND_URL)

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

# Chat Request/Response Models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None  # Optional session ID, generated if not provided

class ChatResponse(BaseModel):
    response: str
    session_id: str  # Return session ID to client


@app.get("/read-email", response_model=List[EmailOut])
async def get_emails(filters: EmailFilters = Depends()):
    """
    Fetch emails using Gmail API.
    If auth is required, return 401 with an auth_url for the frontend.
    """
    logger.info(f"Endpoint called: /read-email with filters: {filters}")
    try:
        query = filters.to_gmail_query()
        emails = fetch_messages(query=query)
        logger.info(f"Successfully fetched {len(emails)} emails")
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
async def auth_callback(code: str):
    """
    This is the endpoint Google redirects to after user login.
    It exchanges the 'code' for a 'token.json'.
    """
    logger.info("Endpoint called: /auth/callback")
    try:
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES
        )
        flow.redirect_uri = REDIRECT_URI

        # Exchange the code for credentials
        flow.fetch_token(code=code)
        creds = flow.credentials

        # Save the credentials to token.json
        with open("token.json", "w") as token:
            token.write(creds.to_json())
            
        logger.info("Successfully exchanged code for token and saved to token.json")
        # Redirect the user's browser back to the frontend app
        return RedirectResponse(url=FRONTEND_URL)
        
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")


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
        global chat_sessions
        sessions_count = len(chat_sessions)
        chat_sessions.clear()
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
async def chat(request: ChatRequest):
    """
    AI Chat endpoint for email assistance.
    Maintains session state for multi-turn conversations.
    """
    logger.info(f"Endpoint called: /chat with session_id: {request.session_id}")
    try:
        # Validate input
        if not request.message or not request.message.strip():
            raise ValueError("Message cannot be empty")

        # Get or create session ID
        session_id = request.session_id if request.session_id else str(uuid.uuid4())

        # Get or create ChatService instance for this session
        if session_id not in chat_sessions:
            logger.info(f"Creating new ChatService for session_id: {session_id}")
            chat_sessions[session_id] = ChatService()

        chat_service = chat_sessions[session_id]

        # Get AI response
        ai_response = chat_service.chat(request.message)
        logger.info("Successfully generated AI response")
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
        return fetch_drafts(max_results=50, user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emails/sent", response_model=List[EmailOut])
async def list_sent(user_id: str = Header(..., alias="X-User-Id")):
    try:
        return fetch_messages_by_label("SENT", max_results=50, user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emails/favorites", response_model=List[EmailOut])
async def list_starred(user_id: str = Header(..., alias="X-User-Id")):
    try:
        return fetch_messages_by_label("STARRED", max_results=50, user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emails/important", response_model=List[EmailOut])
async def list_important(user_id: str = Header(..., alias="X-User-Id")):
    try:
        return fetch_messages_by_label("IMPORTANT", max_results=50, user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emails/spam", response_model=List[EmailOut])
async def list_spam(user_id: str = Header(..., alias="X-User-Id")):
    try:
        return fetch_messages_by_label("SPAM", max_results=50, include_spam_trash=True, user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emails/trash", response_model=List[EmailOut])
async def list_trash(user_id: str = Header(..., alias="X-User-Id")):
    """
    Retrieve deleted emails (Trash folder).
    """
    try:
        return fetch_messages_by_label("TRASH", max_results=50, include_spam_trash=True, user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/emails/{message_id}")
async def delete_email(message_id: str, user_id: str = Header(..., alias="X-User-Id")):
    """
    Move an email to Trash.
    """
    try:
        resp = trash_message(message_id, user_id=user_id)
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
        resp = untrash_message(message_id, user_id=user_id)
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
        resp = set_star(message_id, starred, user_id=user_id)
        return {
            "status": "starred" if starred else "unstarred",
            "message_id": resp.get("id", message_id),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))