from datetime import datetime
from typing import List

from fastapi import FastAPI, Depends, HTTPException, Body
from dotenv import load_dotenv

from models import EmailOut, EmailRequest
from filters import EmailFilters
from gmail_service import fetch_messages, send_email, get_current_user_email, fetch_messages_by_label, fetch_drafts, trash_message, set_star

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

@app.get("/emails/drafts", response_model=List[EmailOut])
async def list_drafts():
    try:
        return fetch_drafts(max_results=50)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emails/sent", response_model=List[EmailOut])
async def list_sent():
    try:
        return fetch_messages_by_label("SENT", max_results=50)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emails/favorites", response_model=List[EmailOut])
async def list_starred():
    try:
        return fetch_messages_by_label("STARRED", max_results=50)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emails/important", response_model=List[EmailOut])
async def list_important():
    try:
        return fetch_messages_by_label("IMPORTANT", max_results=50)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emails/spam", response_model=List[EmailOut])
async def list_spam():
    try:
        return fetch_messages_by_label("SPAM", max_results=50, include_spam_trash=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emails/trash", response_model=List[EmailOut])
async def list_trash():
    """
    Retrieve deleted emails (Trash folder).
    """
    try:
        return fetch_messages_by_label("TRASH", max_results=50, include_spam_trash=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/emails/{message_id}")
async def delete_email(message_id: str):
    """
    Move an email to Trash.
    """
    try:
        resp = trash_message(message_id)
        return {
            "status": "trashed",
            "message_id": resp.get("id", message_id),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/emails/{message_id}/star")
async def star_email(message_id: str, starred: bool = Body(True)):
    """
    Star or unstar an email.

    Request body (examples):
    { "starred": true }    -> add star
    { "starred": false }   -> remove star
    """
    try:
        resp = set_star(message_id, starred)
        return {
            "status": "starred" if starred else "unstarred",
            "message_id": resp.get("id", message_id),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))