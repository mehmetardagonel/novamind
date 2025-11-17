from datetime import datetime
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware # <--- NEW IMPORT
from dotenv import load_dotenv

from models import EmailOut, EmailRequest
from filters import EmailFilters
from gmail_service import fetch_messages, send_email, get_current_user_email

load_dotenv()

app = FastAPI()

origins = [
    # Allow your frontend's origin. Replace with the actual URL 
    # if it's not running on the same machine/port.
    "http://localhost:5173", 
    "http://127.0.0.1:44956",
    "http://127.0.0.1:54320",
    
    # You can add the IP/port from your error log if needed, though it's local:
    # "http://127.0.0.1:35658" 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For development, use ["*"] to allow all
    # For better security, use the defined 'origins' variable above
    allow_credentials=True,
    allow_methods=["*"], # Allows GET, POST, OPTIONS, etc.
    allow_headers=["*"], # Allows all headers (like Content-Type and Authorization)
)
# --------------------------


@app.get("/read-email", response_model=List[EmailOut])
async def get_emails(filters: EmailFilters = Depends()):
    """
    Fetch emails using Gmail API, filtered by query params.
    """
    try:
        query = filters.to_gmail_query()
        emails = fetch_messages(query=query)
        return emails
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/send-email")
async def send_email_endpoint(req: EmailRequest):
    """
    Send an email using Gmail API.
    """
    try:
        # Dynamically get sender email from Gmail profile
        sender_email = get_current_user_email()

        result = send_email(
            sender=sender_email or "me",
            to=req.to,
            subject=req.subject,
            body=req.body,
        )

        return {
            "status": "sent",
            "message_id": result.get("id"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))