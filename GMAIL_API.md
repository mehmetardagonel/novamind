# Gmail API Backend

This project is a backend service built with FastAPI that integrates securely with the Gmail API.
It allows users to read, filter, and send emails via their Gmail account using OAuth 2.0 authentication, without ever exposing credentials in the source code.

## Features

- Gmail API integration with official Google client libraries  
- Secure authentication using OAuth 2.0  
- Environment-based credentials (no client_secret.json required)  
- Read emails with filters (sender, recipient, subject, unread, date range, etc.)  
- Send new emails from the authenticated account  
- FastAPI endpoints with Pydantic validation and Swagger UI  
- Token refresh & persistence (via token.json, gitignored)

## Environment Variables

Create a `.env` file in the project root with your Gmail OAuth credentials:

```env
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_PROJECT_ID=your_project_id_here
GOOGLE_REDIRECT_URI=http://localhost
GOOGLE_AUTH_URI=https://accounts.google.com/o/oauth2/auth
GOOGLE_TOKEN_URI=https://oauth2.googleapis.com/token
GOOGLE_AUTH_PROVIDER_X509_CERT_URL=https://www.googleapis.com/oauth2/v1/certs
SUPABASE_URL=your-supabase-url-here
SUPABASE_KEY=your-supabase-key-here
SUPABASE_JWT_SECRET=your-supabase-jwt-secret-here
FRONTEND_URL="http://localhost:5173"
```

## Installation & Setup

1. Clone the repository
   ```bash
   git clone git@github.com:mehmetardagonel/novamind.git
   git checkout feature/melih-gmail-api
   ```

2. Create a virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate   # or venv\Scripts\activate on Windows
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Add your `.env` file

5. Run the app
   ```bash
   uvicorn main:app --reload
   ```

6. Visit Swagger UI:  
   http://127.0.0.1:8000/docs

## API Endpoints

### GET /read-email
Fetch emails using Gmail filters.

| Query Parameter | Type | Example | Description |
|-----------------|------|----------|--------------|
| `sender` | string | `sender@gmail.com` | Filter by sender |
| `recipient` | string | `me@gmail.com` | Filter by recipient |
| `subject_contains` | string | `invoice` | Filter by subject text |
| `unread` | bool | `true` | Show unread emails only |
| `labels` | list[str] | `labels=IMPORTANT&labels=Work` | Gmail labels |
| `newer_than_days` | int | `7` | Last N days |
| `since` | date | `2025-11-01` | Start date |
| `until` | date | `2025-11-09` | End date |

Example:
```
GET /read-email?sender=Supabase&unread=true&newer_than_days=3
```

### POST /send-email
Send an email using the authenticated Gmail account.

Request body:
```json
{
  "to": "someone@example.com",
  "subject": "Test email from FastAPI",
  "body": "Hello from my Gmail API backend!"
}
```

Response:
```json
{
  "status": "sent",
  "message_id": "18f9a2e9c3f9d0e1"
}
```

### GET /emails/drafts
Retrieve all Gmail drafts for the authenticated user.

Drafts are stored differently from normal messages, so this endpoint uses the Gmail Drafts API internally.

Example Request:
```
GET /emails/drafts
```

Example Response:
```
[
  {
    "sender": "me@gmail.com",
    "recipient": "example@gmail.com",
    "subject": "Draft message",
    "body": "This is the draft content...",
    "date": "2025-11-09T13:12:54"
  }
]
```

### GET /emails/sent
Retrieve emails from the Sent folder (Gmail label: SENT).

Example Request:
```
GET /emails/sent
```

Example Response:
```
[
  {
    "sender": "me@gmail.com",
    "recipient": "friend@example.com",
    "subject": "Project Update",
    "body": "Here is the update...",
    "date": "2025-11-08T09:21:10"
  }
]
```

### GET /emails/starred
Retrieve all starred emails (Gmail label: STARRED).

Example Request:
```
GET /emails/starred
```

Example Response:
```
[
  {
    "sender": "newsletter@example.com",
    "recipient": "me@gmail.com",
    "subject": "Important Info",
    "body": "Details inside...",
    "date": "2025-11-05T18:05:42"
  }
]
```

### GET /emails/important
Retrieve emails marked by Gmail as Important (Gmail system label: IMPORTANT).

Example Request:
```
GET /emails/important
```

Example Response:
```
[
  {
    "sender": "boss@example.com",
    "recipient": "me@gmail.com",
    "subject": "Urgent: Meeting Update",
    "body": "We need to discuss...",
    "date": "2025-10-29T14:37:21"
  }
]
```

### GET /emails/spam
Retrieve all emails from the Spam folder (Gmail system label: SPAM).

Example Request:
```
GET /emails/spam
```

Example Response:
```
[
  {
    "sender": "fraud@mail.scam",
    "recipient": "me@gmail.com",
    "subject": "You won a prize!",
    "body": "Click here to claim...",
    "date": "2025-11-07T22:10:11"
  }
]
```

### GET /emails/trash
Retrieve deleted emails in the Trash folder (Gmail system label: TRASH).

Example Request:
```
GET /emails/trash
```

Example Response:
```
[
  {
    "sender": "me@gmail.com",
    "recipient": "old@example.com",
    "subject": "Old message",
    "body": "Deleting this one...",
    "date": "2025-11-03T12:44:00"
  }
]
```

## Summary of All Endpoints

- GET /read-email : Read inbox messages with filters
- POST /send-email : Send an email
- GET /emails/drafts : List draft emails
- GET /emails/sent : List sent emails
- GET /emails/starred : List starred emails
- GET /emails/important : List Gmail-flagged important emails
- GET /emails/spam : List spam emails
- GET /emails/trash : List deleted/trash emails


## Authentication Flow

The first time you call `/read-email` or `/send-email`, a Google OAuth window will open.  
After granting access, the credentials are stored locally in `token.json` (automatically refreshed on expiration).

No `client_secret.json` file is required — the credentials are built entirely from `.env`.

## Tech Stack

- Python 3.12.x
- FastAPI
- Google Auth / Gmail API
- Pydantic v2
- Uvicorn
- dotenv
