"""
Unified Email Account Service

Manages both Gmail and Outlook accounts in a single service.
Uses the `email_accounts` table with provider column for differentiation.
"""

import os
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta

from supabase import Client
from auth import supabase
from encryption import encrypt_token, decrypt_token

# Gmail imports
from google.oauth2.credentials import Credentials as GoogleCredentials

# Outlook token structure (stored as JSON)
# Access tokens from MSAL are stored differently than Google

logger = logging.getLogger(__name__)


class EmailAccountService:
    """
    Unified service for managing email accounts from multiple providers.
    Supports: Gmail, Outlook
    """

    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client

    async def save_account(
        self,
        user_id: str,
        email_address: str,
        provider: str,
        access_token: str,
        refresh_token: str,
        token_expiry: Optional[datetime] = None,
        scopes: Optional[List[str]] = None,
        display_name: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Save an email account (Gmail or Outlook) to the database.

        Args:
            user_id: Supabase auth user ID
            email_address: Email address of the account
            provider: 'gmail' or 'outlook'
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            token_expiry: Token expiration datetime
            scopes: List of OAuth scopes
            display_name: Display name for the account

        Returns:
            The saved account record or None if failed
        """
        try:
            # Check if this is user's first account (to set as primary)
            existing = self.supabase.table("email_accounts")\
                .select("id")\
                .eq("user_id", user_id)\
                .execute()

            is_primary = len(existing.data) == 0

            # Encrypt tokens for secure storage
            encrypted_access = encrypt_token(access_token)
            encrypted_refresh = encrypt_token(refresh_token)

            data = {
                "user_id": user_id,
                "email_address": email_address,
                "display_name": display_name or email_address,
                "provider": provider,
                "access_token": encrypted_access,
                "refresh_token": encrypted_refresh,
                "token_expiry": token_expiry.isoformat() if token_expiry else None,
                "scopes": scopes or [],
                "is_primary": is_primary,
                "is_active": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            result = self.supabase.table("email_accounts")\
                .upsert(data, on_conflict="user_id,email_address")\
                .execute()

            logger.info(f"Saved {provider} account {email_address} for user {user_id}")
            return result.data[0] if result.data else None

        except Exception as e:
            logger.error(f"Error saving account {email_address}: {e}")
            return None

    async def save_gmail_account(
        self,
        user_id: str,
        email_address: str,
        credentials: GoogleCredentials,
        display_name: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Save a Gmail account from Google OAuth credentials.

        Args:
            user_id: Supabase auth user ID
            email_address: Gmail address
            credentials: Google OAuth credentials object
            display_name: Display name

        Returns:
            Saved account record
        """
        return await self.save_account(
            user_id=user_id,
            email_address=email_address,
            provider="gmail",
            access_token=credentials.token,
            refresh_token=credentials.refresh_token or "",
            token_expiry=credentials.expiry,
            scopes=list(credentials.scopes) if credentials.scopes else [],
            display_name=display_name,
        )

    async def save_outlook_account(
        self,
        user_id: str,
        email_address: str,
        token_response: Dict,
        display_name: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Save an Outlook account from MSAL token response.

        Args:
            user_id: Supabase auth user ID
            email_address: Outlook email address
            token_response: MSAL token response dictionary
            display_name: Display name

        Returns:
            Saved account record
        """
        # Parse token expiry from MSAL response
        expires_in_raw = token_response.get("expires_in", 3600)
        try:
            expires_in = int(expires_in_raw)
        except (TypeError, ValueError):
            expires_in = 3600

        token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        return await self.save_account(
            user_id=user_id,
            email_address=email_address,
            provider="outlook",
            access_token=token_response.get("access_token", ""),
            refresh_token=token_response.get("refresh_token", ""),
            token_expiry=token_expiry,
            scopes=token_response.get("scope", "").split(" "),
            display_name=display_name,
        )

    async def get_account(self, user_id: str, account_id: str) -> Optional[Dict]:
        """
        Get a specific email account.

        Args:
            user_id: Supabase auth user ID
            account_id: Account UUID

        Returns:
            Account record or None
        """
        try:
            result = self.supabase.table("email_accounts")\
                .select("*")\
                .eq("user_id", user_id)\
                .eq("id", account_id)\
                .single()\
                .execute()

            return result.data if result.data else None
        except Exception as e:
            logger.error(f"Error getting account {account_id}: {e}")
            return None

    async def get_all_accounts(self, user_id: str) -> List[Dict]:
        """
        Get all email accounts for a user.

        Args:
            user_id: Supabase auth user ID

        Returns:
            List of account records (without decrypted tokens)
        """
        try:
            result = self.supabase.table("email_accounts")\
                .select("id, email_address, display_name, provider, is_primary, is_active, created_at, last_sync_at")\
                .eq("user_id", user_id)\
                .eq("is_active", True)\
                .order("is_primary", desc=True)\
                .order("created_at")\
                .execute()

            return result.data or []
        except Exception as e:
            logger.error(f"Error getting accounts for user {user_id}: {e}")
            return []

    async def get_accounts_by_provider(self, user_id: str, provider: str) -> List[Dict]:
        """
        Get all accounts for a specific provider.

        Args:
            user_id: Supabase auth user ID
            provider: 'gmail' or 'outlook'

        Returns:
            List of account records
        """
        try:
            result = self.supabase.table("email_accounts")\
                .select("*")\
                .eq("user_id", user_id)\
                .eq("provider", provider)\
                .eq("is_active", True)\
                .execute()

            return result.data or []
        except Exception as e:
            logger.error(f"Error getting {provider} accounts: {e}")
            return []

    async def get_primary_account(self, user_id: str) -> Optional[Dict]:
        """
        Get the user's primary email account.

        Args:
            user_id: Supabase auth user ID

        Returns:
            Primary account record or None
        """
        try:
            result = self.supabase.table("email_accounts")\
                .select("*")\
                .eq("user_id", user_id)\
                .eq("is_primary", True)\
                .single()\
                .execute()

            return result.data if result.data else None
        except Exception as e:
            logger.error(f"Error getting primary account: {e}")
            return None

    async def get_decrypted_tokens(self, user_id: str, account_id: str) -> Optional[Dict]:
        """
        Get decrypted tokens for an account.

        Args:
            user_id: Supabase auth user ID
            account_id: Account UUID

        Returns:
            Dictionary with access_token, refresh_token, provider
        """
        logger.info(f"[DECRYPT_TOKENS] Getting tokens for account {account_id}, user {user_id}")
        account = await self.get_account(user_id, account_id)
        if not account:
            logger.error(f"[DECRYPT_TOKENS] Account {account_id} not found")
            return None

        logger.info(f"[DECRYPT_TOKENS] Account found: {account['email_address']}, provider: {account.get('provider')}")

        try:
            logger.info(f"[DECRYPT_TOKENS] Decrypting access token...")
            access_token = decrypt_token(account["access_token"])
            logger.info(f"[DECRYPT_TOKENS] Access token decrypted successfully")

            logger.info(f"[DECRYPT_TOKENS] Decrypting refresh token...")
            refresh_token = decrypt_token(account["refresh_token"])
            logger.info(f"[DECRYPT_TOKENS] Refresh token decrypted successfully")

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "provider": account["provider"],
                "token_expiry": account.get("token_expiry"),
                "scopes": account.get("scopes", []),
            }
        except Exception as e:
            logger.error(f"[DECRYPT_TOKENS] Error decrypting tokens for account {account_id}: {type(e).__name__}: {e}", exc_info=True)

            # Check if this is an InvalidToken error (encryption key mismatch)
            if "InvalidToken" in str(type(e).__name__):
                logger.error(f"[DECRYPT_TOKENS] This appears to be an encryption key mismatch!")
                logger.error(f"[DECRYPT_TOKENS] The token was encrypted with a different TOKEN_ENCRYPTION_KEY than the current one.")
                logger.error(f"[DECRYPT_TOKENS] Solution: User needs to re-authenticate this account.")

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
                    logger.info(f"[DECRYPT_TOKENS] Cleared invalid tokens for account {account_id}")
                except Exception as clear_err:
                    logger.error(f"[DECRYPT_TOKENS] Failed to clear invalid tokens: {clear_err}")

            return None

    async def get_gmail_credentials(self, user_id: str, account_id: str) -> Optional[GoogleCredentials]:
        """
        Get Google OAuth credentials for a Gmail account.

        Args:
            user_id: Supabase auth user ID
            account_id: Account UUID

        Returns:
            Google Credentials object or None
        """
        account = await self.get_account(user_id, account_id)
        if not account or account.get("provider") != "gmail":
            return None

        try:
            token_data = {
                "token": decrypt_token(account["access_token"]),
                "refresh_token": decrypt_token(account["refresh_token"]),
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "scopes": account.get("scopes", []),
            }

            return GoogleCredentials.from_authorized_user_info(token_data)
        except Exception as e:
            logger.error(f"Error creating Gmail credentials: {e}")
            return None

    async def get_outlook_access_token(self, user_id: str, account_id: str) -> Optional[str]:
        """
        Get access token for an Outlook account.
        Handles token refresh if needed.

        Args:
            user_id: Supabase auth user ID
            account_id: Account UUID

        Returns:
            Valid access token or None
        """
        tokens = await self.get_decrypted_tokens(user_id, account_id)
        if not tokens or tokens.get("provider") != "outlook":
            return None

        # Check if token is expired
        token_expiry = tokens.get("token_expiry")
        if token_expiry:
            try:
                expiry_dt = datetime.fromisoformat(token_expiry.replace("Z", "+00:00"))
                if expiry_dt < datetime.now(timezone.utc):
                    # Token expired, refresh it
                    return await self._refresh_outlook_token(user_id, account_id, tokens["refresh_token"])
            except (ValueError, TypeError):
                pass

        return tokens.get("access_token")

    async def _refresh_outlook_token(
        self,
        user_id: str,
        account_id: str,
        refresh_token: str
    ) -> Optional[str]:
        """
        Refresh an expired Outlook access token.

        Returns:
            New access token or None
        """
        try:
            from outlook_service import refresh_access_token

            new_tokens = refresh_access_token(refresh_token)

            # Update stored tokens
            encrypted_access = encrypt_token(new_tokens["access_token"])
            encrypted_refresh = encrypt_token(new_tokens.get("refresh_token", refresh_token))

            expires_in_raw = new_tokens.get("expires_in", 3600)
            try:
                expires_in = int(expires_in_raw)
            except (TypeError, ValueError):
                expires_in = 3600

            new_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            self.supabase.table("email_accounts")\
                .update({
                    "access_token": encrypted_access,
                    "refresh_token": encrypted_refresh,
                    "token_expiry": new_expiry.isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })\
                .eq("id", account_id)\
                .execute()

            logger.info(f"Refreshed Outlook token for account {account_id}")
            return new_tokens["access_token"]

        except Exception as e:
            logger.error(f"Error refreshing Outlook token: {e}")
            return None

    async def update_last_sync(self, user_id: str, account_id: str) -> bool:
        """
        Update the last_sync_at timestamp for an account.

        Args:
            user_id: Supabase auth user ID
            account_id: Account UUID

        Returns:
            True if updated, False otherwise
        """
        try:
            self.supabase.table("email_accounts")\
                .update({
                    "last_sync_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })\
                .eq("user_id", user_id)\
                .eq("id", account_id)\
                .execute()

            return True
        except Exception as e:
            logger.error(f"Error updating last sync: {e}")
            return False

    async def set_primary(self, user_id: str, account_id: str) -> bool:
        """
        Set an account as the primary account.

        Args:
            user_id: Supabase auth user ID
            account_id: Account UUID to set as primary

        Returns:
            True if successful, False otherwise
        """
        try:
            # Remove primary from all accounts
            self.supabase.table("email_accounts")\
                .update({"is_primary": False})\
                .eq("user_id", user_id)\
                .execute()

            # Set new primary
            result = self.supabase.table("email_accounts")\
                .update({"is_primary": True})\
                .eq("user_id", user_id)\
                .eq("id", account_id)\
                .execute()

            return len(result.data) > 0 if result.data else False
        except Exception as e:
            logger.error(f"Error setting primary account: {e}")
            return False

    async def delete_account(self, user_id: str, account_id: str) -> bool:
        """
        Delete (deactivate) an email account.

        Args:
            user_id: Supabase auth user ID
            account_id: Account UUID

        Returns:
            True if deleted, False otherwise
        """
        try:
            # Soft delete by setting is_active to False
            result = self.supabase.table("email_accounts")\
                .update({"is_active": False})\
                .eq("user_id", user_id)\
                .eq("id", account_id)\
                .execute()

            return len(result.data) > 0 if result.data else False
        except Exception as e:
            logger.error(f"Error deleting account {account_id}: {e}")
            return False

    async def hard_delete_account(self, user_id: str, account_id: str) -> bool:
        """
        Permanently delete an email account.

        Args:
            user_id: Supabase auth user ID
            account_id: Account UUID

        Returns:
            True if deleted, False otherwise
        """
        try:
            result = self.supabase.table("email_accounts")\
                .delete()\
                .eq("user_id", user_id)\
                .eq("id", account_id)\
                .execute()

            return len(result.data) > 0 if result.data else False
        except Exception as e:
            logger.error(f"Error hard deleting account {account_id}: {e}")
            return False


# Global instance
email_account_service = EmailAccountService(supabase)
