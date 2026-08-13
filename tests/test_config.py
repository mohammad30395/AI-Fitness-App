import config


def clear_config_env(monkeypatch):
    for name in config.ALL_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_secrets_are_not_included_in_validation_messages(monkeypatch):
    clear_config_env(monkeypatch)
    secret = "super-secret-token"
    monkeypatch.setenv("ASTRA_DB_APPLICATION_TOKEN", secret)

    result = config.validate_config("astra")
    message_text = "\n".join(result.messages)

    assert secret not in message_text
    assert "ASTRA_DB_APPLICATION_TOKEN" not in result.missing


def test_blank_optional_variables_do_not_fail_app_base_validation(monkeypatch):
    clear_config_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ASTRA_DB_KEYSPACE", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")

    result = config.validate_config("base")

    assert result.ok
    assert result.missing == ()


def test_missing_required_variables_are_reported_by_name(monkeypatch):
    clear_config_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ASTRA_PERSONAL_COLLECTION", "personal_data")
    monkeypatch.setenv("ASTRA_NOTES_COLLECTION", "notes")

    result = config.validate_config("astra")

    assert not result.ok
    assert result.missing == (
        "ASTRA_DB_API_ENDPOINT",
        "ASTRA_DB_APPLICATION_TOKEN",
    )
