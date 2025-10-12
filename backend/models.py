from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field

class Email(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sender: str
    subject: str
    body: str
    received_at: datetime = Field(default_factory=datetime.utcnow)

class EmailCreate(SQLModel):
    sender: str
    subject: str
    body: str

class EmailUpdate(SQLModel):
    sender: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None