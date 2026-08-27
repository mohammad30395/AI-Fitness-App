from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

import requests

import config
from utils import parse_nutrition_json


DEFAULT_INPUT_TYPE = "chat"
DEFAULT_OUTPUT_TYPE = "chat"
DEFAULT_TIMEOUT_SECONDS = 60.0


class LangflowClientError(Exception):
    """Base error for Langflow client failures."""


class LangflowConfigError(LangflowClientError):
    """Raised when required Langflow client configuration is missing."""


class LangflowResponseError(LangflowClientError):
    """Raised when Langflow returns an unexpected response shape."""


class LangflowHTTPError(LangflowClientError):
    """Raised when Langflow returns a non-success HTTP status."""


class LangflowTimeoutError(LangflowClientError):
    """Raised when a Langflow request times out."""


class LangflowConnectionError(LangflowClientError):
    """Raised when Langflow cannot be reached."""


def _sanitize_diagnostic(message: Any) -> str:
    sanitized = str(message)
    for name in getattr(config, "ALL_VARIABLES", ()):
        value = config.get_env_value(name)
        if value and len(value) >= 4:
            sanitized = sanitized.replace(value, f"<redacted:{name}>")
    sanitized = re.sub(r"AstraCS:[A-Za-z0-9._:-]+", "AstraCS:<redacted>", sanitized)
    sanitized = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-<redacted>", sanitized)
    sanitized = re.sub(r"(https?://)[^/\s:@]+:[^/\s@]+@", r"\1<redacted>@", sanitized)
    return sanitized


def _require_config_value(name: str) -> str:
    value = config.get_env_value(name).strip()
    if not value:
        raise LangflowConfigError(f"Missing required environment variable: {name}")
    return value


def _build_run_url(base_url: str, flow_id: str) -> str:
    cleaned_base_url = base_url.rstrip("/")
    parsed_url = urlparse(cleaned_base_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise LangflowConfigError("LANGFLOW_URL must be a valid http(s) URL.")
    if parsed_url.scheme == "http" and parsed_url.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise LangflowConfigError("LANGFLOW_URL must use https for non-local hosts.")

    cleaned_flow_id = flow_id.strip().strip("/")
    if not cleaned_flow_id:
        raise LangflowConfigError("flow_id is required.")
    return f"{cleaned_base_url}/api/v1/run/{cleaned_flow_id}"


def _validate_timeout(timeout: float) -> float:
    try:
        timeout_value = float(timeout)
    except (TypeError, ValueError) as exc:
        raise ValueError("timeout must be a positive number of seconds.") from exc
    if timeout_value <= 0:
        raise ValueError("timeout must be a positive number of seconds.")
    return timeout_value


def build_ask_ai_search_filter(account_id: str, profile_id: str) -> dict[str, str]:
    """Build the account-scoped metadata filter for Ask AI note retrieval."""
    if not isinstance(account_id, str) or not account_id.strip():
        raise ValueError("account_id must be a non-empty string.")
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise ValueError("profile_id must be a non-empty string.")

    return {
        "owner_account_id": account_id.strip(),
        "user_id": profile_id.strip(),
    }


def _top_level_preview(data: Any) -> str:
    if isinstance(data, Mapping):
        keys = sorted(str(key) for key in data.keys())
        return f"top-level keys: {keys}"
    return f"top-level type: {type(data).__name__}"


def extract_langflow_message_text(data: Any) -> str:
    """Extract message text from the current Langflow v1 chat response shape."""
    if not isinstance(data, Mapping):
        raise LangflowResponseError(f"Expected JSON object from Langflow; {_top_level_preview(data)}.")

    outputs = data.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise LangflowResponseError(
            "Expected non-empty list at response['outputs']; "
            f"{_top_level_preview(data)}."
        )

    first_output = outputs[0]
    if not isinstance(first_output, Mapping):
        raise LangflowResponseError(
            "Expected object at response['outputs'][0]; "
            f"{_top_level_preview(data)}."
        )

    component_outputs = first_output.get("outputs")
    if not isinstance(component_outputs, list) or not component_outputs:
        raise LangflowResponseError(
            "Expected non-empty list at response['outputs'][0]['outputs']; "
            f"{_top_level_preview(data)}."
        )

    first_component_output = component_outputs[0]
    if not isinstance(first_component_output, Mapping):
        raise LangflowResponseError(
            "Expected object at response['outputs'][0]['outputs'][0]; "
            f"{_top_level_preview(data)}."
        )

    results = first_component_output.get("results")
    if not isinstance(results, Mapping):
        raise LangflowResponseError(
            "Expected object at response['outputs'][0]['outputs'][0]['results']; "
            f"{_top_level_preview(data)}."
        )

    message = results.get("message")
    if not isinstance(message, Mapping):
        raise LangflowResponseError(
            "Expected object at response['outputs'][0]['outputs'][0]['results']['message']; "
            f"{_top_level_preview(data)}."
        )

    text = message.get("text")
    if not isinstance(text, str):
        raise LangflowResponseError(
            "Expected string at response['outputs'][0]['outputs'][0]['results']['message']['text']; "
            f"{_top_level_preview(data)}."
        )

    return text


def run_flow(
    flow_id: str,
    input_value: str,
    *,
    input_type: str = DEFAULT_INPUT_TYPE,
    output_type: str = DEFAULT_OUTPUT_TYPE,
    tweaks: Mapping[str, Any] | None = None,
    session_id: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Run a Langflow v1 flow and return the response message text."""
    base_url = _require_config_value("LANGFLOW_URL")
    api_key = _require_config_value("LANGFLOW_API_KEY")
    url = _build_run_url(base_url, flow_id)
    timeout_value = _validate_timeout(timeout)

    payload: dict[str, Any] = {
        "output_type": output_type,
        "input_type": input_type,
        "input_value": input_value,
    }
    if tweaks is not None:
        payload["tweaks"] = dict(tweaks)
    if session_id:
        payload["session_id"] = session_id

    response = None
    try:
        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
            },
            json=payload,
            timeout=timeout_value,
        )
        response.raise_for_status()
    except requests.Timeout as exc:
        raise LangflowTimeoutError(
            f"Langflow request timed out after {timeout_value:g} seconds."
        ) from exc
    except requests.HTTPError as exc:
        status_code = getattr(response, "status_code", None)
        if status_code is None and getattr(exc, "response", None) is not None:
            status_code = getattr(exc.response, "status_code", None)
        status_label = status_code if status_code is not None else "unknown"
        raise LangflowHTTPError(
            f"Langflow HTTP request failed with status {status_label}."
        ) from exc
    except requests.RequestException as exc:
        raise LangflowConnectionError(
            f"Langflow request failed ({type(exc).__name__}): "
            f"{_sanitize_diagnostic(str(exc))}"
        ) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise LangflowResponseError("Langflow returned a non-JSON response.") from exc

    return extract_langflow_message_text(data)


def get_macros(profile_context: str, goals: str) -> dict[str, int | float]:
    """Run the configured Macro Flow and return normalized nutrition targets."""
    if not isinstance(profile_context, str) or not profile_context.strip():
        raise ValueError("profile_context must be a non-empty string.")

    flow_id = _require_config_value("MACRO_FLOW_ID")
    goals_component_id = _require_config_value("MACRO_GOALS_COMPONENT_ID")

    text = run_flow(
        flow_id,
        profile_context,
        input_type=DEFAULT_INPUT_TYPE,
        output_type=DEFAULT_OUTPUT_TYPE,
        tweaks={
            goals_component_id: {
                "goals": goals,
            }
        },
    )
    return parse_nutrition_json(text)


def ask_ai(
    question: str,
    profile_context: str,
    account_id: str,
    profile_id: str,
    session_id: str | None = None,
) -> str:
    """Run Ask AI V2 through Langflow and return the final plain-text answer."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string.")
    if not isinstance(profile_context, str) or not profile_context.strip():
        raise ValueError("profile_context must be a non-empty string.")
    search_filter = build_ask_ai_search_filter(account_id, profile_id)

    flow_id = _require_config_value("ASK_AI_FLOW_ID")
    profile_component_id = _require_config_value("ASK_PROFILE_COMPONENT_ID")
    user_id_component_id = _require_config_value("ASK_USER_ID_COMPONENT_ID")

    return run_flow(
        flow_id,
        question.strip(),
        input_type=DEFAULT_INPUT_TYPE,
        output_type=DEFAULT_OUTPUT_TYPE,
        session_id=session_id,
        tweaks={
            profile_component_id: {
                "profile": profile_context,
            },
            user_id_component_id: {
                "advanced_search_filter": json.dumps(search_filter),
            },
        },
    )
