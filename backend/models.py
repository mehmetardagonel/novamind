from pydantic import BaseModel, Field, EmailStr
from datetime import datetime, timezone
from typing import Optional, List

class EmailOut(BaseModel):
    sender: str
    recipient: str
    subject: str
    body: str
    date: datetime

class EmailRequest(BaseModel):
    to: EmailStr
    subject: str
    body: str    