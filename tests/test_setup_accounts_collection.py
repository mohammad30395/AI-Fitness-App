from scripts import setup_accounts_collection as setup_script


def _patch_config(monkeypatch, collection_name="accounts"):
    values = {
        "ASTRA_DB_API_ENDPOINT": "https://example-region.apps.astra.datastax.com",
        "ASTRA_DB_APPLICATION_TOKEN": "AstraCS:super-secret-token",
        "ASTRA_DB_KEYSPACE": "",
        "ASTRA_ACCOUNTS_COLLECTION": collection_name,
    }
    monkeypatch.setattr(setup_script.config, "get_env_value", lambda name: values.get(name, ""))
    return values


def test_uses_configured_collection_name(monkeypatch):
    _patch_config(monkeypatch, collection_name="custom_accounts")
    calls = []

    class FakeDatabase:
        names = []

        def list_collection_names(self):
            return list(self.names)

        def create_collection(self, name, *args, **kwargs):
            calls.append(("create_collection", name, args, kwargs))
            self.names.append(name)

    fake_database = FakeDatabase()

    class FakeDataAPIClient:
        def __init__(self, token):
            calls.append(("client", token))

        def get_database(self, endpoint, **kwargs):
            calls.append(("get_database", endpoint, kwargs))
            return fake_database

    monkeypatch.setattr(setup_script, "DataAPIClient", FakeDataAPIClient)

    result = setup_script.setup_accounts_collection()

    assert result.created
    assert result.collection_name == "custom_accounts"
    assert ("create_collection", "custom_accounts", (), {}) in calls


def test_creates_missing_collection_without_documents(monkeypatch):
    _patch_config(monkeypatch)
    calls = []

    class FakeDatabase:
        def __init__(self):
            self.names = []

        def list_collection_names(self):
            calls.append(("list_collection_names",))
            return list(self.names)

        def create_collection(self, name, *args, **kwargs):
            calls.append(("create_collection", name, args, kwargs))
            self.names.append(name)

        def get_collection(self, name):
            calls.append(("get_collection", name))
            raise AssertionError("setup must not open or insert into account collection")

        def insert_one(self, document):
            calls.append(("insert_one", document))
            raise AssertionError("setup must not insert account documents")

    fake_database = FakeDatabase()

    class FakeDataAPIClient:
        def __init__(self, token):
            pass

        def get_database(self, endpoint, **kwargs):
            return fake_database

    monkeypatch.setattr(setup_script, "DataAPIClient", FakeDataAPIClient)

    result = setup_script.setup_accounts_collection()

    assert result.created
    assert result.collection_name == "accounts"
    assert calls.count(("create_collection", "accounts", (), {})) == 1
    assert not any(call[0] in {"get_collection", "insert_one"} for call in calls)


def test_reuses_existing_collection_without_creating_or_deleting(monkeypatch):
    _patch_config(monkeypatch)
    calls = []

    class FakeDatabase:
        def list_collection_names(self):
            calls.append(("list_collection_names",))
            return ["accounts"]

        def list_collections(self):
            calls.append(("list_collections",))
            return [{"name": "accounts"}]

        def create_collection(self, name, *args, **kwargs):
            calls.append(("create_collection", name))
            raise AssertionError("existing accounts collection must not be recreated")

        def drop_collection(self, name):
            calls.append(("drop_collection", name))
            raise AssertionError("accounts collection must never be dropped")

    fake_database = FakeDatabase()

    class FakeDataAPIClient:
        def __init__(self, token):
            pass

        def get_database(self, endpoint, **kwargs):
            return fake_database

    monkeypatch.setattr(setup_script, "DataAPIClient", FakeDataAPIClient)

    result = setup_script.setup_accounts_collection()

    assert result.reused
    assert result.collection_name == "accounts"
    assert ("list_collections",) in calls
    assert not any(call[0] in {"create_collection", "drop_collection"} for call in calls)


def test_second_run_reuses_collection_created_by_first_run(monkeypatch):
    _patch_config(monkeypatch)
    calls = []

    class FakeDatabase:
        def __init__(self):
            self.names = []

        def list_collection_names(self):
            return list(self.names)

        def list_collections(self):
            calls.append(("list_collections",))
            return [{"name": name} for name in self.names]

        def create_collection(self, name, *args, **kwargs):
            calls.append(("create_collection", name))
            self.names.append(name)

    fake_database = FakeDatabase()

    class FakeDataAPIClient:
        def __init__(self, token):
            pass

        def get_database(self, endpoint, **kwargs):
            return fake_database

    monkeypatch.setattr(setup_script, "DataAPIClient", FakeDataAPIClient)

    first = setup_script.setup_accounts_collection()
    second = setup_script.setup_accounts_collection()

    assert first.created
    assert second.reused
    assert calls.count(("create_collection", "accounts")) == 1
    assert ("list_collections",) in calls


def test_blank_collection_name_uses_default_accounts(monkeypatch):
    _patch_config(monkeypatch, collection_name="")
    created = []

    class FakeDatabase:
        def __init__(self):
            self.names = []

        def list_collection_names(self):
            return list(self.names)

        def create_collection(self, name, *args, **kwargs):
            created.append(name)
            self.names.append(name)

    fake_database = FakeDatabase()

    class FakeDataAPIClient:
        def __init__(self, token):
            pass

        def get_database(self, endpoint, **kwargs):
            return fake_database

    monkeypatch.setattr(setup_script, "DataAPIClient", FakeDataAPIClient)

    result = setup_script.setup_accounts_collection()

    assert result.created
    assert result.collection_name == "accounts"
    assert created == ["accounts"]
