import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.config import Settings


class TokenCipher:
    """Encrypts GitHub tokens at rest with Fernet (AES-128-CBC + HMAC-SHA256).

    The key is kept outside the database, so a copied or leaked reviewmind.db exposes only
    ciphertext. On a single machine the key file sits next to the database, which makes this
    defence in depth rather than a vault; in a deployment the key comes from SECRET_KEY.
    """

    def __init__(self, key: bytes | str):
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str | None:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            return None


def token_hint(token: str) -> str | None:
    return token[-4:] if len(token) >= 12 else None


def load_or_create_key(settings: Settings) -> bytes:
    if settings.secret_key is not None and settings.secret_key.get_secret_value().strip():
        return settings.secret_key.get_secret_value().strip().encode()

    path = Path(settings.secret_key_file)
    if path.exists():
        return path.read_bytes().strip()

    path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    # O_EXCL + 0600: owner-only from the first byte, and an existing key is never overwritten.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(key)
    return key
