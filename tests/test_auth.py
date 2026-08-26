from argon2 import PasswordHasher
from argon2.low_level import Type
import pytest

import auth


VALID_PASSWORD = "correct horse battery staple"


@pytest.fixture(autouse=True)
def fast_password_hasher(monkeypatch):
    monkeypatch.setattr(
        auth,
        "_PASSWORD_HASHER",
        PasswordHasher(
            time_cost=1,
            memory_cost=1024,
            parallelism=1,
            hash_len=16,
            salt_len=16,
            type=Type.ID,
        ),
    )


def test_normalize_username_trims_whitespace():
    assert auth.normalize_username("  Alice_User-01  ") == "alice_user-01"


def test_normalize_username_case_normalization():
    assert auth.normalize_username("MiXeD-Case") == "mixed-case"


def test_blank_username_rejected():
    with pytest.raises(auth.InvalidUsernameError):
        auth.validate_username("   ")


def test_too_short_username_rejected():
    with pytest.raises(auth.InvalidUsernameError):
        auth.validate_username("ab")


@pytest.mark.parametrize("username", ["bad user", "bad.user", "_bad", "bad!", "ümlaut"])
def test_invalid_username_rejected(username):
    with pytest.raises(auth.InvalidUsernameError):
        auth.validate_username(username)


def test_short_password_rejected():
    with pytest.raises(auth.InvalidPasswordError):
        auth.validate_password("too-short")


def test_long_password_accepted():
    password = "a" * 128
    assert auth.validate_password(password) == password


def test_unicode_password_accepted():
    password = "বাংলা password 🔐 12345"
    hashed = auth.hash_password(password)
    assert auth.verify_password(password, hashed) is True


def test_password_hash_differs_from_plaintext():
    hashed = auth.hash_password(VALID_PASSWORD)
    assert hashed != VALID_PASSWORD
    assert hashed.startswith("$argon2id$")


def test_correct_password_verifies():
    hashed = auth.hash_password(VALID_PASSWORD)
    assert auth.verify_password(VALID_PASSWORD, hashed) is True


def test_incorrect_password_fails():
    hashed = auth.hash_password(VALID_PASSWORD)
    assert auth.verify_password("wrong horse battery staple", hashed) is False


def test_same_password_hashes_do_not_need_to_match():
    first = auth.hash_password(VALID_PASSWORD)
    second = auth.hash_password(VALID_PASSWORD)

    assert first != second
    assert auth.verify_password(VALID_PASSWORD, first) is True
    assert auth.verify_password(VALID_PASSWORD, second) is True
