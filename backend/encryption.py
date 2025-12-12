from cryptography.fernet import Fernet
from typing import Optional
import os
import base64

# Encryption key from environment (must be 32 url-safe base64 chars)
ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY")

if not ENCRYPTION_KEY:
    # Generate a key for development (PRODUCTION'da mutlaka .env'de olmalı!)
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    print(f"WARNING: Generated encryption key: {ENCRYPTION_KEY}")
    print("Add this to your .env file as TOKEN_ENCRYPTION_KEY")

cipher_suite = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

def encrypt_token(token_json: str) -> str:
    """Encrypt OAuth token JSON for database storage"""
    encrypted = cipher_suite.encrypt(token_json.encode())
    return base64.urlsafe_b64encode(encrypted).decode()

def decrypt_token(encrypted_token: str) -> str:
    """Decrypt OAuth token JSON from database"""
    decoded = base64.urlsafe_b64decode(encrypted_token.encode())
    decrypted = cipher_suite.decrypt(decoded)
    return decrypted.decode()
