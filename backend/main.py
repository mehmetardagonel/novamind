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

from models import (
    EmailOut,
    EmailRequest,
    LabelOut,
    LabelCreate,
    LabelUpdateRequest,
    GmailAccountOut,
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

import logging


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

# Startup event to preload ML models
@app.on_event("startup")
async def startup_event():
    """
    Preload ML models on server startup.
    """
    logger.info("=" * 60)
    logger.info("🚀 Starting Novamind Backend Server...")
    logger.info("=" * 60)

    try:
        logger.info("📦 Loading ML classification models...")
        classifier = get_classifier()
        logger.info("✅ ML Classifier initialized successfully!")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"❌ Failed to initialize ML classifier: {str(e)}")
        logger.warning("⚠️  Server will use rule-based classification as fallback")
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

            await gmail_account_service.save_account(
                user_id=user_id,
                email_address=email_address,
                credentials=creds
            )

            logger.info(f"Connected Gmail account {email_address} for user {user_id}")
            return RedirectResponse(url=f"{FRONTEND_URL}/inbox?connected={email_address}")
        else:
            # Legacy flow: save to token.json (backward compatibility)
            with open("token.json", "w") as token:
                token.write(creds.to_json())

            logger.info("Successfully exchanged code for token and saved to token.json")
            return RedirectResponse(url=FRONTEND_URL)

    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        return RedirectResponse(url=f"{FRONTEND_URL}/inbox?error=connection_failed")


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
        success = await gmail_account_service.delete_account(user_id, account_id)
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
    Fetch emails from connected Gmail accounts.
    If account_id is provided, fetch only from that account.
    Otherwise, fetch from all accounts (unified view).
    Sorted by date (newest first).
    """
    logger.info(f"Unified inbox request for user {user_id}")

    try:
        # Get all connected accounts
        accounts = await gmail_account_service.get_all_accounts(user_id)

        if not accounts:
            # Return empty array instead of 401 to avoid triggering logout
            logger.info(f"No Gmail accounts found for user {user_id}")
            return []

        # Filter to specific account if requested
        if account_id:
            accounts = [acc for acc in accounts if acc["id"] == account_id]
            if not accounts:
                raise HTTPException(status_code=404, detail="Account not found")
            logger.info(f"Filtering emails for account: {account_id}")

        all_emails = []
        query = filters.to_gmail_query()
        if query:
            query = f"in:inbox {query}"
        else:
            query = "in:inbox"

        # Fetch emails from each account
        for account in accounts:
            try:
                service = await get_user_gmail_service(user_id, account["id"])

                # Use existing fetch logic but with specific service
                emails = fetch_messages_with_service(
                    service=service,
                    query=query,
                    max_results=max_per_account
                )

                # Add account information to each email
                for email in emails:
                    email.account_id = account["id"]
                    email.account_email = account["email_address"]

                all_emails.extend(emails)

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