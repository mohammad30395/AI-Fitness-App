import json

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
    def __init__(
        self,
        *,
        json_data=None,
        status_code=200,
        json_exc=None,
        http_exc=None,
        text="",
    ):
        self._json_data = json_data
        self.status_code = status_code
        self._json_exc = json_exc
        self._http_exc = http_exc
        self.text = text

    def raise_for_status(self):
        if self._http_exc:
            raise self._http_exc

    def json(self):
        if self._json_exc:
            raise self._json_exc
        return self._json_data


def provider_402_payload():
    return {
        "detail": (
            "Error running graph: Error building Component OpenRouter: "
            "Error code: 402 - {'error': {'message': 'This request requires more "
            "credits, or fewer max_tokens to be set.', 'code': 402, 'metadata': "
            "{'provider_name': None}}, 'user_id': 'user-secret-id', "
            "'x-api-key': 'FAKE_LANGFLOW_SECRET_DO_NOT_LEAK', "
            "'authorization': 'FAKE_OPENROUTER_SECRET_DO_NOT_LEAK'}"
        )
    }


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


def test_run_flow_rejects_remote_plain_http_langflow_url(monkeypatch):
    values = {
        "LANGFLOW_URL": "http://langflow.example.test",
        "LANGFLOW_API_KEY": "secret-langflow-key",
    }
    monkeypatch.setattr(ai.config, "get_env_value", lambda name: values.get(name, ""))

    def fake_post(url, *, headers, json, timeout):
        raise AssertionError("requests.post must not be called for insecure remote URL")

    monkeypatch.setattr(ai.requests, "post", fake_post)

    with pytest.raises(ai.LangflowConfigError) as exc_info:
        ai.run_flow("flow-123", "profile context")

    assert "https" in str(exc_info.value)
    assert "secret-langflow-key" not in str(exc_info.value)


@pytest.mark.parametrize("status_code", [401, 403, 404, 500])
def test_run_flow_http_errors_call_raise_for_status(monkeypatch, status_code):
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
    assert exc_info.value.status_code == status_code
    assert exc_info.value.provider_status is None


def test_run_flow_provider_402_from_langflow_500_is_classified_safely(monkeypatch):
    patch_langflow_config(monkeypatch)
    http_error = requests.HTTPError("500 Server Error")

    def fake_post(url, *, headers, json, timeout):
        return FakeResponse(
            json_data=provider_402_payload(),
            status_code=500,
            http_exc=http_error,
        )

    monkeypatch.setattr(ai.requests, "post", fake_post)

    with pytest.raises(ai.ProviderQuotaError) as exc_info:
        ai.run_flow("flow-123", "profile context containing private goals")

    error = exc_info.value
    message = str(error)
    diagnostic = error.diagnostic_summary
    assert error.status_code == 500
    assert error.provider_status == 402
    assert "provider billing/quota" in message
    assert "profile context containing private goals" not in message
    assert "profile context containing private goals" not in diagnostic
    assert "FAKE_LANGFLOW_SECRET_DO_NOT_LEAK" not in message
    assert "FAKE_OPENROUTER_SECRET_DO_NOT_LEAK" not in message
    assert "FAKE_LANGFLOW_SECRET_DO_NOT_LEAK" not in diagnostic
    assert "FAKE_OPENROUTER_SECRET_DO_NOT_LEAK" not in diagnostic
    assert "x-api-key" not in message.lower()
    assert "authorization" not in message.lower()
    assert "x-api-key" not in diagnostic.lower()
    assert "authorization" not in diagnostic.lower()
    assert "user-secret-id" not in diagnostic
    assert len(diagnostic) <= ai.MAX_HTTP_ERROR_DIAGNOSTIC_CHARS


@pytest.mark.parametrize(
    ("status_code", "payload"),
    [
        (401, {"detail": "Unauthorized Langflow request."}),
        (403, {"detail": "Forbidden Langflow request."}),
        (404, {"detail": "Flow not found."}),
        (500, {"detail": "Error running graph without provider quota evidence."}),
    ],
)
def test_run_flow_http_errors_do_not_false_positive_provider_quota(
    monkeypatch,
    status_code,
    payload,
):
    patch_langflow_config(monkeypatch)
    http_error = requests.HTTPError(f"{status_code} Error")

    def fake_post(url, *, headers, json, timeout):
        return FakeResponse(json_data=payload, status_code=status_code, http_exc=http_error)

    monkeypatch.setattr(ai.requests, "post", fake_post)

    with pytest.raises(ai.LangflowHTTPError) as exc_info:
        ai.run_flow("flow-123", "profile context")

    assert not isinstance(exc_info.value, ai.ProviderQuotaError)
    assert exc_info.value.status_code == status_code
    assert exc_info.value.provider_status is None


def test_run_flow_http_error_non_json_body_is_sanitized_and_capped(monkeypatch):
    patch_langflow_config(monkeypatch)
    http_error = requests.HTTPError("500 Server Error")
    body = (
        "internal failure FAKE_LANGFLOW_SECRET_DO_NOT_LEAK "
        "Authorization: FAKE_OPENROUTER_SECRET_DO_NOT_LEAK "
        + ("body-detail " * 80)
    )

    def fake_post(url, *, headers, json, timeout):
        return FakeResponse(
            status_code=500,
            http_exc=http_error,
            json_exc=ValueError("not json"),
            text=body,
        )

    monkeypatch.setattr(ai.requests, "post", fake_post)

    with pytest.raises(ai.LangflowHTTPError) as exc_info:
        ai.run_flow("flow-123", "profile context")

    message = str(exc_info.value)
    diagnostic = exc_info.value.diagnostic_summary
    assert "FAKE_LANGFLOW_SECRET_DO_NOT_LEAK" not in message
    assert "FAKE_OPENROUTER_SECRET_DO_NOT_LEAK" not in message
    assert "FAKE_LANGFLOW_SECRET_DO_NOT_LEAK" not in diagnostic
    assert "FAKE_OPENROUTER_SECRET_DO_NOT_LEAK" not in diagnostic
    assert "authorization" not in diagnostic.lower()
    assert len(diagnostic) <= ai.MAX_HTTP_ERROR_DIAGNOSTIC_CHARS
    assert len(diagnostic) < len(body)


def test_get_macros_preserves_provider_quota_classification(monkeypatch):
    patch_macro_config(monkeypatch)
    error = ai.ProviderQuotaError(
        "Langflow HTTP request failed with status 500. Upstream provider HTTP 402.",
        status_code=500,
        diagnostic_summary="OpenRouter 402 requires more credits",
        provider_status=402,
    )

    def fake_run_flow(flow_id, input_value, **kwargs):
        raise error

    monkeypatch.setattr(ai, "run_flow", fake_run_flow)

    with pytest.raises(ai.ProviderQuotaError) as exc_info:
        ai.get_macros("profile context", "build strength")

    assert exc_info.value.provider_status == 402


def test_ask_ai_preserves_provider_quota_classification(monkeypatch):
    patch_ask_ai_config(monkeypatch)
    error = ai.ProviderQuotaError(
        "Langflow HTTP request failed with status 500. Upstream provider HTTP 402.",
        status_code=500,
        diagnostic_summary="OpenRouter 402 requires more credits",
        provider_status=402,
    )

    def fake_run_flow(flow_id, input_value, **kwargs):
        raise error

    monkeypatch.setattr(ai, "run_flow", fake_run_flow)

    with pytest.raises(ai.ProviderQuotaError) as exc_info:
        ai.ask_ai("What next?", "profile context", "account-1", "profile-1")

    assert exc_info.value.provider_status == 402


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
    values = {
        "MACRO_FLOW_ID": "macro-flow",
        "MACRO_GOALS_COMPONENT_ID": "Prompt Template-VgARU",
        "MACRO_OPENROUTER_COMPONENT_ID": "ext:openrouter:OpenRouterComponent@official-snoVc",
        "MACRO_OPENROUTER_MAX_TOKENS": "512",
        "OPENROUTER_API_KEY": "fake-openrouter-key",
    }
    monkeypatch.setattr(ai.config, "get_env_value", lambda name: values.get(name, ""))
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
                    },
                    "ext:openrouter:OpenRouterComponent@official-snoVc": {
                        "max_tokens": 512,
                        "api_key": "fake-openrouter-key",
                    }
                },
            },
        )
    ]


def test_get_macros_caps_openrouter_tokens_without_openrouter_key(monkeypatch):
    patch_macro_config(monkeypatch)
    calls = []

    def fake_run_flow(flow_id, input_value, **kwargs):
        calls.append(kwargs)
        return '{"calories": 2200, "protein": 150, "fat": 70, "carbs": 250}'

    monkeypatch.setattr(ai, "run_flow", fake_run_flow)

    ai.get_macros("profile context", "build strength")

    openrouter_tweak = calls[0]["tweaks"]["ext:openrouter:OpenRouterComponent@official-snoVc"]
    assert openrouter_tweak == {"max_tokens": 512}


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
    values = {
        "ASK_AI_FLOW_ID": "ask-flow",
        "ASK_PROFILE_COMPONENT_ID": "Prompt Template-GtOCM",
        "ASK_USER_ID_COMPONENT_ID": "ext:datastax:AstraDBVectorStoreComponent@official-2VBhC",
        "ASK_ROUTER_OPENROUTER_COMPONENT_ID": "ext:openrouter:OpenRouterComponent@official-lyVR9",
        "ASK_ADVICE_OPENROUTER_COMPONENT_ID": "ext:openrouter:OpenRouterComponent@official-N7r20",
        "ASK_MATH_AGENT_COMPONENT_ID": "Agent-8TtHH",
        "ASK_ROUTER_OPENROUTER_MAX_TOKENS": "128",
        "ASK_ADVICE_OPENROUTER_MAX_TOKENS": "1024",
        "ASK_MATH_AGENT_MAX_TOKENS": "512",
        "OPENROUTER_API_KEY": "fake-openrouter-key",
    }
    monkeypatch.setattr(ai.config, "get_env_value", lambda name: values.get(name, ""))
    calls = []

    def fake_run_flow(flow_id, input_value, **kwargs):
        calls.append((flow_id, input_value, kwargs))
        return "Use your notes to structure next week around recovery and strength."

    monkeypatch.setattr(ai, "run_flow", fake_run_flow)

    result = ai.ask_ai(
        " Based on my notes, what should I do next week? ",
        "Profile id: profile-1\nActivity level: moderate",
        "account-1",
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
                        "advanced_search_filter": (
                            '{"owner_account_id": "account-1", "user_id": "profile-1"}'
                        ),
                    },
                    "ext:openrouter:OpenRouterComponent@official-lyVR9": {
                        "max_tokens": 128,
                        "api_key": "fake-openrouter-key",
                    },
                    "ext:openrouter:OpenRouterComponent@official-N7r20": {
                        "max_tokens": 1024,
                        "api_key": "fake-openrouter-key",
                    },
                    "Agent-8TtHH": {
                        "max_tokens": 512,
                        "api_key": "fake-openrouter-key",
                    },
                },
            },
        )
    ]


@pytest.mark.parametrize(
    ("account_id", "profile_id", "expected_filter"),
    [
        (
            "account-a",
            "profile-a",
            {"owner_account_id": "account-a", "user_id": "profile-a"},
        ),
        (
            "account-b",
            "profile-b",
            {"owner_account_id": "account-b", "user_id": "profile-b"},
        ),
    ],
)
def test_ask_ai_sends_compound_rag_filter_for_account_profile_pairings(
    monkeypatch,
    account_id,
    profile_id,
    expected_filter,
):
    patch_ask_ai_config(monkeypatch)
    calls = []

    def fake_run_flow(flow_id, input_value, **kwargs):
        calls.append(kwargs)
        return "Answer"

    monkeypatch.setattr(ai, "run_flow", fake_run_flow)

    ai.ask_ai("What should I do next week?", "profile context", account_id, profile_id)

    tweaks = calls[0]["tweaks"]
    astra_tweak = tweaks["ext:datastax:AstraDBVectorStoreComponent@official-2VBhC"]
    emitted_filter = json.loads(astra_tweak["advanced_search_filter"])
    assert emitted_filter == expected_filter
    assert set(emitted_filter) == {"owner_account_id", "user_id"}


def test_ask_ai_does_not_emit_old_profile_only_filter(monkeypatch):
    patch_ask_ai_config(monkeypatch)
    calls = []

    def fake_run_flow(flow_id, input_value, **kwargs):
        calls.append(kwargs)
        return "Answer"

    monkeypatch.setattr(ai, "run_flow", fake_run_flow)

    ai.ask_ai("What should I do next week?", "profile context", "account-1", "profile-1")

    astra_tweak = calls[0]["tweaks"]["ext:datastax:AstraDBVectorStoreComponent@official-2VBhC"]
    emitted_filter = json.loads(astra_tweak["advanced_search_filter"])
    assert emitted_filter != {"user_id": "profile-1"}
    assert emitted_filter == {"owner_account_id": "account-1", "user_id": "profile-1"}


def test_ask_ai_keeps_account_id_out_of_profile_context(monkeypatch):
    patch_ask_ai_config(monkeypatch)
    calls = []

    def fake_run_flow(flow_id, input_value, **kwargs):
        calls.append(kwargs)
        return "Answer"

    monkeypatch.setattr(ai, "run_flow", fake_run_flow)

    ai.ask_ai(
        "What should I do next week?",
        "Profile id: profile-1\nActivity level: moderate",
        "account-secret-id",
        "profile-1",
    )

    profile_tweak = calls[0]["tweaks"]["Prompt Template-GtOCM"]
    assert profile_tweak == {"profile": "Profile id: profile-1\nActivity level: moderate"}
    assert "account-secret-id" not in profile_tweak["profile"]


def test_ask_ai_does_not_generate_password_filter_fields(monkeypatch):
    patch_ask_ai_config(monkeypatch)
    calls = []

    def fake_run_flow(flow_id, input_value, **kwargs):
        calls.append(kwargs)
        return "Answer"

    monkeypatch.setattr(ai, "run_flow", fake_run_flow)

    ai.ask_ai("What should I do next week?", "profile context", "account-1", "profile-1")

    serialized_filter = calls[0]["tweaks"][
        "ext:datastax:AstraDBVectorStoreComponent@official-2VBhC"
    ]["advanced_search_filter"]
    assert "password" not in serialized_filter
    assert "password_hash" not in serialized_filter


def test_build_ask_ai_search_filter_returns_compound_ownership_filter():
    result = ai.build_ask_ai_search_filter("account-a", "profile-a")

    assert result == {
        "owner_account_id": "account-a",
        "user_id": "profile-a",
    }
    assert set(result) == {"owner_account_id", "user_id"}


@pytest.mark.parametrize(
    ("account_id", "profile_id", "expected"),
    [
        (
            "account-a",
            "profile-a",
            {"owner_account_id": "account-a", "user_id": "profile-a"},
        ),
        (
            "account-b",
            "profile-b",
            {"owner_account_id": "account-b", "user_id": "profile-b"},
        ),
    ],
)
def test_build_ask_ai_search_filter_preserves_account_profile_pairings(
    account_id,
    profile_id,
    expected,
):
    assert ai.build_ask_ai_search_filter(account_id, profile_id) == expected


def test_build_ask_ai_search_filter_does_not_substitute_username():
    result = ai.build_ask_ai_search_filter("account-uuid-123", "profile-1")

    assert result["owner_account_id"] == "account-uuid-123"
    assert "username" not in result
    assert "password" not in result
    assert "password_hash" not in result


@pytest.mark.parametrize("account_id", ["", "   ", None, 123])
def test_build_ask_ai_search_filter_rejects_invalid_account_id(account_id):
    with pytest.raises(ValueError, match="account_id"):
        ai.build_ask_ai_search_filter(account_id, "profile-a")


@pytest.mark.parametrize("profile_id", ["", "   ", None, 123])
def test_build_ask_ai_search_filter_rejects_invalid_profile_id(profile_id):
    with pytest.raises(ValueError, match="profile_id"):
        ai.build_ask_ai_search_filter("account-a", profile_id)


@pytest.mark.parametrize("question", ["", "   ", None])
def test_ask_ai_rejects_blank_questions(monkeypatch, question):
    patch_ask_ai_config(monkeypatch)

    with pytest.raises(ValueError, match="question"):
        ai.ask_ai(question, "profile context", "account-1", "profile-1")


@pytest.mark.parametrize(
    ("profile_context", "account_id", "profile_id", "match"),
    [
        ("", "account-1", "profile-1", "profile_context"),
        (None, "account-1", "profile-1", "profile_context"),
        ("profile context", "", "profile-1", "account_id"),
        ("profile context", "   ", "profile-1", "account_id"),
        ("profile context", None, "profile-1", "account_id"),
        ("profile context", 123, "profile-1", "account_id"),
        ("profile context", "account-1", "", "profile_id"),
        ("profile context", "account-1", "   ", "profile_id"),
        ("profile context", "account-1", None, "profile_id"),
        ("profile context", "account-1", 123, "profile_id"),
    ],
)
def test_ask_ai_rejects_invalid_runtime_context(
    monkeypatch,
    profile_context,
    account_id,
    profile_id,
    match,
):
    patch_ask_ai_config(monkeypatch)

    with pytest.raises(ValueError, match=match):
        ai.ask_ai("What should I do next week?", profile_context, account_id, profile_id)


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
        ai.ask_ai("What should I do next week?", "profile context", "account-1", "profile-1")

    assert "Missing required environment variable" in str(exc_info.value)


def test_ask_ai_propagates_langflow_errors_without_secrets(monkeypatch):
    patch_ask_ai_config(monkeypatch)

    def fake_run_flow(flow_id, input_value, **kwargs):
        raise ai.LangflowResponseError("Expected response shape; top-level keys: ['outputs']")

    monkeypatch.setattr(ai, "run_flow", fake_run_flow)

    with pytest.raises(ai.LangflowResponseError) as exc_info:
        ai.ask_ai("What should I do next week?", "profile context", "account-1", "profile-1")

    assert "top-level keys" in str(exc_info.value)
    assert "secret" not in str(exc_info.value).lower()
