from scripts import setup_notes_collection as setup_script


def _patch_config(monkeypatch, collection_name="notes"):
    values = {
        "ASTRA_DB_API_ENDPOINT": "https://example-region.apps.astra.datastax.com",
        "ASTRA_DB_APPLICATION_TOKEN": "AstraCS:super-secret-token",
        "ASTRA_DB_KEYSPACE": "",
        "ASTRA_NOTES_COLLECTION": collection_name,
    }
    monkeypatch.setattr(
        setup_script.config,
        "get_env_value",
        lambda name: values.get(name, ""),
    )
    return values


def _provider_model(provider="nvidia", model="nvidia/nv-embedqa-e5-v5", dimension=1024):
    return setup_script.ProviderModel(provider=provider, model=model, vector_dimension=dimension)


class FakeProvider:
    def __init__(self, models):
        self.models = models


class FakeProvidersResult:
    def __init__(self, providers):
        self.embedding_providers = providers


class FakeAdmin:
    def __init__(self, models):
        self.models = models

    def find_embedding_providers(self):
        return FakeProvidersResult(
            {
                provider_model.provider: FakeProvider(
                    [
                        type(
                            "Model",
                            (),
                            {
                                "name": provider_model.model,
                                "vector_dimension": provider_model.vector_dimension,
                            },
                        )()
                    ]
                )
                for provider_model in self.models
            }
        )


def test_creates_notes_when_supported_and_missing(monkeypatch):
    _patch_config(monkeypatch)
    calls = []

    class FakeDatabase:
        def get_database_admin(self):
            calls.append(("get_database_admin",))
            return FakeAdmin([_provider_model()])

        def list_collection_names(self):
            calls.append(("list_collection_names",))
            return []

        def list_collections(self):
            calls.append(("list_collections",))
            return []

        def create_collection(self, name, *, definition):
            calls.append(("create_collection", name, definition.as_dict()))

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

    result = setup_script.setup_notes_collection()

    assert result.created
    create_call = next(call for call in calls if call[0] == "create_collection")
    assert create_call[1] == "notes"
    assert create_call[2]["vector"]["service"] == {
        "provider": "nvidia",
        "modelName": "nvidia/nv-embedqa-e5-v5",
    }
    assert create_call[2]["vector"]["metric"] == "cosine"
    assert "dimension" not in create_call[2]["vector"]
    assert not any(call[0] == "drop_collection" for call in calls)


def test_reuses_existing_compatible_vectorize_collection(monkeypatch):
    _patch_config(monkeypatch)
    calls = []

    class FakeDescriptor:
        name = "notes"

        def as_dict(self):
            return {
                "name": "notes",
                "options": {
                    "vector": {
                        "service": {
                            "provider": "nvidia",
                            "modelName": "nvidia/nv-embedqa-e5-v5",
                        }
                    }
                },
            }

    class FakeDatabase:
        def get_database_admin(self):
            return FakeAdmin([_provider_model()])

        def list_collection_names(self):
            calls.append(("list_collection_names",))
            return ["notes"]

        def list_collections(self):
            calls.append(("list_collections",))
            return [FakeDescriptor()]

        def create_collection(self, name, *, definition):
            calls.append(("create_collection", name))
            raise AssertionError("create_collection must not be called")

        def drop_collection(self, name):
            calls.append(("drop_collection", name))
            raise AssertionError("drop_collection must never be called")

    class FakeDataAPIClient:
        def __init__(self, token):
            pass

        def get_database(self, endpoint, **kwargs):
            return FakeDatabase()

    monkeypatch.setattr(setup_script, "DataAPIClient", FakeDataAPIClient)

    result = setup_script.setup_notes_collection()

    assert result.reused
    assert ("list_collections",) in calls
    assert not any(call[0] in {"create_collection", "drop_collection"} for call in calls)


def test_stops_before_create_when_target_model_unavailable(monkeypatch):
    _patch_config(monkeypatch)
    calls = []

    class FakeDatabase:
        def get_database_admin(self):
            return FakeAdmin([_provider_model(provider="cohere", model="embed-english-v3.0")])

        def list_collection_names(self):
            calls.append(("list_collection_names",))
            return []

        def list_collections(self):
            calls.append(("list_collections",))
            return []

        def create_collection(self, name, *, definition):
            calls.append(("create_collection", name))
            raise AssertionError("create_collection must not be called")

    class FakeDataAPIClient:
        def __init__(self, token):
            pass

        def get_database(self, endpoint, **kwargs):
            return FakeDatabase()

    monkeypatch.setattr(setup_script, "DataAPIClient", FakeDataAPIClient)

    try:
        setup_script.setup_notes_collection()
    except setup_script.SetupStopped as exc:
        assert "cohere" in str(exc)
        assert "embed-english-v3.0" in str(exc)
    else:
        raise AssertionError("SetupStopped was not raised")

    assert not any(call[0] == "create_collection" for call in calls)


def test_stops_on_existing_incompatible_collection(monkeypatch):
    _patch_config(monkeypatch)
    calls = []

    class FakeDescriptor:
        name = "notes"

        def as_dict(self):
            return {
                "name": "notes",
                "options": {
                    "vector": {
                        "service": {
                            "provider": "openai",
                            "modelName": "text-embedding-3-small",
                        }
                    }
                },
            }

    class FakeDatabase:
        def get_database_admin(self):
            return FakeAdmin([_provider_model()])

        def list_collection_names(self):
            return ["notes"]

        def list_collections(self):
            return [FakeDescriptor()]

        def create_collection(self, name, *, definition):
            calls.append(("create_collection", name))
            raise AssertionError("create_collection must not be called")

    class FakeDataAPIClient:
        def __init__(self, token):
            pass

        def get_database(self, endpoint, **kwargs):
            return FakeDatabase()

    monkeypatch.setattr(setup_script, "DataAPIClient", FakeDataAPIClient)

    try:
        setup_script.setup_notes_collection()
    except setup_script.SetupStopped as exc:
        assert "migration or a new collection" in str(exc)
    else:
        raise AssertionError("SetupStopped was not raised")

    assert not any(call[0] == "create_collection" for call in calls)
