from datetime import datetime
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from dotenv import load_dotenv

from models import EmailOut, EmailRequest
from filters import EmailFilters
from gmail_service import fetch_messages, send_email, get_current_user_email

load_dotenv()

app = FastAPI()


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
