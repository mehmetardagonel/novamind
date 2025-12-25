"""
Gmail Account Service - Updated to use email_accounts table

This service manages Gmail accounts using the unified email_accounts table.
It maintains backward compatibility with existing code while using the new schema.
"""

from typing import List, Optional, Dict
import os
import json
import logging
from datetime import datetime, timezone

from supabase import Client
from auth import supabase
from encryption import encrypt_token, decrypt_token
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)


class GmailAccountService:
    """
    Gmail account service using the unified email_accounts table.
    """

    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client

    async def save_account(
        self,
        user_id: str,
        email_address: str,
        credentials: Credentials,
        display_name: Optional[str] = None
    ) -> Dict:
        """Save Gmail account OAuth token to database"""
        # Encrypt tokens separately
        encrypted_access = encrypt_token(credentials.token) if credentials.token else ""
        encrypted_refresh = encrypt_token(credentials.refresh_token) if credentials.refresh_token else ""

        # Check if this is user's first account
        existing = self.supabase.table("email_accounts")\
            .select("id")\
            .eq("user_id", user_id)\
            .execute()

        is_primary = len(existing.data) == 0

        data = {
            "user_id": user_id,
            "email_address": email_address,
            "display_name": display_name or email_address,
            "provider": "gmail",
            "access_token": encrypted_access,
            "refresh_token": encrypted_refresh,
            "token_expiry": credentials.expiry.isoformat() if credentials.expiry else None,
            "scopes": list(credentials.scopes) if credentials.scopes else [],
            "is_primary": is_primary,
            "is_active": True,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        result = self.supabase.table("email_accounts")\
            .upsert(data, on_conflict="user_id,email_address")\
            .execute()

        logger.info(f"Saved Gmail account {email_address} for user {user_id}")
        return result.data[0] if result.data else None

    async def get_account(self, user_id: str, account_id: str) -> Optional[Dict]:
        """Get specific Gmail account"""
        result = self.supabase.table("email_accounts")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("id", account_id)\
            .eq("provider", "gmail")\
            .single()\
            .execute()

        return result.data if result.data else None

    async def get_all_accounts(self, user_id: str) -> List[Dict]:
        """Get all Gmail accounts for a user"""
        result = self.supabase.table("email_accounts")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("provider", "gmail")\
            .eq("is_active", True)\
            .order("is_primary", desc=True)\
            .order("created_at")\
            .execute()

        return result.data or []

    async def get_credentials(self, user_id: str, account_id: str) -> Optional[Credentials]:
        """Get decrypted credentials for an account"""
        logger.info(f"[DECRYPT] Getting credentials for account {account_id}, user {user_id}")
        account = await self.get_account(user_id, account_id)
        if not account:
            logger.error(f"[DECRYPT] Account {account_id} not found in database")
            return None

        logger.info(f"[DECRYPT] Account found: {account['email_address']}, has access_token: {bool(account.get('access_token'))}, has refresh_token: {bool(account.get('refresh_token'))}")

        if account.get("access_token"):
            logger.info(f"[DECRYPT] Access token length: {len(account['access_token'])} chars, first 20: {account['access_token'][:20]}...")
        if account.get("refresh_token"):
            logger.info(f"[DECRYPT] Refresh token length: {len(account['refresh_token'])} chars, first 20: {account['refresh_token'][:20]}...")

        try:
            # Decrypt tokens
            logger.info(f"[DECRYPT] Starting decryption for account {account_id}")

            access_token = None
            if account.get("access_token"):
                logger.info(f"[DECRYPT] Attempting to decrypt access_token...")
                try:
                    access_token = decrypt_token(account["access_token"])
                    logger.info(f"[DECRYPT] Access token decrypted successfully, length: {len(access_token) if access_token else 0}")
                except Exception as decrypt_err:
                    logger.error(f"[DECRYPT] Failed to decrypt access_token: {type(decrypt_err).__name__}: {decrypt_err}")
                    raise

            refresh_token = None
            if account.get("refresh_token"):
                logger.info(f"[DECRYPT] Attempting to decrypt refresh_token...")
                try:
                    refresh_token = decrypt_token(account["refresh_token"])
                    logger.info(f"[DECRYPT] Refresh token decrypted successfully, length: {len(refresh_token) if refresh_token else 0}")
                except Exception as decrypt_err:
                    logger.error(f"[DECRYPT] Failed to decrypt refresh_token: {type(decrypt_err).__name__}: {decrypt_err}")
                    raise

            # Build credential info dict
            logger.info(f"[DECRYPT] Building credential info dict...")
            token_info = {
                "token": access_token,
                "refresh_token": refresh_token,
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "scopes": account.get("scopes", [])
            }

            logger.info(f"[DECRYPT] Creating Credentials object from token_info...")
            creds = Credentials.from_authorized_user_info(token_info)
            logger.info(f"[DECRYPT] Credentials created successfully for {account_id}")
            return creds

        except Exception as e:
            logger.error(f"[DECRYPT] FATAL: Failed to decrypt token for account {account_id}: {type(e).__name__}: {e}", exc_info=True)
            import traceback
            logger.error(f"[DECRYPT] Traceback: {traceback.format_exc()}")

            # Check if this is an InvalidToken error (encryption key mismatch)
            if "InvalidToken" in str(type(e).__name__):
                logger.error(f"[DECRYPT] This appears to be an encryption key mismatch!")
                logger.error(f"[DECRYPT] The token was encrypted with a different TOKEN_ENCRYPTION_KEY than the current one.")
                logger.error(f"[DECRYPT] Solution: User needs to re-authenticate this account.")

                # Clear the invalid tokens from the database
                try:
                    self.supabase.table("email_accounts")\
                        .update({
                            "access_token": "",
                            "refresh_token": "",
                            "token_expiry": None
                        })\
                        .eq("id", account_id)\
                        .execute()
                    logger.info(f"[DECRYPT] Cleared invalid tokens for account {account_id}")
                except Exception as clear_err:
                    logger.error(f"[DECRYPT] Failed to clear invalid tokens: {clear_err}")

            return None

    async def delete_account(self, user_id: str, account_id: str) -> bool:
        """Delete Gmail account connection (soft delete)"""
        result = self.supabase.table("email_accounts")\
            .update({"is_active": False})\
            .eq("user_id", user_id)\
            .eq("id", account_id)\
            .eq("provider", "gmail")\
            .execute()

        return len(result.data) > 0 if result.data else False

    async def set_primary(self, user_id: str, account_id: str) -> bool:
        """Set an account as primary"""
        # First, remove primary from all Gmail accounts
        self.supabase.table("email_accounts")\
            .update({"is_primary": False})\
            .eq("user_id", user_id)\
            .eq("provider", "gmail")\
            .execute()

        # Set new primary
        result = self.supabase.table("email_accounts")\
            .update({"is_primary": True})\
            .eq("user_id", user_id)\
            .eq("id", account_id)\
            .execute()

        return len(result.data) > 0 if result.data else False


# Global instance
gmail_account_service = GmailAccountService(supabase)
