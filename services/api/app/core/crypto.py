import nacl.secret
import nacl.utils
from .config import settings

def _get_key() -> bytes:
    # Ensure key is exactly 32 bytes for SecretBox
    key = settings.TOKEN_ENCRYPTION_KEY.get_secret_value().encode("utf-8")
    if len(key) < 32:
        key = key.ljust(32, b"\0")
    return key[:32]

def encrypt_token(token: str) -> bytes:
    box = nacl.secret.SecretBox(_get_key())
    nonce = nacl.utils.random(nacl.secret.SecretBox.NONCE_SIZE)
    return box.encrypt(token.encode("utf-8"), nonce)

def decrypt_token(encrypted_token: bytes) -> str:
    box = nacl.secret.SecretBox(_get_key())
    return box.decrypt(encrypted_token).decode("utf-8")
