from datetime import date, timedelta
from pydantic import BaseModel, field_validator
from typing import Literal, Optional, List


class EmailFilters(BaseModel):
    sender: Optional[str] = None
    recipient: Optional[str] = None
    subject_contains: Optional[str] = None
    unread: Optional[bool] = None
    labels: Optional[List[str]] = None

    # time filters (use one of these)
    newer_than_days: Optional[int] = None
    since: Optional[date] = None
    until: Optional[date] = None

    @field_validator("newer_than_days")
    @classmethod
    def _non_negative(cls, v):
        if v is not None and v <= 0:
            raise ValueError("newer_than_days must be positive")
        return v

    def to_gmail_query(self) -> str:
        """
        Convert filters into a Gmail search query string.
        Example: from:melih@example.com subject:invoice is:unread label:Work newer_than:7d
        """
        parts: List[str] = []

        if self.sender:
            parts.append(f'from:"{self.sender}"')

        if self.recipient:
            parts.append(f'to:"{self.recipient}"')

        if self.subject_contains:
            parts.append(f'subject:"{self.subject_contains}"')

        if self.unread is True:
            parts.append("is:unread")
        elif self.unread is False:
            parts.append("is:read")

        if self.labels:
            for label in self.labels:
                parts.append(f'label:"{label}"')

        # Time filters
        if self.newer_than_days:
            parts.append(f"newer_than:{self.newer_than_days}d")
        if self.since:
            parts.append(f"after:{self.since.isoformat()}")
        if self.until:
            # Gmail before: is exclusive; add 1 day to make it inclusive
            inclusive_until = self.until + timedelta(days=1)
            parts.append(f"before:{inclusive_until.isoformat()}")

        return " ".join(parts)