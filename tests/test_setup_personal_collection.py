from scripts import setup_personal_collection as setup_script


def _patch_config(monkeypatch, collection_name="personal_data"):
    values = {
        "ASTRA_DB_API_ENDPOINT": "https://example-region.apps.astra.datastax.com",
        "ASTRA_DB_APPLICATION_TOKEN": "AstraCS:super-secret-token",
        "ASTRA_DB_KEYSPACE": "",
        "ASTRA_PERSONAL_COLLECTION": collection_name,
    }
    monkeypatch.setattr(
        setup_script.config,
        "get_env_value",
        lambda name: values.get(name, ""),
    )
    return values


def test_reuses_existing_collection_without_creating_or_deleting(monkeypatch):
    _patch_config(monkeypatch)
    calls = []

    class FakeDatabase:
        def list_collection_names(self):
            calls.append(("list_collection_names",))
            return ["personal_data"]

        def list_collections(self):
            calls.append(("list_collections",))
            return [{"name": "personal_data"}]

        def create_collection(self, name):
            calls.append(("create_collection", name))
            raise AssertionError("create_collection must not be called")

        def drop_collection(self, name):
            calls.append(("drop_collection", name))
            raise AssertionError("drop_collection must never be called")

    class FakeDataAPIClient:
        def __init__(self, token):
            calls.append(("client", token))

        def get_database(self, endpoint, **kwargs):
            calls.append(("get_database", endpoint, kwargs))
            return FakeDatabase()

    monkeypatch.setattr(setup_script, "DataAPIClient", FakeDataAPIClient)

    result = setup_script.setup_personal_collection()

    assert result.reused
    assert result.collection_name == "personal_data"
    assert ("list_collections",) in calls
    assert not any(call[0] in {"create_collection", "drop_collection"} for call in calls)


def test_creates_missing_collection_once_without_schema(monkeypatch):
    _patch_config(monkeypatch)
    calls = []

    class FakeDatabase:
        def __init__(self):
            self.names = []

        def list_collection_names(self):
            calls.append(("list_collection_names",))
            return list(self.names)

        def list_collections(self):
            calls.append(("list_collections",))
            return []

        def create_collection(self, name):
            calls.append(("create_collection", name))
            self.names.append(name)

        def drop_collection(self, name):
            calls.append(("drop_collection", name))
            raise AssertionError("drop_collection must never be called")

    database = FakeDatabase()

    class FakeDataAPIClient:
        def __init__(self, token):
            calls.append(("client", token))

        def get_database(self, endpoint, **kwargs):
            calls.append(("get_database", endpoint, kwargs))
            return database

    monkeypatch.setattr(setup_script, "DataAPIClient", FakeDataAPIClient)

    result = setup_script.setup_personal_collection()

    assert result.created
    assert ("create_collection", "personal_data") in calls
    assert not any(call[0] == "drop_collection" for call in calls)


def test_failure_output_redacts_token_and_endpoint(monkeypatch, capsys):
    values = _patch_config(monkeypatch)

    class FakeDataAPIClient:
        def __init__(self, token):
            pass

        def get_database(self, endpoint, **kwargs):
            raise ValueError(
                f"cannot connect to {values['ASTRA_DB_API_ENDPOINT']} with "
                f"{values['ASTRA_DB_APPLICATION_TOKEN']}"
            )

    monkeypatch.setattr(setup_script, "DataAPIClient", FakeDataAPIClient)

    result = setup_script.main()
    output = capsys.readouterr().out

    assert result == 1
    assert values["ASTRA_DB_API_ENDPOINT"] not in output
    assert values["ASTRA_DB_APPLICATION_TOKEN"] not in output
    assert "[redacted]" in output
