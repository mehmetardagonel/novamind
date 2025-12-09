<<<<<<< HEAD
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime, timezone
from typing import Optional, List

class EmailOut(BaseModel):
    message_id: str
    sender: str
    recipient: str
    subject: str
    body: str
    date: datetime
    ml_prediction: Optional[str] = None  # ML classification: spam, ham, or important
    label_ids: List[str] = []

class EmailRequest(BaseModel):
    to: EmailStr
    subject: str
=======
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime, timezone
from typing import Optional, List

class EmailOut(BaseModel):
    message_id: str
    sender: str
    recipient: str
    subject: str
    body: str
    date: datetime
    label_ids: List[str] = []

class EmailRequest(BaseModel):
    to: EmailStr
    subject: str
>>>>>>> remotes/origin/feature/halil-frontend
    body: str    