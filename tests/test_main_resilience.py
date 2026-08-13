import main


def test_ui_diagnostic_sanitizer_redacts_known_secret_values(monkeypatch):
    values = {
        "LANGFLOW_API_KEY": "secret-langflow-key",
        "ASTRA_DB_APPLICATION_TOKEN": "AstraCS:super-secret-token",
    }
    monkeypatch.setattr(main.config, "get_env_value", lambda name: values.get(name, ""))

    sanitized = main._sanitize_diagnostic(
        "failed with secret-langflow-key, AstraCS:super-secret-token, "
        "and http://user:password@example.test"
    )

    assert "secret-langflow-key" not in sanitized
    assert "AstraCS:super-secret-token" not in sanitized
    assert "password" not in sanitized
    assert "<redacted:LANGFLOW_API_KEY>" in sanitized
    assert "<redacted:ASTRA_DB_APPLICATION_TOKEN>" in sanitized


def test_safe_ui_errors_are_user_friendly_without_low_level_details():
    error = RuntimeError("AstraCS:super-secret-token")

    assert "AstraCS" not in main._safe_profile_error("Loading profiles", error)
    assert "AstraCS" not in main._safe_notes_error("Loading notes", error)
    assert "AstraCS" not in main._safe_macro_error("Generating macros", error)
    assert "AstraCS" not in main._safe_ask_ai_error("Ask AI", error)
