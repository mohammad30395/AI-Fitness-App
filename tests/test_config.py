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


def test_langflow_required_variables_are_reported_by_name(monkeypatch):
    clear_config_env(monkeypatch)
    monkeypatch.setenv("LANGFLOW_URL", "http://127.0.0.1:7860")
    monkeypatch.setenv("LANGFLOW_API_KEY", "secret-langflow-key")

    result = config.validate_config("langflow")

    assert not result.ok
    assert result.missing == (
        "MACRO_FLOW_ID",
        "ASK_AI_FLOW_ID",
        "MACRO_PROFILE_COMPONENT_ID",
        "MACRO_GOALS_COMPONENT_ID",
        "ASK_PROFILE_COMPONENT_ID",
        "ASK_USER_ID_COMPONENT_ID",
    )
    assert "secret-langflow-key" not in "\n".join(result.messages)


def test_variable_status_reports_booleans_without_values(monkeypatch):
    clear_config_env(monkeypatch)
    monkeypatch.setenv("LANGFLOW_API_KEY", "secret-langflow-key")
    monkeypatch.setenv("LANGFLOW_URL", "")

    status = config.variable_status(["LANGFLOW_API_KEY", "LANGFLOW_URL", "MACRO_FLOW_ID"])

    assert status == {
        "LANGFLOW_API_KEY": True,
        "LANGFLOW_URL": False,
        "MACRO_FLOW_ID": False,
    }
    assert "secret-langflow-key" not in repr(status)
