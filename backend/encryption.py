from cryptography.fernet import Fernet
from typing import Optional
import os
import base64
import logging

logger = logging.getLogger(__name__)

# Encryption key from environment (must be 32 url-safe base64 chars)
ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY")

if not ENCRYPTION_KEY:
    # Generate a key for development (PRODUCTION'da mutlaka .env'de olmalı!)
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    logger.warning(f"WARNING: Generated encryption key: {ENCRYPTION_KEY}")
    logger.warning("Add this to your .env file as TOKEN_ENCRYPTION_KEY")
else:
    logger.info(f"[ENCRYPTION] Encryption key loaded from environment: {len(ENCRYPTION_KEY)} chars")

cipher_suite = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

def encrypt_token(token_json: str) -> str:
    """Encrypt OAuth token JSON for database storage"""
    logger.debug(f"[ENCRYPTION] Encrypting token, input length: {len(token_json)}")
    try:
        encrypted = cipher_suite.encrypt(token_json.encode())
        result = base64.urlsafe_b64encode(encrypted).decode()
        logger.debug(f"[ENCRYPTION] Token encrypted successfully, output length: {len(result)}")
        return result
    except Exception as e:
        logger.error(f"[ENCRYPTION] Encryption failed: {type(e).__name__}: {e}")
        raise

def decrypt_token(encrypted_token: str) -> str:
    """Decrypt OAuth token JSON from database"""
    logger.debug(f"[ENCRYPTION] Decrypting token, input length: {len(encrypted_token)}, first 30: {encrypted_token[:30]}...")
    try:
        logger.debug(f"[ENCRYPTION] Step 1: base64 decoding...")
        decoded = base64.urlsafe_b64decode(encrypted_token.encode())
        logger.debug(f"[ENCRYPTION] Step 1 success: decoded length: {len(decoded)}")

        logger.debug(f"[ENCRYPTION] Step 2: Fernet decryption...")
        decrypted = cipher_suite.decrypt(decoded)
        logger.debug(f"[ENCRYPTION] Step 2 success: decrypted length: {len(decrypted)}")

        logger.debug(f"[ENCRYPTION] Step 3: UTF-8 decoding...")
        result = decrypted.decode()
        logger.debug(f"[ENCRYPTION] Decryption successful, result length: {len(result)}")
        return result
    except Exception as e:
        logger.error(f"[ENCRYPTION] Decryption failed: {type(e).__name__}: {e}")
        logger.error(f"[ENCRYPTION] Input token: {encrypted_token[:50]}...")
        raise
