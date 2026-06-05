from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


PASSWORD_HASH_PREFIX = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 210_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _derive_password_digest(password, salt, PASSWORD_HASH_ITERATIONS)
    return "$".join(
        [
            PASSWORD_HASH_PREFIX,
            str(PASSWORD_HASH_ITERATIONS),
            _b64encode(salt),
            _b64encode(digest),
        ]
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        prefix, iterations_text, salt_text, digest_text = password_hash.split("$", 3)
        if prefix != PASSWORD_HASH_PREFIX:
            return False

        iterations = int(iterations_text)
        salt = _b64decode(salt_text)
        expected_digest = _b64decode(digest_text)
    except (ValueError, TypeError):
        return False

    actual_digest = _derive_password_digest(password, salt, iterations)
    return hmac.compare_digest(actual_digest, expected_digest)


def create_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _derive_password_digest(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))
