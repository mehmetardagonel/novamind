import re
from typing import Optional


def sanitize_for_tts(text: Optional[str]) -> str:
    if not text:
        return ""

    cleaned = str(text)
    cleaned = cleaned.replace("```", "")
    cleaned = cleaned.replace("`", "")
    cleaned = re.sub(r"^\s{0,3}#{1,6}\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace("*", "")
    cleaned = re.sub(r"^\s*[-•]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
