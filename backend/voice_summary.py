import re
from typing import Optional, Iterable, List, Dict


def _extract_email_address(value: str) -> Optional[str]:
    if not value:
        return None
    match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", value)
    return match.group(0) if match else None


def _clean_sender(value: Optional[str]) -> str:
    if not value:
        return "Someone"
    raw = str(value).strip().strip("\"'")
    raw = re.sub(r"\s*<[^>]+>", "", raw).strip()
    if raw:
        email = _extract_email_address(raw)
        if email and raw == email:
            domain = email.split("@", 1)[1].strip()
            return domain or email.split("@", 1)[0].strip() or "Someone"
        return raw
    email = _extract_email_address(value)
    if not email:
        return "Someone"
    domain = email.split("@", 1)[1].strip()
    return domain or email.split("@", 1)[0].strip() or "Someone"


def _clean_subject(value: Optional[str], max_len: int = 80) -> str:
    subject = re.sub(r"\s+", " ", str(value or "").strip())
    if not subject:
        return "(no subject)"
    if len(subject) <= max_len:
        return subject
    return f"{subject[: max_len - 3].rstrip()}..."


def _detect_provider(emails: Iterable[Dict]) -> Optional[str]:
    providers = set()
    for email in emails:
        if not isinstance(email, dict):
            continue
        provider = email.get("provider")
        if isinstance(provider, str) and provider.strip():
            providers.add(provider.strip().lower())
    if len(providers) == 1:
        provider = providers.pop()
        if provider == "gmail":
            return "Gmail"
        if provider == "outlook":
            return "Outlook"
    return None


def _detect_folder(emails: Iterable[Dict]) -> Optional[str]:
    for email in emails:
        if not isinstance(email, dict):
            continue
        folder = email.get("folder") or email.get("mailbox")
        if isinstance(folder, str) and folder.strip():
            return folder.strip().lower()
        label_ids = email.get("label_ids")
        if isinstance(label_ids, list) and label_ids:
            labels = {str(label).upper() for label in label_ids if label}
            if "SPAM" in labels or "JUNK" in labels:
                return "spam"
            if "TRASH" in labels or "DELETED" in labels:
                return "trash"
            if "DRAFT" in labels or "DRAFTS" in labels:
                return "drafts"
            if "SENT" in labels:
                return "sent"
            if "IMPORTANT" in labels:
                return "important"
            if "INBOX" in labels:
                return "inbox"
    return None


def build_email_voice_summary(
    *,
    emails: Optional[List[Dict]],
    total: Optional[int] = None,
    max_to_read: int = 5,
    provider_name: Optional[str] = None,
    folder_name: Optional[str] = None,
) -> str:
    emails = emails or []
    total_count = total if isinstance(total, int) else len(emails)

    if total_count <= 0:
        return "You don't have any emails here."

    provider = provider_name or _detect_provider(emails)
    folder = folder_name or _detect_folder(emails) or "inbox"

    if provider:
        intro = f"Here are your {provider} {folder} emails."
    else:
        intro = f"Here are your {folder} emails."

    lines = [intro]

    for email in emails[: max_to_read]:
        if not isinstance(email, dict):
            continue
        sender = _clean_sender(
            email.get("sender_name")
            or email.get("from_name")
            or email.get("from")
            or email.get("sender")
        )
        subject = _clean_subject(email.get("subject") or email.get("title"))
        lines.append(f'{sender} sent an email \"{subject}\".')

    remaining = total_count - min(max_to_read, total_count)
    if remaining > 0:
        lines.append(f"And {remaining} different emails.")

    return " ".join(line for line in lines if line).strip()
