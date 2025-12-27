
import re

def parse_update_instruction(user_input: str) -> dict:
    # Pattern 1: "subject: X body: Y" or "subject with: X and body: Y" or "subject: X and body with: Y"
    pattern1 = re.search(
        r'subject\s*(?:with)?\s*:\s*(.+?)\s+(?:and\s+)?body\s*(?:with)?\s*:\s*(.+)',
        user_input,
        re.IGNORECASE | re.DOTALL
    )

    # Pattern 2: Just "subject: X" or "subject with: X" (subject only)
    pattern2 = re.search(
        r'(?:update\s+)?subject\s*(?:with)?\s*:\s*(.+?)(?:\s+and\s+body|$)',
        user_input,
        re.IGNORECASE
    )

    # Pattern 3: Just "body: X" or "body with: X" (body only)
    pattern3 = re.search(
        r'(?:update\s+)?body\s*(?:with)?\s*:\s*(.+?)$',
        user_input,
        re.IGNORECASE
    )

    if pattern1:
        subject = pattern1.group(1).strip()
        body = pattern1.group(2).strip()
        return {
            "mode": "direct",
            "subject": subject,
            "body": body,
            "instruction": None
        }
    elif pattern2:
        subject = pattern2.group(1).strip()
        subject = re.sub(r'\s+and\s+body\s*$', '', subject, flags=re.IGNORECASE).strip()
        return {
            "mode": "direct",
            "subject": subject,
            "body": None,
            "instruction": None
        }
    elif pattern3:
        body = pattern3.group(1).strip()
        return {
            "mode": "direct",
            "subject": None,
            "body": body,
            "instruction": None
        }
    else:
        return {
            "mode": "instruction",
            "subject": None,
            "body": None,
            "instruction": user_input.strip()
        }

def check(text):
    parsed = parse_update_instruction(text)
    instruction = parsed.get("instruction", "")
    is_generic_update = not instruction or "update draft" in instruction.lower() and len(instruction.split()) < 10
    print(f"Text: '{text}'")
    print(f"Parsed: {parsed}")
    print(f"Generic: {is_generic_update}")
    print("-" * 20)

check("update draft for novamindtester@gmail.com")
check("update draft")
check("update the draft to make it formal")
check("make it formal")
