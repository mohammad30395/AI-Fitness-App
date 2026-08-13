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

    with pytest.raises(requests.HTTPError) as exc_info:
        ai.run_flow("flow-123", "profile context")

    assert str(status_code) in str(exc_info.value)
    assert "secret-langflow-key" not in str(exc_info.value)


def test_run_flow_timeout_propagates_without_secret(monkeypatch):
    patch_langflow_config(monkeypatch)

    def fake_post(url, *, headers, json, timeout):
        raise requests.Timeout("request timed out")

    monkeypatch.setattr(ai.requests, "post", fake_post)

    with pytest.raises(requests.Timeout) as exc_info:
        ai.run_flow("flow-123", "profile context", timeout=5)

    assert "secret-langflow-key" not in str(exc_info.value)


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
