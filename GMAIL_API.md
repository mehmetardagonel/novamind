# Gmail API Backend (FastAPI)

This project provides a backend service for Gmail integration using the official Google Gmail API.  
It supports reading, sending, and managing emails for multiple users with individual OAuth tokens.  
Each application user (identified by their Supabase `user.id`) is mapped to their own Google OAuth token stored securely under the `tokens/` directory.

This backend is designed to serve as the server-side component of an AI-powered email assistant, but it can also be used independently.

---

## Features

### Gmail OAuth Integration (Per User)
- Each Supabase-authenticated user gets their own Google OAuth token.
- Tokens are stored at:
  ```
  tokens/token_<supabase_user_id>.json
  ```
- Ensures complete separation of Gmail accounts.

### Email Operations
- Read inbox with filters
- Read drafts, sent, starred, important, spam, trash emails
- Send email
- Star / unstar email
- Delete email (move to Trash)

### FastAPI API
- Clean, structured endpoints
- Fully documented via Swagger at:
  ```
  http://localhost:8000/docs
  ```

---

## Folder Structure

```
backend/
    main.py
    gmail_service.py
    filters.py
    models.py
    requirements.txt
    env.example
    .env
tokens/
    token_<user_id>.json   (generated dynamically)
.gitignore
GMAIL_API.md
```

---

## Installation

### 1. Clone the repository
```bash
git clone git@github.com:mehmetardagonel/novamind.git
cd novamind/backend/
```

### 2. Create a virtual environment
```bash
python3 -m venv my_venv
source my_venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r ../requirements.txt
```

---

## Environment Variables

Create a `.env` file inside the `backend/` folder using `env.example` as a guide.

```
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_PROJECT_ID=

GOOGLE_REDIRECT_URI=http://localhost:8000/oauth2callback
GOOGLE_AUTH_URI=https://accounts.google.com/o/oauth2/auth
GOOGLE_TOKEN_URI=https://oauth2.googleapis.com/token
GOOGLE_AUTH_PROVIDER_X509_CERT_URL=https://www.googleapis.com/oauth2/v1/certs
```

---

## Running the Backend

Inside the `backend/` folder, run:

```bash
uvicorn main:app --reload
```

Backend will start at:
```
http://127.0.0.1:8000
```

API docs:
```
http://127.0.0.1:8000/docs
```

---

## Per-User Authentication

This backend does **not** use a single global Gmail token.

Instead:

1. The frontend sends the Supabase user ID as a header:
   ```
   X-User-Id: <supabase_user_id>
   ```

2. The backend loads the user-specific OAuth token from:
   ```
   tokens/token_<user_id>.json
   ```

3. If the token does not exist:
   - OAuth consent flow starts
   - User signs in with Google
   - Token is saved for future requests

This prevents cross-account mixing and makes the backend multi-user safe.

---

## API Endpoints

### GET /read-email
Fetch inbox emails with optional filters.

Header (required):
```
X-User-Id: <supabase_user_id>
```

Query parameters include:
- sender
- recipient
- subject_contains
- unread
- labels
- newer_than_days
- since
- until

Example:
```
GET /read-email?sender=support@gmail.com
```

---

### POST /send-email
Send an email.

Header:
```
X-User-Id: <supabase_user_id>
```

Body:
```json
{
  "to": "someone@example.com",
  "subject": "Hello",
  "body": "Testing Gmail API"
}
```

---

### Additional Email Endpoints

Each requires:
```
X-User-Id: <supabase_user_id>
```

#### GET /emails/drafts
Returns Gmail drafts.

#### GET /emails/sent
Returns Sent mail (label: SENT).

#### GET /emails/starred
Returns Starred mail (label: STARRED).

#### GET /emails/important
Returns Important mail (label: IMPORTANT).

#### GET /emails/spam
Returns Spam mail (label: SPAM).

#### GET /emails/trash
Returns Trash mail (label: TRASH).

---

### POST /emails/{message_id}/star
Star or unstar an email.

Body:
```json
{ "starred": true }
```

Unstar:
```json
{ "starred": false }
```

---

### DELETE /emails/{message_id}
Moves email to Trash.

Response:
```json
{ "status": "trashed", "message_id": "..." }
```

---

## Testing Without Frontend

You can test everything using Swagger UI:
```
http://localhost:8000/docs
```

For each request, enter:
```
X-User-Id: <your_supabase_user_id>
```

Alternatively, use curl:

```bash
curl -X GET "http://127.0.0.1:8000/read-email" \
  -H "X-User-Id: <your_user_id>"
```

---

## tokens/ Directory

The backend automatically creates:
```
tokens/token_<user_id>.json
```

This file contains the OAuth credentials **only for that user**.

The directory is ignored by Git.

---

## Requirements

This backend uses:
- FastAPI
- Uvicorn
- Python Gmail API client
- google-auth
- python-dotenv
- email libraries

See `backend/requirements.txt`.
