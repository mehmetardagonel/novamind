from datetime import datetime
from typing import List

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from simplegmail import Gmail
from simplegmail.query import construct_query

from models import EmailOut, EmailRequest
from filters import EmailFilters
from auth import (
    get_current_active_user,
    UserOut,
    SupabaseUser
)

# Initialize FastAPI app
app = FastAPI(
    title="NovaMind Email Assistant API",
    description="AI-powered email management with Gmail integration",
    version="1.0.0"
)

# CORS configuration - allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server default
        "http://localhost:5179",  # Vite dev server current
        "http://localhost:3000",  # Alternative frontend port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5179",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize on startup
@app.on_event("startup")
def startup_event():
    print("✅ Supabase authentication configured")
    print("🚀 NovaMind Email Assistant API is running")

# Lazy load Gmail client
_gmail_client = None

def get_gmail_client() -> Gmail:
    """Lazy load Gmail client to avoid startup errors if credentials are missing"""
    global _gmail_client
    if _gmail_client is None:
        try:
            _gmail_client = Gmail()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Gmail API not configured. Please set up client_secret.json and gmail_token.json. Error: {str(e)}"
            )
    return _gmail_client

def to_out(msg) -> EmailOut:
    return EmailOut(
        sender    = msg.sender    or "",
        recipient = msg.recipient or "",
        subject   = msg.subject   or "(no subject)",
        body      = msg.plain     or msg.html or "(empty)",
        date      = msg.date,
    )

# ==================== ROOT ENDPOINT ====================
@app.get("/")
def read_root():
    return {
        "message": "NovaMind Email Assistant API",
        "version": "1.0.0",
        "status": "running",
        "auth": "Supabase",
        "endpoints": {
            "auth": {
                "me": "GET /api/auth/me (requires Supabase token)"
            },
            "emails": {
                "read": "GET /backend/read-email (requires auth)",
                "send": "POST /backend/send-email (requires auth)"
            }
        }
    }

# ==================== AUTHENTICATION ENDPOINTS ====================
@app.get("/api/auth/me", response_model=UserOut)
async def get_me(current_user: SupabaseUser = Depends(get_current_active_user)):
    """Get current logged-in user information from Supabase"""
    return UserOut(
        id=current_user.id,
        email=current_user.email,
        created_at=datetime.utcnow().isoformat()
    )

# ==================== EMAIL ENDPOINTS ====================
@app.get("/backend/read-email", response_model=List[EmailOut])
def list_emails(
    filters: EmailFilters = Depends(),
    current_user: SupabaseUser = Depends(get_current_active_user)
):
    """Fetch emails from Gmail with optional filters (requires Supabase authentication)"""
    # Build query from filters
    qdict = filters.to_simplegmail_query()

    try:
        q = construct_query(qdict) if qdict else None
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid filter: {e}")

    try:
        # Fetch messages
        gmail = get_gmail_client()
        messages = gmail.get_messages(query=q)
        return [to_out(m) for m in messages]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching emails: {str(e)}"
        )

@app.post("/backend/send-email")
def send_email(
    req: EmailRequest,
    current_user: SupabaseUser = Depends(get_current_active_user)
):
    """Send email via Gmail (requires Supabase authentication)"""
    try:
        gmail = get_gmail_client()
        user_info = gmail.service.users().getProfile(userId="me").execute()
        sender_email = user_info["emailAddress"]

        params = {
            "to": req.to,
            "sender": sender_email,
            "subject": req.subject,
            "msg_plain": req.body,
            "signature": True
        }
        message = gmail.send_message(**params)
        return {
            "status": "sent",
            "message_id": getattr(message, "id", None),
            "to": req.to,
            "subject": req.subject
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending email: {str(e)}")

# ==================== HEALTH CHECK ====================
@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "NovaMind Email Assistant"
    }
