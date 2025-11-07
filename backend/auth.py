from datetime import datetime
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "your-jwt-secret-here")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Security scheme for bearer tokens
security = HTTPBearer()

# Pydantic models
class UserOut(BaseModel):
    id: str
    email: str
    created_at: str

class SupabaseUser(BaseModel):
    id: str
    email: str
    user_metadata: dict = {}

# Verify Supabase JWT token
async def verify_supabase_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> SupabaseUser:
    """
    Verify the Supabase JWT token from the Authorization header
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials

        # Get user from Supabase using the token
        user_response = supabase.auth.get_user(token)

        if not user_response or not user_response.user:
            raise credentials_exception

        user_data = user_response.user

        return SupabaseUser(
            id=user_data.id,
            email=user_data.email,
            user_metadata=user_data.user_metadata or {}
        )
    except Exception as e:
        print(f"Token verification error: {e}")
        raise credentials_exception

# Get current user (alias for verify_supabase_token)
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> SupabaseUser:
    """
    Get the current authenticated user from Supabase
    """
    return await verify_supabase_token(credentials)

# Get current active user
async def get_current_active_user(current_user: SupabaseUser = Depends(get_current_user)) -> SupabaseUser:
    """
    Get current active user (Supabase users are active by default if authenticated)
    """
    return current_user
