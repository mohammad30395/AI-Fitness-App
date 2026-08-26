import os
from dataclasses import dataclass
from typing import Iterable

from dotenv import load_dotenv


load_dotenv()


APP_ENV = os.getenv("APP_ENV", "development")
ASTRA_DB_API_ENDPOINT = os.getenv("ASTRA_DB_API_ENDPOINT", "")
ASTRA_DB_APPLICATION_TOKEN = os.getenv("ASTRA_DB_APPLICATION_TOKEN", "")
ASTRA_DB_KEYSPACE = os.getenv("ASTRA_DB_KEYSPACE", "")
ASTRA_PERSONAL_COLLECTION = os.getenv("ASTRA_PERSONAL_COLLECTION", "personal_data")
ASTRA_NOTES_COLLECTION = os.getenv("ASTRA_NOTES_COLLECTION", "notes")
ASTRA_ACCOUNTS_COLLECTION = os.getenv("ASTRA_ACCOUNTS_COLLECTION", "accounts")
LANGFLOW_URL = os.getenv("LANGFLOW_URL", "")
LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY", "")
MACRO_FLOW_ID = os.getenv("MACRO_FLOW_ID", "")
ASK_AI_FLOW_ID = os.getenv("ASK_AI_FLOW_ID", "")
MACRO_PROFILE_COMPONENT_ID = os.getenv("MACRO_PROFILE_COMPONENT_ID", "")
MACRO_GOALS_COMPONENT_ID = os.getenv("MACRO_GOALS_COMPONENT_ID", "")
ASK_PROFILE_COMPONENT_ID = os.getenv("ASK_PROFILE_COMPONENT_ID", "")
ASK_USER_ID_COMPONENT_ID = os.getenv("ASK_USER_ID_COMPONENT_ID", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")


BASE_VARIABLES = ("APP_ENV",)
BASE_REQUIRED_VARIABLES = ()

ASTRA_REQUIRED_VARIABLES = (
    "ASTRA_DB_API_ENDPOINT",
    "ASTRA_DB_APPLICATION_TOKEN",
    "ASTRA_PERSONAL_COLLECTION",
    "ASTRA_NOTES_COLLECTION",
)

ASTRA_OPTIONAL_VARIABLES = (
    # AstraPy Data API usage does not always require an explicit keyspace.
    "ASTRA_DB_KEYSPACE",
    "ASTRA_ACCOUNTS_COLLECTION",
)

LANGFLOW_REQUIRED_VARIABLES = (
    "LANGFLOW_URL",
    "LANGFLOW_API_KEY",
    "MACRO_FLOW_ID",
    "ASK_AI_FLOW_ID",
    "MACRO_PROFILE_COMPONENT_ID",
    "MACRO_GOALS_COMPONENT_ID",
    "ASK_PROFILE_COMPONENT_ID",
    "ASK_USER_ID_COMPONENT_ID",
)

FUTURE_OPTIONAL_VARIABLES = (
    # The Streamlit app should call Langflow, not OpenRouter, in this architecture.
    "OPENROUTER_API_KEY",
)

ALL_VARIABLES = (
    BASE_VARIABLES
    + ASTRA_REQUIRED_VARIABLES
    + ASTRA_OPTIONAL_VARIABLES
    + LANGFLOW_REQUIRED_VARIABLES
    + FUTURE_OPTIONAL_VARIABLES
)

REQUIRED_BY_MODE = {
    "base": BASE_REQUIRED_VARIABLES,
    "astra": ASTRA_REQUIRED_VARIABLES,
    "langflow": LANGFLOW_REQUIRED_VARIABLES,
    "all": ASTRA_REQUIRED_VARIABLES + LANGFLOW_REQUIRED_VARIABLES,
}


@dataclass(frozen=True)
class ValidationResult:
    mode: str
    missing: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.missing

    @property
    def messages(self) -> tuple[str, ...]:
        if self.ok:
            return (f"Configuration mode '{self.mode}' is valid.",)
        return tuple(f"Missing required environment variable: {name}" for name in self.missing)


def get_env_value(name: str) -> str:
    return os.getenv(name, "")


def is_set(name: str) -> bool:
    return bool(get_env_value(name).strip())


def missing_required(mode: str = "base") -> tuple[str, ...]:
    required = REQUIRED_BY_MODE.get(mode)
    if required is None:
        allowed = ", ".join(sorted(REQUIRED_BY_MODE))
        raise ValueError(f"Unknown config validation mode '{mode}'. Expected one of: {allowed}")
    return tuple(name for name in required if not is_set(name))


def validate_config(mode: str = "base") -> ValidationResult:
    return ValidationResult(mode=mode, missing=missing_required(mode))


def variable_status(names: Iterable[str] = ALL_VARIABLES) -> dict[str, bool]:
    return {name: is_set(name) for name in names}
