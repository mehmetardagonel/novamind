from typing import List, Optional, Dict
import json
import logging
from supabase import Client
from auth import supabase
from encryption import encrypt_token, decrypt_token
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)

class GmailAccountService:
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
        token_json = credentials.to_json()
        encrypted = encrypt_token(token_json)

        # Check if this is user's first account
        existing = self.supabase.table("gmail_accounts")\
            .select("id")\
            .eq("user_id", user_id)\
            .execute()

        is_primary = len(existing.data) == 0

        data = {
            "user_id": user_id,
            "email_address": email_address,
            "display_name": display_name or email_address,
            "encrypted_token": encrypted,
            "is_primary": is_primary
        }

        result = self.supabase.table("gmail_accounts")\
            .upsert(data, on_conflict="user_id,email_address")\
            .execute()

        logger.info(f"Saved Gmail account {email_address} for user {user_id}")
        return result.data[0] if result.data else None

    async def get_account(self, user_id: str, account_id: str) -> Optional[Dict]:
        """Get specific Gmail account"""
        result = self.supabase.table("gmail_accounts")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("id", account_id)\
            .single()\
            .execute()

        return result.data if result.data else None

    async def get_all_accounts(self, user_id: str) -> List[Dict]:
        """Get all Gmail accounts for a user"""
        result = self.supabase.table("gmail_accounts")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("is_primary", desc=True)\
            .order("created_at")\
            .execute()

        return result.data or []

    async def get_credentials(self, user_id: str, account_id: str) -> Optional[Credentials]:
        """Get decrypted credentials for an account"""
        account = await self.get_account(user_id, account_id)
        if not account:
            return None

        try:
            token_json = decrypt_token(account["encrypted_token"])
            creds = Credentials.from_authorized_user_info(
                json.loads(token_json)
            )
            return creds
        except Exception as e:
            logger.error(f"Failed to decrypt token for account {account_id}: {e}")
            return None

    async def delete_account(self, user_id: str, account_id: str) -> bool:
        """Delete Gmail account connection"""
        result = self.supabase.table("gmail_accounts")\
            .delete()\
            .eq("user_id", user_id)\
            .eq("id", account_id)\
            .execute()

        return len(result.data) > 0 if result.data else False

    async def set_primary(self, user_id: str, account_id: str) -> bool:
        """Set an account as primary"""
        # First, remove primary from all accounts
        self.supabase.table("gmail_accounts")\
            .update({"is_primary": False})\
            .eq("user_id", user_id)\
            .execute()

        # Set new primary
        result = self.supabase.table("gmail_accounts")\
            .update({"is_primary": True})\
            .eq("user_id", user_id)\
            .eq("id", account_id)\
            .execute()

        return len(result.data) > 0 if result.data else False

# Global instance
gmail_account_service = GmailAccountService(supabase)
