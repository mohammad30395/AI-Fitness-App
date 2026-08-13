import pytest
import requests

import ai


def patch_langflow_config(monkeypatch):
    values = {
        "LANGFLOW_URL": "http://127.0.0.1:7860",
        "LANGFLOW_API_KEY": "secret-langflow-key",
    }
    monkeypatch.setattr(ai.config, "get_env_value", lambda name: values.get(name, ""))
    return values


def patch_macro_config(monkeypatch, *, flow_id="macro-flow", goals_component_id="Prompt Template-VgARU"):
    values = {
        "MACRO_FLOW_ID": flow_id,
        "MACRO_GOALS_COMPONENT_ID": goals_component_id,
    }
    monkeypatch.setattr(ai.config, "get_env_value", lambda name: values.get(name, ""))
    return values


def patch_ask_ai_config(
    monkeypatch,
    *,
    flow_id="ask-flow",
    profile_component_id="Prompt Template-GtOCM",
    user_id_component_id="ext:datastax:AstraDBVectorStoreComponent@official-2VBhC",
):
    values = {
        "ASK_AI_FLOW_ID": flow_id,
        "ASK_PROFILE_COMPONENT_ID": profile_component_id,
        "ASK_USER_ID_COMPONENT_ID": user_id_component_id,
    }
    monkeypatch.setattr(ai.config, "get_env_value", lambda name: values.get(name, ""))
    return values


def langflow_success_response(text='{"calories": 2200, "protein": 150, "fat": 70, "carbs": 250}'):
    return {
        "session_id": "session-1",
        "outputs": [
            {
                "inputs": {"input_value": "profile text"},
                "outputs": [
                    {
                        "results": {
                            "message": {
                                "text": text,
                                "sender": "Machine",
                                "sender_name": "AI",
                            }
                        }
                    }
                ],
            }
        ],
    }


class FakeResponse:
    def __init__(self, *, json_data=None, status_code=200, json_exc=None, http_exc=None):
        self._json_data = json_data
        self.status_code = status_code
        self._json_exc = json_exc
        self._http_exc = http_exc

    def raise_for_status(self):
        if self._http_exc:
            raise self._http_exc

    def json(self):
        if self._json_exc:
            raise self._json_exc
        return self._json_data


def test_run_flow_success_posts_current_langflow_contract(monkeypatch):
    patch_langflow_config(monkeypatch)
    calls = []

    def fake_post(url, *, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return FakeResponse(json_data=langflow_success_response())

    monkeypatch.setattr(ai.requests, "post", fake_post)

    text = ai.run_flow(
        "flow-123",
        "profile context",
        tweaks={"Prompt Template-VgARU": {"goals": "build strength"}},
        session_id="session-1",
        timeout=12,
    )

    assert text == '{"calories": 2200, "protein": 150, "fat": 70, "carbs": 250}'
    assert calls == [
        (
            "http://127.0.0.1:7860/api/v1/run/flow-123",
            {
                "Content-Type": "application/json",
                "x-api-key": "secret-langflow-key",
            },
            {
                "output_type": "chat",
                "input_type": "chat",
                "input_value": "profile context",
                "tweaks": {"Prompt Template-VgARU": {"goals": "build strength"}},
                "session_id": "session-1",
            },
            12.0,
        )
    ]


@pytest.mark.parametrize("status_code", [401, 403])
def test_run_flow_auth_errors_call_raise_for_status(monkeypatch, status_code):
    patch_langflow_config(monkeypatch)
    http_error = requests.HTTPError(f"{status_code} Client Error")

    def fake_post(url, *, headers, json, timeout):
        return FakeResponse(status_code=status_code, http_exc=http_error)

    monkeypatch.setattr(ai.requests, "post", fake_post)

    with pytest.raises(ai.LangflowHTTPError) as exc_info:
        ai.run_flow("flow-123", "profile context")

    assert str(status_code) in str(exc_info.value)
    assert "secret-langflow-key" not in str(exc_info.value)
    assert exc_info.value.__cause__ is http_error


def test_run_flow_timeout_propagates_without_secret(monkeypatch):
    patch_langflow_config(monkeypatch)

    def fake_post(url, *, headers, json, timeout):
        raise requests.Timeout("request timed out")

    monkeypatch.setattr(ai.requests, "post", fake_post)

    with pytest.raises(ai.LangflowTimeoutError) as exc_info:
        ai.run_flow("flow-123", "profile context", timeout=5)

    assert "secret-langflow-key" not in str(exc_info.value)
    assert "5 seconds" in str(exc_info.value)


def test_run_flow_connection_error_sanitizes_diagnostics(monkeypatch):
    patch_langflow_config(monkeypatch)

    def fake_post(url, *, headers, json, timeout):
        raise requests.ConnectionError(
            "failed with secret-langflow-key and http://user:password@example.test"
        )

    monkeypatch.setattr(ai.requests, "post", fake_post)

    with pytest.raises(ai.LangflowConnectionError) as exc_info:
        ai.run_flow("flow-123", "profile context")

    message = str(exc_info.value)
    assert "secret-langflow-key" not in message
    assert "password" not in message
    assert "<redacted:LANGFLOW_API_KEY>" in message


def test_run_flow_non_json_response_raises_clear_error(monkeypatch):
    patch_langflow_config(monkeypatch)

    def fake_post(url, *, headers, json, timeout):
        return FakeResponse(json_exc=ValueError("not json"))

    monkeypatch.setattr(ai.requests, "post", fake_post)

    with pytest.raises(ai.LangflowResponseError) as exc_info:
        ai.run_flow("flow-123", "profile context")

    assert "non-JSON" in str(exc_info.value)
    assert "secret-langflow-key" not in str(exc_info.value)


def test_run_flow_unexpected_json_shape_reports_sanitized_top_level_keys(monkeypatch):
    patch_langflow_config(monkeypatch)

    def fake_post(url, *, headers, json, timeout):
        return FakeResponse(json_data={"outputs": [], "sensitive_text": "profile details"})

    monkeypatch.setattr(ai.requests, "post", fake_post)

    with pytest.raises(ai.LangflowResponseError) as exc_info:
        ai.run_flow("flow-123", "profile context")

    message = str(exc_info.value)
    assert "response['outputs']" in message
    assert "top-level keys" in message
    assert "sensitive_text" in message
    assert "profile details" not in message
    assert "secret-langflow-key" not in message


def test_extract_langflow_message_text_rejects_non_string_text():
    response = langflow_success_response(text=123)

    with pytest.raises(ai.LangflowResponseError):
        ai.extract_langflow_message_text(response)


def test_run_flow_rejects_missing_config_without_secret(monkeypatch):
    monkeypatch.setattr(ai.config, "get_env_value", lambda name: "")

    with pytest.raises(ai.LangflowConfigError) as exc_info:
        ai.run_flow("flow-123", "profile context")

    assert "LANGFLOW_URL" in str(exc_info.value)


def test_get_macros_uses_configured_macro_flow_and_goals_component(monkeypatch):
    patch_macro_config(monkeypatch)
    calls = []

    def fake_run_flow(flow_id, input_value, **kwargs):
        calls.append((flow_id, input_value, kwargs))
        return '{"calories": 2200, "protein": 150, "fat": 70, "carbs": 250}'

    monkeypatch.setattr(ai, "run_flow", fake_run_flow)

    result = ai.get_macros("profile context", "build strength")

    assert result == {
        "calories": 2200,
        "protein": 150,
        "fat": 70,
        "carbs": 250,
    }
    assert calls == [
        (
            "macro-flow",
            "profile context",
            {
                "input_type": "chat",
                "output_type": "chat",
                "tweaks": {
                    "Prompt Template-VgARU": {
                        "goals": "build strength",
                    }
                },
            },
        )
    ]


@pytest.mark.parametrize(
    "values",
    [
        {"MACRO_FLOW_ID": "", "MACRO_GOALS_COMPONENT_ID": "Prompt Template-VgARU"},
        {"MACRO_FLOW_ID": "macro-flow", "MACRO_GOALS_COMPONENT_ID": ""},
    ],
)
def test_get_macros_rejects_missing_macro_configuration(monkeypatch, values):
    monkeypatch.setattr(ai.config, "get_env_value", lambda name: values.get(name, ""))

    with pytest.raises(ai.LangflowConfigError):
        ai.get_macros("profile context", "build strength")


@pytest.mark.parametrize("profile_context", ["", "   ", None])
def test_get_macros_rejects_blank_profile_context(monkeypatch, profile_context):
    patch_macro_config(monkeypatch)

    with pytest.raises(ValueError, match="profile_context"):
        ai.get_macros(profile_context, "build strength")


def test_ask_ai_uses_configured_flow_and_runtime_tweaks(monkeypatch):
    patch_ask_ai_config(monkeypatch)
    calls = []

    def fake_run_flow(flow_id, input_value, **kwargs):
        calls.append((flow_id, input_value, kwargs))
        return "Use your notes to structure next week around recovery and strength."

    monkeypatch.setattr(ai, "run_flow", fake_run_flow)

    result = ai.ask_ai(
        " Based on my notes, what should I do next week? ",
        "Profile id: profile-1\nActivity level: moderate",
        "profile-1",
        session_id="session-ask",
    )

    assert result == "Use your notes to structure next week around recovery and strength."
    assert calls == [
        (
            "ask-flow",
            "Based on my notes, what should I do next week?",
            {
                "input_type": "chat",
                "output_type": "chat",
                "session_id": "session-ask",
                "tweaks": {
                    "Prompt Template-GtOCM": {
                        "profile": "Profile id: profile-1\nActivity level: moderate",
                    },
                    "ext:datastax:AstraDBVectorStoreComponent@official-2VBhC": {
                        "advanced_search_filter": '{"user_id": "profile-1"}',
                    },
                },
            },
        )
    ]


@pytest.mark.parametrize("question", ["", "   ", None])
def test_ask_ai_rejects_blank_questions(monkeypatch, question):
    patch_ask_ai_config(monkeypatch)

    with pytest.raises(ValueError, match="question"):
        ai.ask_ai(question, "profile context", "profile-1")


@pytest.mark.parametrize(
    ("profile_context", "user_id", "match"),
    [
        ("", "profile-1", "profile_context"),
        ("profile context", "", "user_id"),
        (None, "profile-1", "profile_context"),
        ("profile context", None, "user_id"),
    ],
)
def test_ask_ai_rejects_blank_runtime_context(monkeypatch, profile_context, user_id, match):
    patch_ask_ai_config(monkeypatch)

    with pytest.raises(ValueError, match=match):
        ai.ask_ai("What should I do next week?", profile_context, user_id)


@pytest.mark.parametrize(
    "values",
    [
        {
            "ASK_AI_FLOW_ID": "",
            "ASK_PROFILE_COMPONENT_ID": "Prompt Template-GtOCM",
            "ASK_USER_ID_COMPONENT_ID": "ext:datastax:AstraDBVectorStoreComponent@official-2VBhC",
        },
        {
            "ASK_AI_FLOW_ID": "ask-flow",
            "ASK_PROFILE_COMPONENT_ID": "",
            "ASK_USER_ID_COMPONENT_ID": "ext:datastax:AstraDBVectorStoreComponent@official-2VBhC",
        },
        {
            "ASK_AI_FLOW_ID": "ask-flow",
            "ASK_PROFILE_COMPONENT_ID": "Prompt Template-GtOCM",
            "ASK_USER_ID_COMPONENT_ID": "",
        },
    ],
)
def test_ask_ai_rejects_missing_configuration(monkeypatch, values):
    monkeypatch.setattr(ai.config, "get_env_value", lambda name: values.get(name, ""))

    with pytest.raises(ai.LangflowConfigError) as exc_info:
        ai.ask_ai("What should I do next week?", "profile context", "profile-1")

    assert "Missing required environment variable" in str(exc_info.value)


def test_ask_ai_propagates_langflow_errors_without_secrets(monkeypatch):
    patch_ask_ai_config(monkeypatch)

    def fake_run_flow(flow_id, input_value, **kwargs):
        raise ai.LangflowResponseError("Expected response shape; top-level keys: ['outputs']")

    monkeypatch.setattr(ai, "run_flow", fake_run_flow)

    with pytest.raises(ai.LangflowResponseError) as exc_info:
        ai.ask_ai("What should I do next week?", "profile context", "profile-1")

    assert "top-level keys" in str(exc_info.value)
    assert "secret" not in str(exc_info.value).lower()
