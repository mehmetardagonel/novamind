from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from pydantic import BaseModel

from simplegmail import Gmail
from simplegmail.query import construct_query

from models import EmailOut, EmailRequest
from filters import EmailFilters

app = FastAPI(title="Email Assistant API")
gmail = Gmail()  # loads credentials + token.json automatically

def to_out(msg) -> EmailOut:
    return EmailOut(
        sender    = msg.sender    or "",
        recipient = msg.recipient or "",
        subject   = msg.subject   or "(no subject)",
        body      = msg.plain     or msg.html or "(empty)",
        date      = msg.date,
    )

@app.get("/read-email", response_model=List[EmailOut])
def list_emails(filters: EmailFilters = Depends()):
    # Build query from filters
    qdict = filters.to_simplegmail_query()

    try:
        q = construct_query(qdict) if qdict else None
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid filter: {e}")

    # Fetch messages
    messages = gmail.get_messages(query=q)
    return [to_out(m) for m in messages]

@app.post("/send-email")
def send_email(req: EmailRequest):
    try:
        user_info = gmail.service.users().getProfile(userId="me").execute() # take user email address dynamically
        sender_email = user_info["emailAddress"]

        params = {
            "to": req.to,
            "sender": sender_email,
            "subject": req.subject,
            "msg_plain": req.body,
            "signature": True
        }
        message = gmail.send_message(**params)
        return {"status": "sent", "message_id": getattr(message, "id", None)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))