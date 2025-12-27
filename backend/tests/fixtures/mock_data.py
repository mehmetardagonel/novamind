"""
Mock data for testing the email system.
Contains realistic test data resembling production app structure.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Dict

MOCK_USER_ID = "test_user_123"
MOCK_USER_EMAIL = "user@example.com"

# Realistic email data matching web app structure
MOCK_EMAILS: List[Dict] = [
    {
        "message_id": "msg_001",
        "sender": "john.doe@company.com",
        "recipient": MOCK_USER_EMAIL,
        "subject": "Q4 Project Status Update",
        "body": "Hi team,\n\nHere's the latest update on our Q4 project. We've completed 75% of the tasks and are on track for the December deadline. Key highlights:\n\n- Frontend redesign: 100% complete\n- Backend API: 80% complete\n- Testing: 50% complete\n\nPlease review and let me know if you have any questions.\n\nBest,\nJohn",
        "date": datetime.now(timezone.utc) - timedelta(hours=2),
        "ml_prediction": "important",
        "ml_confidence": 0.92,
        "label_ids": ["INBOX", "IMPORTANT"],
        "account_id": "acc_001",
        "account_email": MOCK_USER_EMAIL,
        "provider": "gmail"
    },
    {
        "message_id": "msg_002",
        "sender": "sarah.williams@partner.com",
        "recipient": MOCK_USER_EMAIL,
        "subject": "Meeting Rescheduled to Friday 3 PM",
        "body": "Hi,\n\nDue to a conflict, I need to reschedule our meeting from Thursday to Friday at 3 PM. Is that time still good for you?\n\nLet me know!\n\nSarah",
        "date": datetime.now(timezone.utc) - timedelta(hours=5),
        "ml_prediction": "important",
        "ml_confidence": 0.88,
        "label_ids": ["INBOX", "IMPORTANT", "CATEGORY_PERSONAL"],
        "account_id": "acc_001",
        "account_email": MOCK_USER_EMAIL,
        "provider": "gmail"
    },
    {
        "message_id": "msg_003",
        "sender": "notifications@github.com",
        "recipient": MOCK_USER_EMAIL,
        "subject": "[repo/project] Pull Request #42: Add dark mode support",
        "body": "A new pull request has been created:\n\nTitle: Add dark mode support\nAuthor: @developer123\n\nChanges:\n- Added dark theme CSS\n- Toggle component in settings\n- User preference persistence\n\nView the pull request: https://github.com/repo/project/pull/42",
        "date": datetime.now(timezone.utc) - timedelta(hours=8),
        "ml_prediction": "ham",
        "ml_confidence": 0.75,
        "label_ids": ["INBOX", "CATEGORY_UPDATES"],
        "account_id": "acc_001",
        "account_email": MOCK_USER_EMAIL,
        "provider": "gmail"
    },
    {
        "message_id": "msg_004",
        "sender": "newsletter@techblog.com",
        "recipient": MOCK_USER_EMAIL,
        "subject": "Weekly Tech Digest: AI, Cloud, and More",
        "body": "This week's top stories:\n\n1. AI breakthrough in natural language processing\n2. Cloud computing trends for 2024\n3. Best practices for microservices architecture\n\nRead more at techblog.com",
        "date": datetime.now(timezone.utc) - timedelta(days=1, hours=3),
        "ml_prediction": "ham",
        "ml_confidence": 0.65,
        "label_ids": ["INBOX", "CATEGORY_PROMOTIONS"],
        "account_id": "acc_001",
        "account_email": MOCK_USER_EMAIL,
        "provider": "gmail"
    },
    {
        "message_id": "msg_005",
        "sender": "alerts@monitoring.com",
        "recipient": MOCK_USER_EMAIL,
        "subject": "URGENT: High CPU Usage on Server prod-01",
        "body": "Alert: Server prod-01 is experiencing high CPU usage (95% for 15 minutes).\n\nServer: prod-01\nCPU: 95%\nMemory: 82%\nDisk: 45%\n\nAction required: Please investigate immediately.",
        "date": datetime.now(timezone.utc) - timedelta(hours=1),
        "ml_prediction": "important",
        "ml_confidence": 0.98,
        "label_ids": ["INBOX", "IMPORTANT", "CATEGORY_UPDATES"],
        "account_id": "acc_001",
        "account_email": MOCK_USER_EMAIL,
        "provider": "gmail"
    }
]

# Mock draft emails
MOCK_DRAFTS: List[Dict] = [
    {
        "id": "draft_001",
        "to": "john.doe@company.com",
        "subject": "Re: Q4 Project Status Update",
        "body": "Thanks for the update, John! Great progress on the project.",
        "date": datetime.now(timezone.utc) - timedelta(hours=1),
        "recipient": "john.doe@company.com"
    },
    {
        "id": "draft_002",
        "to": "john.doe@company.com",
        "subject": "Follow-up: Project Timeline",
        "body": "Hi John,\n\nI wanted to follow up on the project timeline we discussed.",
        "date": datetime.now(timezone.utc) - timedelta(hours=3),
        "recipient": "john.doe@company.com"
    },
    {
        "id": "draft_003",
        "to": "sarah.williams@partner.com",
        "subject": "Re: Meeting Rescheduled",
        "body": "Hi Sarah,\n\nFriday at 3 PM works perfectly for me. See you then!",
        "date": datetime.now(timezone.utc) - timedelta(minutes=30),
        "recipient": "sarah.williams@partner.com"
    }
]
