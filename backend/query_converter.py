"""
Query Converter - Convert Gmail search operators to Microsoft Graph KQL

Supports common Gmail operators:
- from:user@example.com
- to:user@example.com
- subject:keyword
- is:unread / is:read
- has:attachment
- after:YYYY/MM/DD
- before:YYYY/MM/DD
- in:inbox / in:sent
"""

import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def convert_gmail_to_graph_query(gmail_query: str) -> str:
    """
    Convert Gmail search syntax to Microsoft Graph KQL query

    Args:
        gmail_query: Gmail search query (e.g., "from:boss subject:meeting is:unread")

    Returns:
        Microsoft Graph KQL query string

    Examples:
        "from:boss subject:meeting" → 'from:"boss" AND subject:"meeting"'
        "is:unread has:attachment" → 'isRead eq false AND hasAttachments eq true'
        "after:2025/01/01" → 'receivedDateTime ge 2025-01-01T00:00:00Z'
    """
    try:
        if not gmail_query or not gmail_query.strip():
            return "*"  # Match all

        query_lower = gmail_query.lower().strip()
        parts = []

        # Parse individual operators using regex
        tokens = _tokenize_query(query_lower)

        for token in tokens:
            converted = _convert_token(token)
            if converted:
                parts.append(converted)

        if not parts:
            # If no operators matched, treat as general search
            return f'"{gmail_query}"'

        # Join with AND
        result = " AND ".join(parts)
        logger.info(f"Converted Gmail query '{gmail_query}' to Graph query '{result}'")
        return result

    except Exception as e:
        logger.error(f"Error converting query '{gmail_query}': {e}")
        # Fallback to simple keyword search
        return f'"{gmail_query}"'


def _tokenize_query(query: str) -> List[str]:
    """
    Tokenize Gmail query into individual operator parts

    Args:
        query: Gmail query string

    Returns:
        List of tokens (operators and values)
    """
    # Pattern for operators with values: operator:value or operator:"value with spaces"
    operator_pattern = r'(\w+):(?:"([^"]+)"|(\S+))'

    # Pattern for standalone operators: is:unread, has:attachment
    standalone_pattern = r'\b(is|has):(\w+)\b'

    tokens = []

    # Extract operator:value patterns
    for match in re.finditer(operator_pattern, query):
        operator = match.group(1)
        value = match.group(2) or match.group(3)  # Quoted or unquoted value
        tokens.append((operator, value))

    # Extract standalone operators
    for match in re.finditer(standalone_pattern, query):
        operator = match.group(1)
        modifier = match.group(2)
        tokens.append((operator, modifier))

    # If no operators found, treat entire query as keyword search
    if not tokens:
        tokens = [('keyword', query)]

    return tokens


def _convert_token(token: tuple) -> Optional[str]:
    """
    Convert a single token (operator, value) to Graph KQL

    Args:
        token: Tuple of (operator, value)

    Returns:
        Graph KQL string or None if not convertible
    """
    operator, value = token

    # From: sender email or name
    if operator == 'from':
        return f'from/emailAddress/address:"{value}" OR from/emailAddress/name:"{value}"'

    # To: recipient email or name
    elif operator == 'to':
        return f'toRecipients/emailAddress/address:"{value}" OR toRecipients/emailAddress/name:"{value}"'

    # Subject: subject contains keyword
    elif operator == 'subject':
        return f'subject:"{value}"'

    # Is: read/unread status
    elif operator == 'is':
        if value in ['unread', 'read']:
            is_read = 'true' if value == 'read' else 'false'
            return f'isRead eq {is_read}'
        elif value == 'important':
            return 'importance eq "high"'
        elif value == 'starred':
            return 'flag/flagStatus eq "flagged"'

    # Has: attachment check
    elif operator == 'has':
        if value == 'attachment':
            return 'hasAttachments eq true'

    # After: date filter (received after date)
    elif operator == 'after':
        try:
            date_str = _parse_gmail_date(value)
            return f'receivedDateTime ge {date_str}'
        except Exception as e:
            logger.warning(f"Could not parse date '{value}': {e}")

    # Before: date filter (received before date)
    elif operator == 'before':
        try:
            date_str = _parse_gmail_date(value)
            return f'receivedDateTime le {date_str}'
        except Exception as e:
            logger.warning(f"Could not parse date '{value}': {e}")

    # In: folder location
    elif operator == 'in':
        folder_map = {
            'inbox': 'inbox',
            'sent': 'sentitems',
            'drafts': 'drafts',
            'trash': 'deleteditems',
            'spam': 'junkemail'
        }
        folder = folder_map.get(value.lower())
        if folder:
            return f'parentFolderId eq "{folder}"'

    # Keyword: general content search
    elif operator == 'keyword':
        # Search in subject and body
        return f'(subject:"{value}" OR body:"{value}")'

    logger.warning(f"Unsupported operator: {operator}:{value}")
    return None


def _parse_gmail_date(date_str: str) -> str:
    """
    Parse Gmail date format to ISO 8601 format for Microsoft Graph

    Args:
        date_str: Date string in Gmail format (YYYY/MM/DD or timestamp)

    Returns:
        ISO 8601 formatted date string

    Examples:
        "2025/01/15" → "2025-01-15T00:00:00Z"
        "1735689600" → "2025-01-01T00:00:00Z"
    """
    try:
        # Try Unix timestamp first
        if date_str.isdigit():
            dt = datetime.fromtimestamp(int(date_str))
            return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        # Try YYYY/MM/DD format
        if '/' in date_str:
            dt = datetime.strptime(date_str, '%Y/%m/%d')
            return dt.strftime('%Y-%m-%dT00:00:00Z')

        # Try YYYY-MM-DD format
        if '-' in date_str:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            return dt.strftime('%Y-%m-%dT00:00:00Z')

        raise ValueError(f"Unsupported date format: {date_str}")

    except Exception as e:
        logger.error(f"Error parsing date '{date_str}': {e}")
        raise


# Import for type hints
from typing import List, Optional
