"""Password hashing and verification helpers."""

import bcrypt


def get_password_hash(password: str) -> str:
    """Return a bcrypt hash suitable for storage in the database."""
    if not isinstance(password, str):
        raise TypeError("password must be a string")

    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str | None) -> bool:
    """Return whether *password* matches a bcrypt hash."""
    if not isinstance(password, str) or not isinstance(hashed_password, str):
        return False

    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (TypeError, ValueError):
        return False
