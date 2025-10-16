from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from pydantic import BaseModel

from simplegmail import Gmail
from simplegmail.query import construct_query

from models import EmailOut
from filters import EmailFilters

app = FastAPI(title="Email Assistant API")

def to_out(msg) -> EmailOut:
    return EmailOut(
        sender    = msg.sender    or "",
        recipient = msg.recipient or "",
        subject   = msg.subject   or "(no subject)",
        body      = msg.plain     or msg.html or "(empty)",
        date      = msg.date,
    )

@app.get("/emails", response_model=List[EmailOut])
def list_emails(filters: EmailFilters = Depends()):
    gmail = Gmail()  # loads credentials + token.json automatically

    # Build query from filters
    qdict = filters.to_simplegmail_query()

    try:
        q = construct_query(qdict) if qdict else None
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid filter: {e}")

    # Fetch messages
    messages = gmail.get_messages(query=q)
    return [to_out(m) for m in messages]
