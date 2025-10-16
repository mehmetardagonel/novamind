from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional, List

class EmailOut(BaseModel):
    sender: str
    recipient: str
    subject: str
    body: str
    date: datetime
