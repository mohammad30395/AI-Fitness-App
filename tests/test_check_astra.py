from scripts import check_astra


def test_check_astra_failure_output_redacts_token_and_endpoint(monkeypatch, capsys):
    endpoint = "https://example-region.apps.astra.datastax.com"
    token = "AstraCS:super-secret-token"

    values = {
        "ASTRA_DB_API_ENDPOINT": endpoint,
        "ASTRA_DB_APPLICATION_TOKEN": token,
        "ASTRA_DB_KEYSPACE": "",
    }

    monkeypatch.setattr(
        check_astra.config,
        "get_env_value",
        lambda name: values.get(name, ""),
    )

    class FakeDatabase:
        def list_collection_names(self):
            raise ValueError(f"connection failed for {endpoint} with {token}")

    class FakeDataAPIClient:
        def __init__(self, application_token):
            assert application_token == token

        def get_database(self, api_endpoint, **kwargs):
            assert api_endpoint == endpoint
            assert kwargs == {}
            return FakeDatabase()

    monkeypatch.setattr(check_astra, "DataAPIClient", FakeDataAPIClient)

    result = check_astra.run_smoke_test()
    output = capsys.readouterr().out

    assert result == 1
    assert endpoint not in output
    assert token not in output
    assert "[redacted]" in output
