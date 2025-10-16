from datetime import date, timedelta
from pydantic import BaseModel, field_validator
from typing import Literal, Optional, List

class EmailFilters(BaseModel):
    sender: Optional[str] = None                 # "john@example.com" or "John"
    subject_contains: Optional[str] = None       # "invoice"
    unread: Optional[bool] = None
    labels: Optional[List[str]] = None           # ["Work"] or ["Work","CS"]

    # time filters (use one of these)
    newer_than_days: Optional[int] = None        # e.g. 14
    since: Optional[date] = None                 # ISO date: 2025-10-01
    until: Optional[date] = None                 # inclusive end

    @field_validator("newer_than_days")
    @classmethod
    def _positive_days(cls, v):
        if v is not None and v <= 0:
            raise ValueError("newer_than_days must be > 0")
        return v

    @field_validator("until")
    @classmethod
    def _until_after_since(cls, v, info):
        since = info.data.get("since")
        if v and since and v < since:
            raise ValueError("until must be >= since")
        return v

    def to_simplegmail_query(self) -> dict:
        """Translate validated params → simplegmail.query.construct_query() dict."""
        q: dict = {}
        if self.sender:
            # simplegmail understands "sender"
            q["sender"] = self.sender
        if self.subject_contains:
            q["subject"] = self.subject_contains
        if self.unread is True:
            q["unread"] = True
        if self.labels:
            # single or OR-of-ANDs accepted; simplest form:
            q["labels"] = self.labels

        # time window
        if self.newer_than_days:
            q["newer_than"] = (self.newer_than_days, "day")
        if self.since:
            q["after"] = self.since
        if self.until:
            # Gmail "before:" is exclusive; add 1 day to make it inclusive
            q["before"] = self.until + timedelta(days=1)

        return q
