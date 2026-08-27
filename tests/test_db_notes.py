from types import SimpleNamespace

import pytest

import db


ACCOUNT_A = "account-a"
ACCOUNT_B = "account-b"
PROFILE_A = "profile-a"
PROFILE_B = "profile-b"


def test_get_notes_collection_uses_configured_collection(monkeypatch):
    values = {"ASTRA_NOTES_COLLECTION": "notes"}
    calls = []
    monkeypatch.setattr(db.config, "get_env_value", lambda name: values.get(name, ""))

    class FakeDatabase:
        def get_collection(self, name):
            calls.append(name)
            return "notes-collection"

    monkeypatch.setattr(db, "get_database", lambda: FakeDatabase())

    assert db.get_notes_collection() == "notes-collection"
    assert calls == ["notes"]


def test_add_note_includes_user_id_text_and_vectorize(monkeypatch):
    calls = []

    class FakeCollection:
        def insert_one(self, document):
            calls.append(document)
            return SimpleNamespace(inserted_id="note-1")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    inserted_id = db.add_note("user-1", "  Readable note text  ")

    assert inserted_id == "note-1"
    assert calls == [
        {
            "user_id": "user-1",
            "text": "Readable note text",
            "$vectorize": "Readable note text",
        }
    ]
    assert "$vector" not in calls[0]


@pytest.mark.parametrize("blank_text", ["", "   ", None])
def test_add_note_rejects_blank_notes_before_database_call(monkeypatch, blank_text):
    class FakeCollection:
        def insert_one(self, document):
            raise AssertionError("insert_one must not be called for invalid text")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidNoteError):
        db.add_note("user-1", blank_text)


def test_list_notes_filters_by_owner_profile_and_limit(monkeypatch):
    profile_checks = []
    calls = []
    documents = [
        {"_id": "note-a", "owner_account_id": ACCOUNT_A, "user_id": PROFILE_A, "text": "A"},
        {"_id": "note-b", "owner_account_id": ACCOUNT_B, "user_id": PROFILE_B, "text": "B"},
        {"_id": "legacy-note", "user_id": PROFILE_A, "text": "Legacy"},
        {"_id": "cross-note", "owner_account_id": ACCOUNT_B, "user_id": PROFILE_A, "text": "Cross"},
    ]

    def fake_get_profile(account_id, profile_id):
        profile_checks.append((account_id, profile_id))
        if (account_id, profile_id) in {
            (ACCOUNT_A, PROFILE_A),
            (ACCOUNT_B, PROFILE_B),
        }:
            return {"_id": profile_id, "owner_account_id": account_id}
        raise db.ProfileNotFoundError("Profile not found.")

    class FakeCollection:
        def find(self, filter_doc, **kwargs):
            calls.append((dict(filter_doc), dict(kwargs)))
            assert set(filter_doc) == {"owner_account_id", "user_id"}
            return iter(
                document
                for document in documents
                if document.get("owner_account_id") == filter_doc["owner_account_id"]
                and document.get("user_id") == filter_doc["user_id"]
            )

    monkeypatch.setattr(db, "get_profile", fake_get_profile)
    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    account_a_notes = db.list_notes(ACCOUNT_A, PROFILE_A, limit=2)
    account_b_notes = db.list_notes(ACCOUNT_B, PROFILE_B, limit=3)

    assert account_a_notes == [
        {"_id": "note-a", "owner_account_id": ACCOUNT_A, "user_id": PROFILE_A, "text": "A"},
    ]
    assert account_b_notes == [
        {"_id": "note-b", "owner_account_id": ACCOUNT_B, "user_id": PROFILE_B, "text": "B"},
    ]
    assert "legacy-note" not in [note["_id"] for note in account_a_notes]
    assert "cross-note" not in [note["_id"] for note in account_a_notes]
    assert profile_checks == [(ACCOUNT_A, PROFILE_A), (ACCOUNT_B, PROFILE_B)]
    assert calls == [
        ({"owner_account_id": ACCOUNT_A, "user_id": PROFILE_A}, {"limit": 2}),
        ({"owner_account_id": ACCOUNT_B, "user_id": PROFILE_B}, {"limit": 3}),
    ]


def test_list_notes_rejects_foreign_profile_before_note_query(monkeypatch):
    calls = []

    def fake_get_profile(account_id, profile_id):
        calls.append(("get_profile", account_id, profile_id))
        raise db.ProfileNotFoundError("Profile not found.")

    class FakeCollection:
        def find(self, filter_doc, **kwargs):
            raise AssertionError("notes must not be queried for foreign profile")

    monkeypatch.setattr(db, "get_profile", fake_get_profile)
    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.ProfileNotFoundError):
        db.list_notes(ACCOUNT_A, PROFILE_B, limit=10)
    with pytest.raises(db.ProfileNotFoundError):
        db.list_notes(ACCOUNT_B, PROFILE_A, limit=10)

    assert calls == [
        ("get_profile", ACCOUNT_A, PROFILE_B),
        ("get_profile", ACCOUNT_B, PROFILE_A),
    ]


def test_list_notes_rejects_invalid_limit(monkeypatch):
    with pytest.raises(db.InvalidNoteError):
        db.list_notes(ACCOUNT_A, PROFILE_A, limit=0)


@pytest.mark.parametrize("account_id", ["", "   ", None])
def test_list_notes_rejects_blank_account_id_before_database_call(monkeypatch, account_id):
    monkeypatch.setattr(
        db,
        "get_profile",
        lambda account_id, profile_id: (_ for _ in ()).throw(
            AssertionError("profile ownership must not be checked for invalid account_id")
        ),
    )

    class FakeCollection:
        def find(self, filter_doc, **kwargs):
            raise AssertionError("database must not be called for invalid account_id")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidProfileError):
        db.list_notes(account_id, PROFILE_A, limit=10)


@pytest.mark.parametrize("profile_id", ["", "   ", None])
def test_list_notes_rejects_blank_profile_id_before_database_call(monkeypatch, profile_id):
    monkeypatch.setattr(
        db,
        "get_profile",
        lambda account_id, profile_id: (_ for _ in ()).throw(
            AssertionError("profile ownership must not be checked for invalid profile_id")
        ),
    )

    class FakeCollection:
        def find(self, filter_doc, **kwargs):
            raise AssertionError("database must not be called for invalid profile_id")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidNoteError):
        db.list_notes(ACCOUNT_A, profile_id, limit=10)


def test_add_note_wraps_database_error_without_token(monkeypatch):
    secret = "AstraCS:super-secret-token"

    class FakeCollection:
        def insert_one(self, document):
            raise RuntimeError(f"insert failed with {secret}")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.DatabaseConnectionError) as exc_info:
        db.add_note("user-1", "Readable note text")

    message = str(exc_info.value)
    assert "Adding note failed" in message
    assert secret not in message
    assert "AstraCS:<redacted>" in message


def test_delete_note_uses_user_scoped_filter(monkeypatch):
    calls = []

    class FakeCollection:
        def find_one(self, filter_doc):
            calls.append(("find_one", filter_doc))
            return {"_id": "note-1", "user_id": "user-1"}

        def delete_one(self, filter_doc):
            calls.append(("delete_one", filter_doc))
            return SimpleNamespace(deleted_count=1)

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    assert db.delete_note("user-1", "note-1") is True
    assert calls == [
        ("find_one", {"_id": "note-1", "user_id": "user-1"}),
        ("delete_one", {"_id": "note-1", "user_id": "user-1"}),
    ]


def test_cross_user_delete_is_not_allowed(monkeypatch):
    calls = []

    class FakeCollection:
        def find_one(self, filter_doc):
            calls.append(("find_one", filter_doc))
            return None

        def delete_one(self, filter_doc):
            calls.append(("delete_one", filter_doc))
            raise AssertionError("delete_one must not be called without matching user_id")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.NoteNotFoundError):
        db.delete_note("user-2", "note-1")
    assert calls == [("find_one", {"_id": "note-1", "user_id": "user-2"})]


def test_update_note_refreshes_text_and_vectorize_with_user_filter(monkeypatch):
    calls = []

    class FakeCollection:
        def __init__(self):
            self.document = {"_id": "note-1", "user_id": "user-1", "text": "old"}

        def find_one(self, filter_doc):
            calls.append(("find_one", filter_doc))
            if filter_doc == {"_id": "note-1", "user_id": "user-1"}:
                return dict(self.document)
            return None

        def update_one(self, filter_doc, update_doc, **kwargs):
            calls.append(("update_one", filter_doc, update_doc, kwargs))
            self.document.update(update_doc["$set"])
            return SimpleNamespace(update_info={"n": 1})

    collection = FakeCollection()
    monkeypatch.setattr(db, "get_notes_collection", lambda: collection)

    updated = db.update_note("user-1", "note-1", " new text ")

    assert updated["text"] == "new text"
    assert updated["$vectorize"] == "new text"
    assert (
        "update_one",
        {"_id": "note-1", "user_id": "user-1"},
        {"$set": {"text": "new text", "$vectorize": "new text"}},
        {"upsert": False},
    ) in calls


def test_cross_user_update_is_not_allowed(monkeypatch):
    calls = []

    class FakeCollection:
        def find_one(self, filter_doc):
            calls.append(("find_one", filter_doc))
            return None

        def update_one(self, filter_doc, update_doc, **kwargs):
            calls.append(("update_one", filter_doc))
            raise AssertionError("update_one must not be called without matching user_id")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.NoteNotFoundError):
        db.update_note("user-2", "note-1", "new text")
    assert calls == [("find_one", {"_id": "note-1", "user_id": "user-2"})]


def test_update_note_rejects_blank_text_before_database_call(monkeypatch):
    class FakeCollection:
        def find_one(self, filter_doc):
            raise AssertionError("database must not be called for invalid text")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidNoteError):
        db.update_note("user-1", "note-1", " ")
