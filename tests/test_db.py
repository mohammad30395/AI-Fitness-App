from types import SimpleNamespace

import pytest

import db


def valid_profile(**overrides):
    profile = {
        "name": "Ada Lovelace",
        "age": 31,
        "weight": 64.5,
        "height": 170,
        "gender": "female",
        "activity_level": "moderate",
        "goals": ["strength", "mobility"],
        "nutrition": {
            "calories": 2100,
            "protein": 140,
            "fat": 70,
            "carbs": 220,
        },
    }
    profile.update(overrides)
    return profile


def patch_config(monkeypatch, *, keyspace=""):
    values = {
        "ASTRA_DB_API_ENDPOINT": "https://example-region.apps.astra.datastax.com",
        "ASTRA_DB_APPLICATION_TOKEN": "AstraCS:super-secret-token",
        "ASTRA_DB_KEYSPACE": keyspace,
        "ASTRA_PERSONAL_COLLECTION": "personal_data",
    }
    monkeypatch.setattr(db.config, "get_env_value", lambda name: values.get(name, ""))
    return values


def test_get_database_uses_config_and_optional_keyspace(monkeypatch):
    values = patch_config(monkeypatch, keyspace="fitness")
    calls = []

    class FakeClient:
        def __init__(self, token):
            calls.append(("client", token))

        def get_database(self, endpoint, **kwargs):
            calls.append(("get_database", endpoint, kwargs))
            return "database"

    monkeypatch.setattr(db, "DataAPIClient", FakeClient)

    assert db.get_database() == "database"
    assert calls == [
        ("client", values["ASTRA_DB_APPLICATION_TOKEN"]),
        ("get_database", values["ASTRA_DB_API_ENDPOINT"], {"keyspace": "fitness"}),
    ]


def test_get_database_wraps_connection_error_without_token(monkeypatch):
    values = patch_config(monkeypatch)

    class FakeClient:
        def __init__(self, token):
            assert token == values["ASTRA_DB_APPLICATION_TOKEN"]

        def get_database(self, endpoint, **kwargs):
            raise RuntimeError(f"auth failed for {values['ASTRA_DB_APPLICATION_TOKEN']}")

    monkeypatch.setattr(db, "DataAPIClient", FakeClient)

    with pytest.raises(db.DatabaseConnectionError) as exc_info:
        db.get_database()

    message = str(exc_info.value)
    assert "Connecting to Astra DB failed" in message
    assert values["ASTRA_DB_APPLICATION_TOKEN"] not in message
    assert "<redacted:ASTRA_DB_APPLICATION_TOKEN>" in message


def test_get_personal_collection_uses_configured_collection(monkeypatch):
    patch_config(monkeypatch)
    calls = []

    class FakeDatabase:
        def get_collection(self, name):
            calls.append(name)
            return "collection"

    monkeypatch.setattr(db, "get_database", lambda: FakeDatabase())

    assert db.get_personal_collection() == "collection"
    assert calls == ["personal_data"]


def test_list_profiles_returns_plain_dicts(monkeypatch):
    class FakeCollection:
        def find(self, filter_doc):
            assert filter_doc == {}
            return iter(
                [
                    {"_id": "one", "name": "Ada"},
                    {"_id": "two", "name": "Grace"},
                ]
            )

    monkeypatch.setattr(db, "get_personal_collection", lambda: FakeCollection())

    assert db.list_profiles() == [
        {"_id": "one", "name": "Ada"},
        {"_id": "two", "name": "Grace"},
    ]


def test_list_profiles_wraps_read_errors_without_secret(monkeypatch):
    secret = "AstraCS:super-secret-token"

    class FakeCollection:
        def find(self, filter_doc):
            raise RuntimeError(f"read failed with {secret}")

    monkeypatch.setattr(db, "get_personal_collection", lambda: FakeCollection())

    with pytest.raises(db.DatabaseConnectionError) as exc_info:
        db.list_profiles()

    message = str(exc_info.value)
    assert "Listing profiles failed" in message
    assert secret not in message
    assert "AstraCS:<redacted>" in message


def test_get_profile_returns_document_or_raises_not_found(monkeypatch):
    class FakeCollection:
        def find_one(self, filter_doc):
            if filter_doc == {"_id": "profile-1"}:
                return {"_id": "profile-1", "name": "Ada"}
            return None

    monkeypatch.setattr(db, "get_personal_collection", lambda: FakeCollection())

    assert db.get_profile("profile-1") == {"_id": "profile-1", "name": "Ada"}
    with pytest.raises(db.ProfileNotFoundError):
        db.get_profile("missing")


def test_create_profile_validates_and_returns_inserted_id(monkeypatch):
    calls = []

    class FakeCollection:
        def insert_one(self, document):
            calls.append(document)
            return SimpleNamespace(inserted_id="generated-id")

    monkeypatch.setattr(db, "get_personal_collection", lambda: FakeCollection())

    inserted_id = db.create_profile(valid_profile(name="  Ada Lovelace  "))

    assert inserted_id == "generated-id"
    assert calls[0]["name"] == "Ada Lovelace"
    assert "_id" not in calls[0]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("age", 0),
        ("age", 2.5),
        ("weight", -1),
        ("height", 0),
        ("gender", 123),
        ("activity_level", None),
        ("goals", ["valid", 123]),
        ("nutrition", {"calories": -1}),
    ],
)
def test_create_profile_rejects_invalid_profile_input(monkeypatch, field, value):
    class FakeCollection:
        def insert_one(self, document):
            raise AssertionError("insert_one must not be called for invalid input")

    monkeypatch.setattr(db, "get_personal_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidProfileError):
        db.create_profile(valid_profile(**{field: value}))


def test_create_profile_rejects_application_supplied_id(monkeypatch):
    with pytest.raises(db.InvalidProfileError):
        db.create_profile(valid_profile(_id="client-generated-id"))


def test_update_rejects_id_and_empty_updates_before_calling_database(monkeypatch):
    class FakeCollection:
        def find_one(self, filter_doc):
            raise AssertionError("database must not be called for invalid updates")

        def update_one(self, filter_doc, update_doc, **kwargs):
            raise AssertionError("database must not be called for invalid updates")

    monkeypatch.setattr(db, "get_personal_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidProfileError):
        db.update_personal_information("profile-1", {"_id": "new-id"})
    with pytest.raises(db.InvalidProfileError):
        db.update_personal_information("profile-1", {})


def test_update_existing_profile_sets_allowed_fields_and_returns_updated_doc(monkeypatch):
    calls = []

    class FakeCollection:
        def __init__(self):
            self.document = {"_id": "profile-1", "name": "Ada", "age": 31}

        def find_one(self, filter_doc):
            calls.append(("find_one", filter_doc))
            if filter_doc == {"_id": "profile-1"}:
                return dict(self.document)
            return None

        def update_one(self, filter_doc, update_doc, **kwargs):
            calls.append(("update_one", filter_doc, update_doc, kwargs))
            self.document.update(update_doc["$set"])
            return SimpleNamespace(update_info={"n": 1})

    collection = FakeCollection()
    monkeypatch.setattr(db, "get_personal_collection", lambda: collection)

    updated = db.update_personal_information("profile-1", {"weight": 65, "goals": ["strength"]})

    assert updated["weight"] == 65
    assert updated["goals"] == ["strength"]
    assert (
        "update_one",
        {"_id": "profile-1"},
        {"$set": {"weight": 65, "goals": ["strength"]}},
        {"upsert": False},
    ) in calls


def test_update_missing_profile_raises_not_found_without_upsert(monkeypatch):
    class FakeCollection:
        def find_one(self, filter_doc):
            return None

        def update_one(self, filter_doc, update_doc, **kwargs):
            raise AssertionError("update_one must not be called for missing profile")

    monkeypatch.setattr(db, "get_personal_collection", lambda: FakeCollection())

    with pytest.raises(db.ProfileNotFoundError):
        db.update_personal_information("missing", {"name": "Ada"})
