from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from simplegmail import Gmail
from simplegmail.query import construct_query

from models import EmailOut, EmailRequest
from filters import EmailFilters
from database import get_db, init_db, User
from auth import (
    authenticate_user,
    create_access_token,
    create_user,
    get_current_active_user,
    UserCreate,
    UserOut,
    Token,
    ACCESS_TOKEN_EXPIRE_MINUTES
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
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative frontend port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
def startup_event():
    init_db()
    print("✅ Database initialized")
    print("🚀 NovaMind Email Assistant API is running")

gmail = Gmail()  # loads credentials + token.json automatically

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
        "endpoints": {
            "auth": {
                "signup": "POST /api/auth/signup",
                "login": "POST /api/auth/login",
                "me": "GET /api/auth/me"
            },
            "emails": {
                "read": "GET /backend/read-email",
                "send": "POST /backend/send-email"
            }
        }
    }

# ==================== AUTHENTICATION ENDPOINTS ====================
@app.post("/api/auth/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user account"""
    try:
        db_user = create_user(db, user)

        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": db_user.username}, expires_delta=access_token_expires
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": UserOut.from_orm(db_user)
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating user: {str(e)}"
        )

@app.post("/api/auth/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login with username and password"""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserOut.from_orm(user)
    }

@app.get("/api/auth/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_active_user)):
    """Get current logged-in user information"""
    return UserOut.from_orm(current_user)

# ==================== EMAIL ENDPOINTS ====================
@app.get("/backend/read-email", response_model=List[EmailOut])
def list_emails(
    filters: EmailFilters = Depends(),
    current_user: User = Depends(get_current_active_user)
):
    """Fetch emails from Gmail with optional filters (requires authentication)"""
    # Build query from filters
    qdict = filters.to_simplegmail_query()

    try:
        q = construct_query(qdict) if qdict else None
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid filter: {e}")

    try:
        # Fetch messages
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
    current_user: User = Depends(get_current_active_user)
):
    """Send email via Gmail (requires authentication)"""
    try:
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
