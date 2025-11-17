import os
from typing import List

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow # <--- NEW IMPORT

from models import EmailOut, EmailRequest
from filters import EmailFilters
# Import our refactored service and its config
from gmail_service import (
    fetch_messages, 
    send_email, 
    get_current_user_email,
    CLIENT_CONFIG, # <--- NEW IMPORT
    SCOPES         # <--- NEW IMPORT
)

load_dotenv()

app = FastAPI()

# Get redirect URI and frontend URL from config/env
# This ensures it matches your .env file
REDIRECT_URI = CLIENT_CONFIG["installed"]["redirect_uris"][0]
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173") # Set this in your .env!

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server default
        "http://localhost:5179",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5179",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/read-email", response_model=List[EmailOut])
async def get_emails(filters: EmailFilters = Depends()):
    """
    Fetch emails using Gmail API.
    If auth is required, return 401 with an auth_url for the frontend.
    """
    try:
        query = filters.to_gmail_query()
        emails = fetch_messages(query=query)
        return emails
    except Exception as e:
        # Catch the specific error from gmail_service.py
        if str(e) == "AUTH_REQUIRED":
            # Create the Auth Flow using the imported config
            flow = Flow.from_client_config(
                CLIENT_CONFIG,
                scopes=SCOPES
            )
            # Set the redirect_uri to match your config
            flow.redirect_uri = REDIRECT_URI
            
            # Generate the URL for the user to visit
            auth_url, _ = flow.authorization_url(prompt='consent')
            
            # Return 401 (Unauthorized) with the auth_url
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required", "auth_url": auth_url}
            )
        
        # Raise other errors normally
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/callback")
async def auth_callback(code: str):
    """
    This is the endpoint Google redirects to after user login.
    It exchanges the 'code' for a 'token.json'.
    """
    try:
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES
        )
        flow.redirect_uri = REDIRECT_URI

        # Exchange the code for credentials
        flow.fetch_token(code=code)
        creds = flow.credentials

        # Save the credentials to token.json
        with open("token.json", "w") as token:
            token.write(creds.to_json())
            
        # Redirect the user's browser back to the frontend app
        return RedirectResponse(url=FRONTEND_URL)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")


@app.post("/send-email")
async def send_email_endpoint(req: EmailRequest):
    """
    Send an email using Gmail API.
    """
    try:
        sender_email = get_current_user_email()
        result = send_email(
            sender=sender_email or "me",
            to=req.to,
            subject=req.subject,
            body=req.body,
        )
        return {
            "status": "sent",
            "message_id": result.get("id"),
        }
    except Exception as e:
        # Handle auth error here too
        if str(e) == "AUTH_REQUIRED":
            # This shouldn't happen if /read-email was called first,
            # but it's good practice.
             raise HTTPException(status_code=401, detail="Authentication required")
        raise HTTPException(status_code=500, detail=str(e))