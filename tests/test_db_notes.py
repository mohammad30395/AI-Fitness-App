from types import SimpleNamespace

import pytest

import db


ACCOUNT_A = "account-a"
ACCOUNT_B = "account-b"
PROFILE_A = "profile-a"
PROFILE_B = "profile-b"
NOTE_A = "note-a"
NOTE_B = "note-b"
LEGACY_NOTE = "legacy-note"


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


def patch_owned_profiles(monkeypatch):
    profile_checks = []

    def fake_get_profile(account_id, profile_id):
        profile_checks.append((account_id, profile_id))
        if (account_id, profile_id) in {
            (ACCOUNT_A, PROFILE_A),
            (ACCOUNT_B, PROFILE_B),
        }:
            return {"_id": profile_id, "owner_account_id": account_id}
        raise db.ProfileNotFoundError("Profile not found.")

    monkeypatch.setattr(db, "get_profile", fake_get_profile)
    return profile_checks


class FakeOwnedNotesCollection:
    def __init__(self):
        self.documents = [
            {
                "_id": NOTE_A,
                "owner_account_id": ACCOUNT_A,
                "user_id": PROFILE_A,
                "text": "A",
                "$vectorize": "A",
            },
            {
                "_id": NOTE_B,
                "owner_account_id": ACCOUNT_B,
                "user_id": PROFILE_B,
                "text": "B",
                "$vectorize": "B",
            },
            {
                "_id": LEGACY_NOTE,
                "user_id": PROFILE_A,
                "text": "Legacy",
                "$vectorize": "Legacy",
            },
        ]
        self.calls = []

    def find_one(self, filter_doc):
        self.calls.append(("find_one", dict(filter_doc)))
        assert set(filter_doc) == {"_id", "owner_account_id", "user_id"}
        for document in self.documents:
            if (
                document["_id"] == filter_doc["_id"]
                and document.get("owner_account_id") == filter_doc["owner_account_id"]
                and document.get("user_id") == filter_doc["user_id"]
            ):
                return dict(document)
        return None

    def delete_one(self, filter_doc):
        self.calls.append(("delete_one", dict(filter_doc)))
        assert set(filter_doc) == {"_id", "owner_account_id", "user_id"}
        self.documents = [
            document
            for document in self.documents
            if not (
                document["_id"] == filter_doc["_id"]
                and document.get("owner_account_id") == filter_doc["owner_account_id"]
                and document.get("user_id") == filter_doc["user_id"]
            )
        ]
        return SimpleNamespace(deleted_count=1)

    def update_one(self, filter_doc, update_doc, **kwargs):
        self.calls.append(("update_one", dict(filter_doc), dict(update_doc), dict(kwargs)))
        assert set(filter_doc) == {"_id", "owner_account_id", "user_id"}
        for document in self.documents:
            if (
                document["_id"] == filter_doc["_id"]
                and document.get("owner_account_id") == filter_doc["owner_account_id"]
                and document.get("user_id") == filter_doc["user_id"]
            ):
                document.update(update_doc["$set"])
                return SimpleNamespace(update_info={"n": 1})
        return SimpleNamespace(update_info={"n": 0})


def test_add_note_includes_owner_profile_text_and_vectorize(monkeypatch):
    profile_checks = patch_owned_profiles(monkeypatch)
    calls = []

    class FakeCollection:
        def insert_one(self, document):
            calls.append(document)
            return SimpleNamespace(inserted_id="note-1")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    inserted_id = db.add_note(ACCOUNT_A, PROFILE_A, "  Readable note text  ")

    assert inserted_id == "note-1"
    assert profile_checks == [(ACCOUNT_A, PROFILE_A)]
    assert calls == [
        {
            "owner_account_id": ACCOUNT_A,
            "user_id": PROFILE_A,
            "text": "Readable note text",
            "$vectorize": "Readable note text",
        }
    ]
    assert "$vector" not in calls[0]


def test_add_note_uses_supplied_account_and_profile_for_each_owner(monkeypatch):
    profile_checks = patch_owned_profiles(monkeypatch)
    calls = []

    class FakeCollection:
        def insert_one(self, document):
            calls.append(document)
            return SimpleNamespace(inserted_id=f"note-{len(calls)}")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    first = db.add_note(ACCOUNT_A, PROFILE_A, "A note")
    second = db.add_note(ACCOUNT_B, PROFILE_B, "B note")

    assert first == "note-1"
    assert second == "note-2"
    assert profile_checks == [(ACCOUNT_A, PROFILE_A), (ACCOUNT_B, PROFILE_B)]
    assert calls[0]["owner_account_id"] == ACCOUNT_A
    assert calls[0]["user_id"] == PROFILE_A
    assert calls[1]["owner_account_id"] == ACCOUNT_B
    assert calls[1]["user_id"] == PROFILE_B
    assert calls[0]["owner_account_id"] != calls[1]["owner_account_id"]
    assert calls[0]["user_id"] != calls[1]["user_id"]


def test_add_note_rejects_foreign_profile_before_insert(monkeypatch):
    profile_checks = patch_owned_profiles(monkeypatch)

    class FakeCollection:
        def insert_one(self, document):
            raise AssertionError("insert_one must not be called for foreign profile")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.ProfileNotFoundError) as account_a_foreign:
        db.add_note(ACCOUNT_A, PROFILE_B, "A should not write to B")
    with pytest.raises(db.ProfileNotFoundError) as account_b_foreign:
        db.add_note(ACCOUNT_B, PROFILE_A, "B should not write to A")

    assert profile_checks == [(ACCOUNT_A, PROFILE_B), (ACCOUNT_B, PROFILE_A)]
    assert type(account_a_foreign.value) is type(account_b_foreign.value)
    assert str(account_a_foreign.value) == str(account_b_foreign.value)


def test_add_note_missing_and_foreign_profile_fail_indistinguishably(monkeypatch):
    patch_owned_profiles(monkeypatch)

    class FakeCollection:
        def insert_one(self, document):
            raise AssertionError("insert_one must not be called for unauthorized profile")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.ProfileNotFoundError) as missing_profile:
        db.add_note(ACCOUNT_A, "missing-profile", "Readable note text")
    with pytest.raises(db.ProfileNotFoundError) as foreign_profile:
        db.add_note(ACCOUNT_A, PROFILE_B, "Readable note text")

    assert type(missing_profile.value) is type(foreign_profile.value)
    assert str(missing_profile.value) == str(foreign_profile.value)


@pytest.mark.parametrize("blank_text", ["", "   ", None])
def test_add_note_rejects_blank_notes_before_database_call(monkeypatch, blank_text):
    monkeypatch.setattr(
        db,
        "get_profile",
        lambda account_id, profile_id: (_ for _ in ()).throw(
            AssertionError("profile ownership must not be checked for invalid text")
        ),
    )

    class FakeCollection:
        def insert_one(self, document):
            raise AssertionError("insert_one must not be called for invalid text")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidNoteError):
        db.add_note(ACCOUNT_A, PROFILE_A, blank_text)


@pytest.mark.parametrize("account_id", ["", "   ", None])
def test_add_note_rejects_blank_account_id_before_database_call(monkeypatch, account_id):
    monkeypatch.setattr(
        db,
        "get_profile",
        lambda account_id, profile_id: (_ for _ in ()).throw(
            AssertionError("profile ownership must not be checked for invalid account_id")
        ),
    )

    class FakeCollection:
        def insert_one(self, document):
            raise AssertionError("insert_one must not be called for invalid account_id")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidProfileError):
        db.add_note(account_id, PROFILE_A, "Readable note text")


@pytest.mark.parametrize("profile_id", ["", "   ", None])
def test_add_note_rejects_blank_profile_id_before_database_call(monkeypatch, profile_id):
    monkeypatch.setattr(
        db,
        "get_profile",
        lambda account_id, profile_id: (_ for _ in ()).throw(
            AssertionError("profile ownership must not be checked for invalid profile_id")
        ),
    )

    class FakeCollection:
        def insert_one(self, document):
            raise AssertionError("insert_one must not be called for invalid profile_id")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidNoteError):
        db.add_note(ACCOUNT_A, profile_id, "Readable note text")


def test_add_note_requires_account_id_argument():
    with pytest.raises(TypeError):
        db.add_note(PROFILE_A, "Readable note text")


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
    patch_owned_profiles(monkeypatch)
    secret = "AstraCS:super-secret-token"

    class FakeCollection:
        def insert_one(self, document):
            raise RuntimeError(f"insert failed with {secret}")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.DatabaseConnectionError) as exc_info:
        db.add_note(ACCOUNT_A, PROFILE_A, "Readable note text")

    message = str(exc_info.value)
    assert "Adding note failed" in message
    assert secret not in message
    assert "AstraCS:<redacted>" in message


def test_delete_note_uses_owner_profile_note_filter(monkeypatch):
    profile_checks = patch_owned_profiles(monkeypatch)
    collection = FakeOwnedNotesCollection()
    monkeypatch.setattr(db, "get_notes_collection", lambda: collection)

    assert db.delete_note(ACCOUNT_A, PROFILE_A, NOTE_A) is True
    assert db.delete_note(ACCOUNT_B, PROFILE_B, NOTE_B) is True
    assert profile_checks == [(ACCOUNT_A, PROFILE_A), (ACCOUNT_B, PROFILE_B)]
    assert (
        "delete_one",
        {"_id": NOTE_A, "owner_account_id": ACCOUNT_A, "user_id": PROFILE_A},
    ) in collection.calls
    assert (
        "delete_one",
        {"_id": NOTE_B, "owner_account_id": ACCOUNT_B, "user_id": PROFILE_B},
    ) in collection.calls
    assert NOTE_A not in [document["_id"] for document in collection.documents]
    assert NOTE_B not in [document["_id"] for document in collection.documents]


def test_delete_note_rejects_foreign_note_and_legacy_note(monkeypatch):
    patch_owned_profiles(monkeypatch)
    collection = FakeOwnedNotesCollection()
    monkeypatch.setattr(db, "get_notes_collection", lambda: collection)

    with pytest.raises(db.NoteNotFoundError):
        db.delete_note(ACCOUNT_A, PROFILE_A, NOTE_B)
    with pytest.raises(db.NoteNotFoundError):
        db.delete_note(ACCOUNT_B, PROFILE_B, NOTE_A)
    with pytest.raises(db.NoteNotFoundError):
        db.delete_note(ACCOUNT_A, PROFILE_A, LEGACY_NOTE)

    assert [document["_id"] for document in collection.documents] == [
        NOTE_A,
        NOTE_B,
        LEGACY_NOTE,
    ]
    assert not any(call[0] == "delete_one" for call in collection.calls)


def test_delete_note_rejects_foreign_profile_before_note_query(monkeypatch):
    profile_checks = patch_owned_profiles(monkeypatch)

    class FakeCollection:
        def find_one(self, filter_doc):
            raise AssertionError("notes must not be queried for foreign profile")

        def delete_one(self, filter_doc):
            raise AssertionError("delete_one must not be called for foreign profile")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.ProfileNotFoundError):
        db.delete_note(ACCOUNT_A, PROFILE_B, NOTE_B)

    assert profile_checks == [(ACCOUNT_A, PROFILE_B)]


def test_delete_missing_and_foreign_note_fail_indistinguishably(monkeypatch):
    patch_owned_profiles(monkeypatch)
    collection = FakeOwnedNotesCollection()
    monkeypatch.setattr(db, "get_notes_collection", lambda: collection)

    with pytest.raises(db.NoteNotFoundError) as missing_note:
        db.delete_note(ACCOUNT_A, PROFILE_A, "missing-note")
    with pytest.raises(db.NoteNotFoundError) as foreign_note:
        db.delete_note(ACCOUNT_A, PROFILE_A, NOTE_B)

    assert type(missing_note.value) is type(foreign_note.value)
    assert str(missing_note.value) == str(foreign_note.value)


@pytest.mark.parametrize("account_id", ["", "   ", None])
def test_delete_note_rejects_invalid_account_id_before_database_call(monkeypatch, account_id):
    monkeypatch.setattr(
        db,
        "get_profile",
        lambda account_id, profile_id: (_ for _ in ()).throw(
            AssertionError("profile ownership must not be checked for invalid account_id")
        ),
    )

    class FakeCollection:
        def find_one(self, filter_doc):
            raise AssertionError("database must not be called for invalid account_id")

        def delete_one(self, filter_doc):
            raise AssertionError("database must not be called for invalid account_id")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidProfileError):
        db.delete_note(account_id, PROFILE_A, NOTE_A)


@pytest.mark.parametrize("profile_id", ["", "   ", None])
def test_delete_note_rejects_invalid_profile_id_before_database_call(monkeypatch, profile_id):
    monkeypatch.setattr(
        db,
        "get_profile",
        lambda account_id, profile_id: (_ for _ in ()).throw(
            AssertionError("profile ownership must not be checked for invalid profile_id")
        ),
    )

    class FakeCollection:
        def find_one(self, filter_doc):
            raise AssertionError("database must not be called for invalid profile_id")

        def delete_one(self, filter_doc):
            raise AssertionError("database must not be called for invalid profile_id")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidNoteError):
        db.delete_note(ACCOUNT_A, profile_id, NOTE_A)


@pytest.mark.parametrize("note_id", ["", None])
def test_delete_note_rejects_invalid_note_id_before_database_call(monkeypatch, note_id):
    monkeypatch.setattr(
        db,
        "get_profile",
        lambda account_id, profile_id: (_ for _ in ()).throw(
            AssertionError("profile ownership must not be checked for invalid note_id")
        ),
    )

    class FakeCollection:
        def find_one(self, filter_doc):
            raise AssertionError("database must not be called for invalid note_id")

        def delete_one(self, filter_doc):
            raise AssertionError("database must not be called for invalid note_id")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidNoteError):
        db.delete_note(ACCOUNT_A, PROFILE_A, note_id)


def test_delete_note_requires_account_id_argument():
    with pytest.raises(TypeError):
        db.delete_note(PROFILE_A, NOTE_A)


def test_update_note_uses_owner_profile_note_filter_and_refreshes_vectorize(monkeypatch):
    profile_checks = patch_owned_profiles(monkeypatch)
    collection = FakeOwnedNotesCollection()
    monkeypatch.setattr(db, "get_notes_collection", lambda: collection)

    updated = db.update_note(ACCOUNT_A, PROFILE_A, NOTE_A, " new text ")

    assert updated["text"] == "new text"
    assert updated["$vectorize"] == "new text"
    assert "$vector" not in updated
    assert profile_checks == [(ACCOUNT_A, PROFILE_A)]
    assert (
        "update_one",
        {"_id": NOTE_A, "owner_account_id": ACCOUNT_A, "user_id": PROFILE_A},
        {"$set": {"text": "new text", "$vectorize": "new text"}},
        {"upsert": False},
    ) in collection.calls


def test_update_note_rejects_foreign_note_and_legacy_note(monkeypatch):
    patch_owned_profiles(monkeypatch)
    collection = FakeOwnedNotesCollection()
    monkeypatch.setattr(db, "get_notes_collection", lambda: collection)

    with pytest.raises(db.NoteNotFoundError):
        db.update_note(ACCOUNT_B, PROFILE_B, NOTE_A, "Compromised")
    with pytest.raises(db.NoteNotFoundError):
        db.update_note(ACCOUNT_A, PROFILE_A, NOTE_B, "Compromised")
    with pytest.raises(db.NoteNotFoundError):
        db.update_note(ACCOUNT_A, PROFILE_A, LEGACY_NOTE, "Claimed")

    assert collection.documents[0]["text"] == "A"
    assert collection.documents[1]["text"] == "B"
    assert collection.documents[2]["text"] == "Legacy"
    assert not any(call[0] == "update_one" for call in collection.calls)


def test_update_note_rejects_foreign_profile_before_note_query(monkeypatch):
    profile_checks = patch_owned_profiles(monkeypatch)

    class FakeCollection:
        def find_one(self, filter_doc):
            raise AssertionError("notes must not be queried for foreign profile")

        def update_one(self, filter_doc, update_doc, **kwargs):
            raise AssertionError("update_one must not be called for foreign profile")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.ProfileNotFoundError):
        db.update_note(ACCOUNT_A, PROFILE_B, NOTE_B, "new text")

    assert profile_checks == [(ACCOUNT_A, PROFILE_B)]


def test_update_missing_and_foreign_note_fail_indistinguishably(monkeypatch):
    patch_owned_profiles(monkeypatch)
    collection = FakeOwnedNotesCollection()
    monkeypatch.setattr(db, "get_notes_collection", lambda: collection)

    with pytest.raises(db.NoteNotFoundError) as missing_note:
        db.update_note(ACCOUNT_A, PROFILE_A, "missing-note", "new text")
    with pytest.raises(db.NoteNotFoundError) as foreign_note:
        db.update_note(ACCOUNT_A, PROFILE_A, NOTE_B, "new text")

    assert type(missing_note.value) is type(foreign_note.value)
    assert str(missing_note.value) == str(foreign_note.value)


@pytest.mark.parametrize("account_id", ["", "   ", None])
def test_update_note_rejects_invalid_account_id_before_database_call(monkeypatch, account_id):
    monkeypatch.setattr(
        db,
        "get_profile",
        lambda account_id, profile_id: (_ for _ in ()).throw(
            AssertionError("profile ownership must not be checked for invalid account_id")
        ),
    )

    class FakeCollection:
        def find_one(self, filter_doc):
            raise AssertionError("database must not be called for invalid account_id")

        def update_one(self, filter_doc, update_doc, **kwargs):
            raise AssertionError("database must not be called for invalid account_id")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidProfileError):
        db.update_note(account_id, PROFILE_A, NOTE_A, "new text")


@pytest.mark.parametrize("profile_id", ["", "   ", None])
def test_update_note_rejects_invalid_profile_id_before_database_call(monkeypatch, profile_id):
    monkeypatch.setattr(
        db,
        "get_profile",
        lambda account_id, profile_id: (_ for _ in ()).throw(
            AssertionError("profile ownership must not be checked for invalid profile_id")
        ),
    )

    class FakeCollection:
        def find_one(self, filter_doc):
            raise AssertionError("database must not be called for invalid profile_id")

        def update_one(self, filter_doc, update_doc, **kwargs):
            raise AssertionError("database must not be called for invalid profile_id")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidNoteError):
        db.update_note(ACCOUNT_A, profile_id, NOTE_A, "new text")


@pytest.mark.parametrize("note_id", ["", None])
def test_update_note_rejects_invalid_note_id_before_database_call(monkeypatch, note_id):
    monkeypatch.setattr(
        db,
        "get_profile",
        lambda account_id, profile_id: (_ for _ in ()).throw(
            AssertionError("profile ownership must not be checked for invalid note_id")
        ),
    )

    class FakeCollection:
        def find_one(self, filter_doc):
            raise AssertionError("database must not be called for invalid note_id")

        def update_one(self, filter_doc, update_doc, **kwargs):
            raise AssertionError("database must not be called for invalid note_id")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidNoteError):
        db.update_note(ACCOUNT_A, PROFILE_A, note_id, "new text")


def test_update_note_rejects_blank_text_before_database_call(monkeypatch):
    monkeypatch.setattr(
        db,
        "get_profile",
        lambda account_id, profile_id: (_ for _ in ()).throw(
            AssertionError("profile ownership must not be checked for invalid text")
        ),
    )

    class FakeCollection:
        def find_one(self, filter_doc):
            raise AssertionError("database must not be called for invalid text")

        def update_one(self, filter_doc, update_doc, **kwargs):
            raise AssertionError("database must not be called for invalid text")

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidNoteError):
        db.update_note(ACCOUNT_A, PROFILE_A, NOTE_A, " ")


def test_update_note_requires_account_id_argument():
    with pytest.raises(TypeError):
        db.update_note(PROFILE_A, NOTE_A, "new text")
