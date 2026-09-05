from datetime import timezone
import uuid

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


class FakeDuplicateAccountError(RuntimeError):
    pass


class FakeAccountsCollection:
    def __init__(self):
        self.documents = []
        self.find_filters = []
        self.update_calls = []

    def insert_one(self, document):
        if any(existing["_id"] == document["_id"] for existing in self.documents):
            raise FakeDuplicateAccountError(
                f"duplicate key token=AstraCS:super-secret-token password={VALID_PASSWORD}"
            )
        self.documents.append(dict(document))
        return object()

    def find_one(self, filter_doc):
        self.find_filters.append(dict(filter_doc))
        if set(filter_doc) != {"_id"}:
            raise AssertionError("authentication must query by normalized _id only")
        for document in self.documents:
            if document["_id"] == filter_doc["_id"]:
                return dict(document)
        return None

    def update_one(self, filter_doc, update_doc):
        self.update_calls.append((dict(filter_doc), dict(update_doc)))
        if set(filter_doc) != {"_id"}:
            raise AssertionError("password update must query by normalized _id only")
        for document in self.documents:
            if document["_id"] == filter_doc["_id"]:
                document.update(update_doc.get("$set", {}))

                class UpdateResult:
                    matched_count = 1

                return UpdateResult()

        class UpdateResult:
            matched_count = 0

        return UpdateResult()


def patch_accounts_collection(monkeypatch, collection):
    monkeypatch.setattr(auth.db, "get_accounts_collection", lambda: collection)


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


def test_create_account_persists_safe_account_document(monkeypatch):
    collection = FakeAccountsCollection()
    patch_accounts_collection(monkeypatch, collection)

    result = auth.create_account("  Alice_User-01  ", VALID_PASSWORD)

    assert len(collection.documents) == 1
    document = collection.documents[0]
    assert document["_id"] == "alice_user-01"
    assert document["username"] == "Alice_User-01"
    assert uuid.UUID(document["account_id"]).version == 4
    assert document["account_id"] != document["_id"]
    assert document["account_id"] != document["username"]
    assert document["password_hash"].startswith("$argon2id$")
    assert document["password_hash"] != VALID_PASSWORD
    assert "password" not in document
    assert "confirm_password" not in document
    assert VALID_PASSWORD not in document.values()
    assert document["created_at"].tzinfo is not None
    assert document["created_at"].utcoffset() == timezone.utc.utcoffset(document["created_at"])
    assert result == {
        "account_id": document["account_id"],
        "username": "Alice_User-01",
    }
    assert "password_hash" not in result


def test_create_account_generates_different_account_ids(monkeypatch):
    collection = FakeAccountsCollection()
    patch_accounts_collection(monkeypatch, collection)

    first = auth.create_account("first-user", VALID_PASSWORD)
    second = auth.create_account("second-user", VALID_PASSWORD)

    assert first["account_id"] != second["account_id"]
    assert collection.documents[0]["account_id"] != collection.documents[1]["account_id"]


def test_create_account_rejects_duplicate_username_cleanly(monkeypatch):
    collection = FakeAccountsCollection()
    patch_accounts_collection(monkeypatch, collection)

    auth.create_account("existing-user", VALID_PASSWORD)

    with pytest.raises(auth.AccountAlreadyExistsError) as exc_info:
        auth.create_account("existing-user", VALID_PASSWORD)

    message = str(exc_info.value)
    assert message == "Username is already registered."
    assert VALID_PASSWORD not in message
    assert "AstraCS" not in message


def test_create_account_case_insensitive_duplicate_username_collides(monkeypatch):
    collection = FakeAccountsCollection()
    patch_accounts_collection(monkeypatch, collection)

    auth.create_account("Mixed-Case-User", VALID_PASSWORD)

    with pytest.raises(auth.AccountAlreadyExistsError):
        auth.create_account("mixed-case-user", VALID_PASSWORD)

    assert len(collection.documents) == 1


def test_create_account_sanitizes_database_exception(monkeypatch):
    secret = "AstraCS:super-secret-token"

    class FailingAccountsCollection:
        def insert_one(self, document):
            raise RuntimeError(
                f"insert failed token={secret} password={VALID_PASSWORD} hash={document['password_hash']}"
            )

    patch_accounts_collection(monkeypatch, FailingAccountsCollection())

    with pytest.raises(auth.AccountStorageError) as exc_info:
        auth.create_account("new-user", VALID_PASSWORD)

    message = str(exc_info.value)
    assert "Creating account failed (RuntimeError)." == message
    assert secret not in message
    assert VALID_PASSWORD not in message
    assert "argon2" not in message


def test_authenticate_valid_username_password_returns_safe_account(monkeypatch):
    collection = FakeAccountsCollection()
    patch_accounts_collection(monkeypatch, collection)
    created = auth.create_account("login-user", VALID_PASSWORD)

    result = auth.authenticate("login-user", VALID_PASSWORD)

    assert result == {
        "account_id": created["account_id"],
        "username": "login-user",
    }
    assert "password_hash" not in result
    assert "password" not in result
    assert collection.find_filters == [{"_id": "login-user"}]


def test_authenticate_case_insensitive_username_login_works(monkeypatch):
    collection = FakeAccountsCollection()
    patch_accounts_collection(monkeypatch, collection)
    created = auth.create_account("Mixed-Case-User", VALID_PASSWORD)

    result = auth.authenticate("  mixed-case-user  ", VALID_PASSWORD)

    assert result["account_id"] == created["account_id"]
    assert result["username"] == "Mixed-Case-User"
    assert collection.find_filters == [{"_id": "mixed-case-user"}]


def test_authenticate_wrong_password_and_missing_username_fail_generically(monkeypatch):
    collection = FakeAccountsCollection()
    patch_accounts_collection(monkeypatch, collection)
    auth.create_account("known-user", VALID_PASSWORD)

    with pytest.raises(auth.AuthenticationError) as wrong_password:
        auth.authenticate("known-user", "wrong horse battery staple")
    with pytest.raises(auth.AuthenticationError) as missing_username:
        auth.authenticate("missing-user", VALID_PASSWORD)

    assert str(wrong_password.value) == "Invalid username or password."
    assert str(missing_username.value) == "Invalid username or password."
    assert str(wrong_password.value) == str(missing_username.value)
    assert VALID_PASSWORD not in str(missing_username.value)
    assert "wrong horse battery staple" not in str(wrong_password.value)
    assert "password_hash" not in str(wrong_password.value)


def test_authenticate_malformed_account_document_fails_safely(monkeypatch):
    class MalformedAccountsCollection:
        def find_one(self, filter_doc):
            return {
                "_id": "broken-user",
                "username": "broken-user",
                "password_hash": auth.hash_password(VALID_PASSWORD),
            }

    patch_accounts_collection(monkeypatch, MalformedAccountsCollection())

    with pytest.raises(auth.AccountStorageError) as exc_info:
        auth.authenticate("broken-user", VALID_PASSWORD)

    message = str(exc_info.value)
    assert message == "Stored account record is malformed."
    assert VALID_PASSWORD not in message
    assert "password_hash" not in message


def test_authenticate_stored_invalid_password_hash_fails_safely(monkeypatch):
    class InvalidHashAccountsCollection:
        def find_one(self, filter_doc):
            return {
                "_id": "invalid-hash-user",
                "account_id": "account-1",
                "username": "invalid-hash-user",
                "password_hash": "not-an-argon2-hash",
            }

    patch_accounts_collection(monkeypatch, InvalidHashAccountsCollection())

    with pytest.raises(auth.AuthenticationError) as exc_info:
        auth.authenticate("invalid-hash-user", VALID_PASSWORD)

    message = str(exc_info.value)
    assert message == "Invalid username or password."
    assert VALID_PASSWORD not in message
    assert "not-an-argon2-hash" not in message


def test_authenticate_sanitizes_database_exception(monkeypatch):
    secret = "AstraCS:super-secret-token"

    class FailingAccountsCollection:
        def find_one(self, filter_doc):
            raise RuntimeError(
                f"read failed token={secret} password={VALID_PASSWORD} hash=$argon2id$secret"
            )

    patch_accounts_collection(monkeypatch, FailingAccountsCollection())

    with pytest.raises(auth.AccountStorageError) as exc_info:
        auth.authenticate("new-user", VALID_PASSWORD)

    message = str(exc_info.value)
    assert message == "Authenticating account failed (RuntimeError)."
    assert secret not in message
    assert VALID_PASSWORD not in message
    assert "argon2" not in message


def test_update_password_verifies_current_password_and_rehashes(monkeypatch):
    collection = FakeAccountsCollection()
    patch_accounts_collection(monkeypatch, collection)
    auth.create_account("login-user", VALID_PASSWORD)
    old_hash = collection.documents[0]["password_hash"]

    auth.update_password("login-user", VALID_PASSWORD, "new secure password")

    document = collection.documents[0]
    assert document["password_hash"] != old_hash
    assert auth.verify_password(VALID_PASSWORD, document["password_hash"]) is False
    assert auth.verify_password("new secure password", document["password_hash"]) is True
    assert document["updated_at"].tzinfo is not None
    assert document["updated_at"].utcoffset() == timezone.utc.utcoffset(document["updated_at"])
    assert collection.find_filters[-1] == {"_id": "login-user"}
    assert collection.update_calls[-1][0] == {"_id": "login-user"}
    assert "$set" in collection.update_calls[-1][1]
    assert collection.update_calls[-1][1]["$set"]["password_hash"] != "new secure password"
    assert VALID_PASSWORD not in collection.update_calls[-1][1]["$set"].values()


def test_update_password_rejects_wrong_current_password_without_update(monkeypatch):
    collection = FakeAccountsCollection()
    patch_accounts_collection(monkeypatch, collection)
    auth.create_account("login-user", VALID_PASSWORD)
    old_hash = collection.documents[0]["password_hash"]

    with pytest.raises(auth.PasswordUpdateError) as exc_info:
        auth.update_password("login-user", "wrong current password", "new secure password")

    assert str(exc_info.value) == "Current password is incorrect."
    assert collection.documents[0]["password_hash"] == old_hash
    assert collection.update_calls == []


def test_update_password_rejects_reusing_current_password(monkeypatch):
    collection = FakeAccountsCollection()
    patch_accounts_collection(monkeypatch, collection)
    auth.create_account("login-user", VALID_PASSWORD)

    with pytest.raises(auth.InvalidPasswordError) as exc_info:
        auth.update_password("login-user", VALID_PASSWORD, VALID_PASSWORD)

    assert str(exc_info.value) == "New password must be different from the current password."
    assert collection.update_calls == []


def test_update_password_rejects_invalid_new_password_before_update(monkeypatch):
    collection = FakeAccountsCollection()
    patch_accounts_collection(monkeypatch, collection)
    auth.create_account("login-user", VALID_PASSWORD)

    with pytest.raises(auth.InvalidPasswordError):
        auth.update_password("login-user", VALID_PASSWORD, "too-short")

    assert collection.update_calls == []
