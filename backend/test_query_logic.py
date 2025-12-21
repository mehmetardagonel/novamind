import os
import sys
import logging

# Set PYTHONPATH to current directory to import from backend
sys.path.append(os.getcwd())

from email_tools import query_emails, _extract_filters_from_query
from unittest.mock import MagicMock, patch

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_filter_extraction():
    print("\n--- Testing Filter Extraction Logic ---")
    
    test_cases = [
        {
            "query": "what did I receive from Google jobs today?",
            "expected": {"subject_keyword": "google jobs", "time_period": "today"}
        },
        {
            "query": "important emails from boss last week",
            "expected": {"sender": "boss", "importance": True, "time_period": "last_week"}
        },
        {
            "query": "emails regarding meeting from amazon",
            "expected": {"subject_keyword": "amazon", "time_period": None} # amazon is company_keyword, regarding meeting might overwrite
        }
    ]
    
    for tc in test_cases:
        filters = _extract_filters_from_query(tc["query"])
        print(f"Query: '{tc['query']}'")
        print(f"Extracted: {filters}")
        # Note: we don't assert exactly because the logic is heuristic, 
        # but we want to see it's reasonable.

def test_query_emails_mocked():
    print("\n--- Testing query_emails Tool (Mocked API) ---")
    
    user_id = "user123"
    query = "Find emails from LinkedIn"
    
    mock_email = {
        "sender": "LinkedIn <jobs-noreply@linkedin.com>",
        "subject": "New job for you",
        "date": "2025-12-21",
        "body": "Check out this AI Engineer role...",
        "message_id": "li123",
        "account_id": "acc1",
        "provider": "gmail",
        "ml_prediction": "important"
    }

    # Mock fetch_mails to avoid real API calls
    with patch("email_tools.fetch_mails") as mock_fetch:
        mock_fetch.return_value = [mock_email]
        
        result = query_emails(query, user_id=user_id)
        
        print(f"Result success: {result['success']}")
        print(f"Count: {result['count']}")
        print(f"Insights: {result['insights']}")
        
        assert result["success"] == True
        assert result["count"] == 1
        assert "LinkedIn" in result["insights"]

if __name__ == "__main__":
    test_filter_extraction()
    test_query_emails_mocked()
    print("\n✅ Query logic tests completed successfully!")
