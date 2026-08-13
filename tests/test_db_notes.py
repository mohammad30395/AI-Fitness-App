from types import SimpleNamespace

import pytest

import db


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


def test_list_notes_filters_by_user_id_and_limit(monkeypatch):
    calls = []

    class FakeCollection:
        def find(self, filter_doc, **kwargs):
            calls.append((filter_doc, kwargs))
            return iter(
                [
                    {"_id": "note-1", "user_id": "user-1", "text": "A"},
                    {"_id": "note-2", "user_id": "user-1", "text": "B"},
                ]
            )

    monkeypatch.setattr(db, "get_notes_collection", lambda: FakeCollection())

    notes = db.list_notes("user-1", limit=2)

    assert notes == [
        {"_id": "note-1", "user_id": "user-1", "text": "A"},
        {"_id": "note-2", "user_id": "user-1", "text": "B"},
    ]
    assert calls == [({"user_id": "user-1"}, {"limit": 2})]


def test_list_notes_rejects_invalid_limit(monkeypatch):
    with pytest.raises(db.InvalidNoteError):
        db.list_notes("user-1", limit=0)


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
