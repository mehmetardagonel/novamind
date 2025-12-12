from pydantic import BaseModel, Field, EmailStr
from datetime import datetime, timezone
from typing import Optional, List

class GmailAccountOut(BaseModel):
    """Gmail account information returned to frontend"""
    id: str
    email_address: str
    display_name: str
    is_primary: bool
    created_at: datetime
    last_sync_at: Optional[datetime] = None

class EmailOut(BaseModel):
    message_id: str
    sender: str
    recipient: str
    subject: str
    body: str
    date: datetime
    ml_prediction: Optional[str] = None  # ML classification: spam, ham, or important
    label_ids: List[str] = []
    # Multi-account support
    account_id: Optional[str] = None
    account_email: Optional[str] = None

class EmailRequest(BaseModel):
    to: EmailStr
    subject: str
    body: str

class LabelBase(BaseModel):
    name: str = Field(..., min_length=1)


class LabelCreate(LabelBase):
    """Payload when creating a new label."""
    pass


class LabelOut(LabelBase):
    """Label as returned to the frontend."""
    id: str
    type: Optional[str] = None  # 'user' or 'system' (we will mostly return 'user')


class LabelUpdateRequest(BaseModel):
    """
    Payload for updating labels on a specific email.
    Used by /emails/{message_id}/labels.
    """
    add_label_ids: List[str] = []
    remove_label_ids: List[str] = []
