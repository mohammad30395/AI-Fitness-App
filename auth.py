"""Authentication helpers for username/password accounts.

Username normalization is intentionally conservative:
- trim surrounding whitespace
- casefold for case-insensitive login/uniqueness
- allow only lowercase ASCII letters, numbers, underscores, and hyphens
- require 3-32 characters and an alphanumeric first character
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type

import db


USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 32
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 4096

_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,31}$")
_PASSWORD_HASHER = PasswordHasher(type=Type.ID)


class AuthValidationError(ValueError):
    """Base exception for invalid authentication input."""


class InvalidUsernameError(AuthValidationError):
    """Raised when a username fails validation."""


class InvalidPasswordError(AuthValidationError):
    """Raised when a password fails validation."""


class AccountAlreadyExistsError(RuntimeError):
    """Raised when a normalized username is already registered."""


class AccountStorageError(RuntimeError):
    """Raised when account persistence fails."""


class AuthenticationError(RuntimeError):
    """Raised when username/password authentication fails."""


def normalize_username(username: str) -> str:
    """Return the deterministic normalized username."""
    if not isinstance(username, str):
        raise InvalidUsernameError("Username must be a string.")

    normalized = username.strip().casefold()
    if not normalized:
        raise InvalidUsernameError("Username is required.")

    return normalized


def validate_username(username: str) -> str:
    """Validate and return the normalized username."""
    normalized = normalize_username(username)

    if not (USERNAME_MIN_LENGTH <= len(normalized) <= USERNAME_MAX_LENGTH):
        raise InvalidUsernameError("Username must be 3 to 32 characters.")

    if not _USERNAME_RE.fullmatch(normalized):
        raise InvalidUsernameError(
            "Username may contain only letters, numbers, underscores, and hyphens, "
            "and must start with a letter or number."
        )

    return normalized


def validate_password(password: str) -> str:
    """Validate and return the original password without modification."""
    if not isinstance(password, str):
        raise InvalidPasswordError("Password must be a string.")

    if len(password) < PASSWORD_MIN_LENGTH:
        raise InvalidPasswordError("Password must be at least 12 characters.")

    if len(password) > PASSWORD_MAX_LENGTH:
        raise InvalidPasswordError("Password is too long.")

    return password


def hash_password(password: str) -> str:
    """Hash a password with Argon2id."""
    return _PASSWORD_HASHER.hash(validate_password(password))


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against an Argon2id encoded hash."""
    try:
        validate_password(password)
    except InvalidPasswordError:
        return False

    if not isinstance(password_hash, str) or not password_hash:
        return False

    try:
        return bool(_PASSWORD_HASHER.verify(password_hash, password))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def _is_duplicate_account_error(error: Exception) -> bool:
    error_text = f"{type(error).__name__} {error}".casefold()
    duplicate_markers = (
        "duplicate",
        "already exists",
        "conflict",
        "409",
    )
    return any(marker in error_text for marker in duplicate_markers)


def create_account(username: str, password: str) -> dict[str, str]:
    """Create a username/password account and return only safe account fields."""
    normalized_username = validate_username(username)
    validated_password = validate_password(password)
    display_username = username.strip()
    account_id = str(uuid.uuid4())
    account_document = {
        "_id": normalized_username,
        "account_id": account_id,
        "username": display_username,
        "password_hash": hash_password(validated_password),
        "created_at": datetime.now(timezone.utc),
    }

    try:
        db.get_accounts_collection().insert_one(account_document)
    except Exception as error:
        if _is_duplicate_account_error(error):
            raise AccountAlreadyExistsError("Username is already registered.") from error
        raise AccountStorageError(f"Creating account failed ({type(error).__name__}).") from error

    return {
        "account_id": account_id,
        "username": display_username,
    }


def authenticate(username: str, password: str) -> dict[str, str]:
    """Authenticate a username/password pair and return only safe account fields."""
    failure_message = "Invalid username or password."
    try:
        normalized_username = validate_username(username)
    except InvalidUsernameError as error:
        raise AuthenticationError(failure_message) from error

    try:
        account = db.get_accounts_collection().find_one({"_id": normalized_username})
    except Exception as error:
        raise AccountStorageError(f"Authenticating account failed ({type(error).__name__}).") from error

    if account is None:
        raise AuthenticationError(failure_message)

    if not isinstance(account, dict):
        raise AccountStorageError("Stored account record is malformed.")

    password_hash = account.get("password_hash")
    if not isinstance(password_hash, str) or not password_hash:
        raise AccountStorageError("Stored account record is malformed.")

    if not verify_password(password, password_hash):
        raise AuthenticationError(failure_message)

    account_id = account.get("account_id")
    display_username = account.get("username")
    if not isinstance(account_id, str) or not account_id.strip():
        raise AccountStorageError("Stored account record is malformed.")
    if not isinstance(display_username, str) or not display_username.strip():
        raise AccountStorageError("Stored account record is malformed.")

    return {
        "account_id": account_id,
        "username": display_username,
    }
