from types import SimpleNamespace

import pytest

import db


ACCOUNT_A = "account-a"
ACCOUNT_B = "account-b"


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


def profile_document(profile_id, owner_account_id, **overrides):
    profile = valid_profile(_id=profile_id)
    if owner_account_id is not None:
        profile["owner_account_id"] = owner_account_id
    profile.update(overrides)
    return profile


class FakeOwnedProfilesCollection:
    def __init__(self, documents):
        self.documents = [dict(document) for document in documents]
        self.calls = []

    def find_one(self, filter_doc):
        self.calls.append(("find_one", dict(filter_doc)))
        assert set(filter_doc) == {"_id", "owner_account_id"}
        for document in self.documents:
            if (
                document["_id"] == filter_doc["_id"]
                and document.get("owner_account_id") == filter_doc["owner_account_id"]
            ):
                return dict(document)
        return None

    def update_one(self, filter_doc, update_doc, **kwargs):
        self.calls.append(("update_one", dict(filter_doc), dict(update_doc), dict(kwargs)))
        assert set(filter_doc) == {"_id", "owner_account_id"}
        for document in self.documents:
            if (
                document["_id"] == filter_doc["_id"]
                and document.get("owner_account_id") == filter_doc["owner_account_id"]
            ):
                document.update(update_doc["$set"])
                return SimpleNamespace(update_info={"n": 1})
        return SimpleNamespace(update_info={"n": 0})


def patch_config(monkeypatch, *, keyspace=""):
    values = {
        "ASTRA_DB_API_ENDPOINT": "https://example-region.apps.astra.datastax.com",
        "ASTRA_DB_APPLICATION_TOKEN": "AstraCS:super-secret-token",
        "ASTRA_DB_KEYSPACE": keyspace,
        "ASTRA_PERSONAL_COLLECTION": "personal_data",
        "ASTRA_ACCOUNTS_COLLECTION": "accounts",
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


@pytest.mark.parametrize(
    ("values", "missing_name"),
    [
        (
            {
                "ASTRA_DB_API_ENDPOINT": "",
                "ASTRA_DB_APPLICATION_TOKEN": "AstraCS:super-secret-token",
            },
            "ASTRA_DB_API_ENDPOINT",
        ),
        (
            {
                "ASTRA_DB_API_ENDPOINT": "https://example-region.apps.astra.datastax.com",
                "ASTRA_DB_APPLICATION_TOKEN": "",
            },
            "ASTRA_DB_APPLICATION_TOKEN",
        ),
    ],
)
def test_get_database_rejects_missing_required_configuration(monkeypatch, values, missing_name):
    monkeypatch.setattr(db.config, "get_env_value", lambda name: values.get(name, ""))

    class FakeClient:
        def __init__(self, token):
            raise AssertionError("DataAPIClient must not be created with missing config")

    monkeypatch.setattr(db, "DataAPIClient", FakeClient)

    with pytest.raises(db.ConfigurationError) as exc_info:
        db.get_database()

    assert missing_name in str(exc_info.value)


def test_get_database_rejects_non_https_astra_endpoint(monkeypatch):
    values = {
        "ASTRA_DB_API_ENDPOINT": "http://astra.example.test",
        "ASTRA_DB_APPLICATION_TOKEN": "AstraCS:super-secret-token",
    }
    monkeypatch.setattr(db.config, "get_env_value", lambda name: values.get(name, ""))

    class FakeClient:
        def __init__(self, token):
            raise AssertionError("DataAPIClient must not be created for insecure endpoint")

    monkeypatch.setattr(db, "DataAPIClient", FakeClient)

    with pytest.raises(db.ConfigurationError) as exc_info:
        db.get_database()

    assert "ASTRA_DB_API_ENDPOINT" in str(exc_info.value)
    assert "https" in str(exc_info.value)


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


def test_get_accounts_collection_uses_configured_collection(monkeypatch):
    values = patch_config(monkeypatch)
    calls = []

    class FakeDatabase:
        def get_collection(self, name):
            calls.append(name)
            return "collection"

    monkeypatch.setattr(db, "get_database", lambda: FakeDatabase())

    assert db.get_accounts_collection() == "collection"
    assert calls == [values["ASTRA_ACCOUNTS_COLLECTION"]]


def test_list_profiles_returns_only_profiles_owned_by_account(monkeypatch):
    documents = [
        profile_document("profile-a", ACCOUNT_A, name="Ada"),
        profile_document("profile-b", ACCOUNT_B, name="Grace"),
        profile_document("legacy-profile", None, name="Legacy"),
    ]
    filters = []

    class FakeCollection:
        def find(self, filter_doc):
            filters.append(dict(filter_doc))
            assert "owner_account_id" in filter_doc
            return iter(
                document
                for document in documents
                if document.get("owner_account_id") == filter_doc["owner_account_id"]
            )

    monkeypatch.setattr(db, "get_personal_collection", lambda: FakeCollection())

    account_a_profiles = db.list_profiles(ACCOUNT_A)
    account_b_profiles = db.list_profiles(ACCOUNT_B)

    assert [profile["_id"] for profile in account_a_profiles] == ["profile-a"]
    assert [profile["_id"] for profile in account_b_profiles] == ["profile-b"]
    assert "profile-b" not in [profile["_id"] for profile in account_a_profiles]
    assert "profile-a" not in [profile["_id"] for profile in account_b_profiles]
    assert "legacy-profile" not in [profile["_id"] for profile in account_a_profiles]
    assert filters == [
        {"owner_account_id": ACCOUNT_A},
        {"owner_account_id": ACCOUNT_B},
    ]


@pytest.mark.parametrize("account_id", ["", "   ", None])
def test_list_profiles_rejects_blank_or_invalid_account_id(monkeypatch, account_id):
    class FakeCollection:
        def find(self, filter_doc):
            raise AssertionError("database must not be called for invalid account_id")

    monkeypatch.setattr(db, "get_personal_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidProfileError):
        db.list_profiles(account_id)


def test_list_profiles_wraps_read_errors_without_secret(monkeypatch):
    secret = "AstraCS:super-secret-token"

    class FakeCollection:
        def find(self, filter_doc):
            raise RuntimeError(f"read failed with {secret}")

    monkeypatch.setattr(db, "get_personal_collection", lambda: FakeCollection())

    with pytest.raises(db.DatabaseConnectionError) as exc_info:
        db.list_profiles(ACCOUNT_A)

    message = str(exc_info.value)
    assert "Listing profiles failed" in message
    assert secret not in message
    assert "AstraCS:<redacted>" in message


def test_get_profile_returns_only_profile_owned_by_account(monkeypatch):
    documents = [
        profile_document("profile-a", ACCOUNT_A, name="Ada"),
        profile_document("profile-b", ACCOUNT_B, name="Grace"),
        profile_document("legacy-profile", None, name="Legacy"),
    ]
    filters = []

    class FakeCollection:
        def find_one(self, filter_doc):
            filters.append(dict(filter_doc))
            assert "owner_account_id" in filter_doc
            for document in documents:
                if (
                    document["_id"] == filter_doc["_id"]
                    and document.get("owner_account_id") == filter_doc["owner_account_id"]
                ):
                    return dict(document)
            return None

    monkeypatch.setattr(db, "get_personal_collection", lambda: FakeCollection())

    assert db.get_profile(ACCOUNT_A, "profile-a")["_id"] == "profile-a"
    assert filters[-1] == {"_id": "profile-a", "owner_account_id": ACCOUNT_A}

    with pytest.raises(db.ProfileNotFoundError):
        db.get_profile(ACCOUNT_B, "profile-a")
    with pytest.raises(db.ProfileNotFoundError):
        db.get_profile(ACCOUNT_A, "profile-b")
    with pytest.raises(db.ProfileNotFoundError):
        db.get_profile(ACCOUNT_A, "legacy-profile")

    with pytest.raises(db.ProfileNotFoundError) as missing_profile:
        db.get_profile(ACCOUNT_A, "missing")
    with pytest.raises(db.ProfileNotFoundError) as foreign_profile:
        db.get_profile(ACCOUNT_B, "profile-a")

    assert type(missing_profile.value) is type(foreign_profile.value)
    assert "Profile not found" in str(missing_profile.value)
    assert "Profile not found" in str(foreign_profile.value)


@pytest.mark.parametrize("account_id", ["", "   ", None])
def test_get_profile_rejects_blank_or_invalid_account_id(monkeypatch, account_id):
    class FakeCollection:
        def find_one(self, filter_doc):
            raise AssertionError("database must not be called for invalid account_id")

    monkeypatch.setattr(db, "get_personal_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidProfileError):
        db.get_profile(account_id, "profile-1")


def test_create_profile_assigns_trusted_owner_and_returns_inserted_id(monkeypatch):
    calls = []

    class FakeCollection:
        def insert_one(self, document):
            calls.append(document)
            return SimpleNamespace(inserted_id="generated-id")

    monkeypatch.setattr(db, "get_personal_collection", lambda: FakeCollection())

    inserted_id = db.create_profile(ACCOUNT_A, valid_profile(name="  Ada Lovelace  "))

    assert inserted_id == "generated-id"
    assert calls[0]["name"] == "Ada Lovelace"
    assert calls[0]["owner_account_id"] == ACCOUNT_A
    assert "_id" not in calls[0]


def test_create_profile_uses_supplied_account_id_for_each_account(monkeypatch):
    calls = []

    class FakeCollection:
        def insert_one(self, document):
            calls.append(document)
            return SimpleNamespace(inserted_id=f"profile-{len(calls)}")

    monkeypatch.setattr(db, "get_personal_collection", lambda: FakeCollection())

    db.create_profile(ACCOUNT_A, valid_profile(name="Account A Profile"))
    db.create_profile(ACCOUNT_B, valid_profile(name="Account B Profile"))

    assert calls[0]["owner_account_id"] == ACCOUNT_A
    assert calls[1]["owner_account_id"] == ACCOUNT_B
    assert calls[0]["owner_account_id"] != calls[1]["owner_account_id"]


@pytest.mark.parametrize("account_id", ["", "   ", None])
def test_create_profile_rejects_blank_or_invalid_account_id(monkeypatch, account_id):
    class FakeCollection:
        def insert_one(self, document):
            raise AssertionError("insert_one must not be called for invalid account_id")

    monkeypatch.setattr(db, "get_personal_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidProfileError):
        db.create_profile(account_id, valid_profile())


def test_create_profile_rejects_forged_owner_account_id(monkeypatch):
    class FakeCollection:
        def insert_one(self, document):
            raise AssertionError("insert_one must not be called for forged owner")

    monkeypatch.setattr(db, "get_personal_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidProfileError):
        db.create_profile(ACCOUNT_A, valid_profile(owner_account_id=ACCOUNT_B))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("age", 0),
        ("age", 2.5),
        ("weight", -1),
        ("height", 0),
        ("gender", ""),
        ("gender", "   "),
        ("gender", 123),
        ("activity_level", ""),
        ("activity_level", "   "),
        ("activity_level", None),
        ("goals", ["valid", 123]),
        ("goals", ["valid", "   "]),
        ("nutrition", {"calories": -1}),
    ],
)
def test_create_profile_rejects_invalid_profile_input(monkeypatch, field, value):
    class FakeCollection:
        def insert_one(self, document):
            raise AssertionError("insert_one must not be called for invalid input")

    monkeypatch.setattr(db, "get_personal_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidProfileError):
        db.create_profile(ACCOUNT_A, valid_profile(**{field: value}))


def test_create_profile_rejects_application_supplied_id(monkeypatch):
    with pytest.raises(db.InvalidProfileError):
        db.create_profile(ACCOUNT_A, valid_profile(_id="client-generated-id"))


@pytest.mark.parametrize("account_id", ["", "   ", None])
def test_update_rejects_blank_or_invalid_account_id(monkeypatch, account_id):
    class FakeCollection:
        def find_one(self, filter_doc):
            raise AssertionError("database must not be called for invalid account_id")

        def update_one(self, filter_doc, update_doc, **kwargs):
            raise AssertionError("database must not be called for invalid account_id")

    monkeypatch.setattr(db, "get_personal_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidProfileError):
        db.update_personal_information(account_id, "profile-a", {"name": "Ada"})


def test_update_rejects_id_owner_and_empty_updates_before_calling_database(monkeypatch):
    class FakeCollection:
        def find_one(self, filter_doc):
            raise AssertionError("database must not be called for invalid updates")

        def update_one(self, filter_doc, update_doc, **kwargs):
            raise AssertionError("database must not be called for invalid updates")

    monkeypatch.setattr(db, "get_personal_collection", lambda: FakeCollection())

    with pytest.raises(db.InvalidProfileError):
        db.update_personal_information(ACCOUNT_A, "profile-a", {"_id": "new-id"})
    with pytest.raises(db.InvalidProfileError):
        db.update_personal_information(ACCOUNT_A, "profile-a", {"owner_account_id": ACCOUNT_B})
    with pytest.raises(db.InvalidProfileError):
        db.update_personal_information(ACCOUNT_A, "profile-a", {})


def test_account_a_and_b_can_update_their_own_profiles(monkeypatch):
    collection = FakeOwnedProfilesCollection(
        [
            profile_document("profile-a", ACCOUNT_A, name="Ada"),
            profile_document("profile-b", ACCOUNT_B, name="Grace"),
        ]
    )
    monkeypatch.setattr(db, "get_personal_collection", lambda: collection)

    updated_a = db.update_personal_information(ACCOUNT_A, "profile-a", {"name": "Ada Updated"})
    updated_b = db.update_personal_information(ACCOUNT_B, "profile-b", {"name": "Grace Updated"})

    assert updated_a["name"] == "Ada Updated"
    assert updated_b["name"] == "Grace Updated"
    assert (
        "update_one",
        {"_id": "profile-a", "owner_account_id": ACCOUNT_A},
        {"$set": {"name": "Ada Updated"}},
        {"upsert": False},
    ) in collection.calls
    assert (
        "update_one",
        {"_id": "profile-b", "owner_account_id": ACCOUNT_B},
        {"$set": {"name": "Grace Updated"}},
        {"upsert": False},
    ) in collection.calls


def test_update_foreign_and_legacy_profiles_are_not_modified(monkeypatch):
    collection = FakeOwnedProfilesCollection(
        [
            profile_document("profile-a", ACCOUNT_A, name="Ada"),
            profile_document("profile-b", ACCOUNT_B, name="Grace"),
            profile_document("legacy-profile", None, name="Legacy"),
        ]
    )
    monkeypatch.setattr(db, "get_personal_collection", lambda: collection)

    with pytest.raises(db.ProfileNotFoundError):
        db.update_personal_information(ACCOUNT_B, "profile-a", {"name": "Compromised"})
    with pytest.raises(db.ProfileNotFoundError):
        db.update_personal_information(ACCOUNT_A, "profile-b", {"name": "Compromised"})
    with pytest.raises(db.ProfileNotFoundError):
        db.update_personal_information(ACCOUNT_A, "legacy-profile", {"name": "Claimed"})

    assert collection.documents[0]["name"] == "Ada"
    assert collection.documents[1]["name"] == "Grace"
    assert collection.documents[2]["name"] == "Legacy"
    assert not any(call[0] == "update_one" for call in collection.calls)


def test_update_existing_profile_sets_allowed_fields_and_returns_updated_doc(monkeypatch):
    collection = FakeOwnedProfilesCollection(
        [profile_document("profile-a", ACCOUNT_A, name="Ada", age=31)]
    )
    monkeypatch.setattr(db, "get_personal_collection", lambda: collection)

    updated = db.update_personal_information(
        ACCOUNT_A,
        "profile-a",
        {"weight": 65, "goals": ["strength"]},
    )

    assert updated["weight"] == 65
    assert updated["goals"] == ["strength"]
    assert (
        "update_one",
        {"_id": "profile-a", "owner_account_id": ACCOUNT_A},
        {"$set": {"weight": 65, "goals": ["strength"]}},
        {"upsert": False},
    ) in collection.calls


def test_update_nutrition_uses_same_ownership_boundary(monkeypatch):
    collection = FakeOwnedProfilesCollection(
        [
            profile_document("profile-a", ACCOUNT_A, name="Ada"),
            profile_document("profile-b", ACCOUNT_B, name="Grace"),
        ]
    )
    monkeypatch.setattr(db, "get_personal_collection", lambda: collection)

    nutrition = {"calories": 2200, "protein": 150, "fat": 80, "carbs": 230}
    updated = db.update_personal_information(ACCOUNT_A, "profile-a", {"nutrition": nutrition})

    assert updated["nutrition"] == nutrition
    with pytest.raises(db.ProfileNotFoundError):
        db.update_personal_information(
            ACCOUNT_B,
            "profile-a",
            {"nutrition": {"calories": 1800}},
        )
    assert collection.documents[0]["nutrition"] == nutrition


def test_update_missing_profile_raises_not_found_without_upsert(monkeypatch):
    collection = FakeOwnedProfilesCollection(
        [profile_document("profile-a", ACCOUNT_A, name="Ada")]
    )
    monkeypatch.setattr(db, "get_personal_collection", lambda: collection)

    with pytest.raises(db.ProfileNotFoundError) as missing_profile:
        db.update_personal_information(ACCOUNT_A, "missing", {"name": "Missing"})
    with pytest.raises(db.ProfileNotFoundError) as foreign_profile:
        db.update_personal_information(ACCOUNT_B, "profile-a", {"name": "Foreign"})

    assert type(missing_profile.value) is type(foreign_profile.value)
    assert str(missing_profile.value) == str(foreign_profile.value)
    assert not any(call[0] == "update_one" for call in collection.calls)


def test_update_personal_information_requires_account_id_argument():
    with pytest.raises(TypeError):
        db.update_personal_information("profile-a", {"name": "Ada"})
