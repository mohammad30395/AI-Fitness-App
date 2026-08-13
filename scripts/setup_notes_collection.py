#!/usr/bin/env python
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from astrapy import DataAPIClient  # noqa: E402
from astrapy.exceptions import DataAPIException, InvalidEnvironmentException  # noqa: E402
from astrapy.info import CollectionDefinition  # noqa: E402

import config  # noqa: E402


REDACTED = "[redacted]"
TARGET_PROVIDER = "nvidia"
TARGET_MODEL = "nvidia/nv-embedqa-e5-v5"
VECTOR_METRIC = "cosine"


class SetupStopped(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderModel:
    provider: str
    model: str
    vector_dimension: int | None


@dataclass(frozen=True)
class NotesSetupResult:
    collection_name: str
    action: str
    provider: str
    model: str

    @property
    def created(self) -> bool:
        return self.action == "created"

    @property
    def reused(self) -> bool:
        return self.action == "reused"


def _configured_values() -> dict[str, str]:
    configured_name = (
        config.get_env_value("ASTRA_NOTES_COLLECTION").strip()
        or config.ASTRA_NOTES_COLLECTION
        or "notes"
    )
    return {
        "ASTRA_DB_API_ENDPOINT": config.get_env_value("ASTRA_DB_API_ENDPOINT").strip(),
        "ASTRA_DB_APPLICATION_TOKEN": config.get_env_value("ASTRA_DB_APPLICATION_TOKEN").strip(),
        "ASTRA_DB_KEYSPACE": config.get_env_value("ASTRA_DB_KEYSPACE").strip(),
        "ASTRA_NOTES_COLLECTION": configured_name,
    }


def _missing_required(values: dict[str, str]) -> tuple[str, ...]:
    required = (
        "ASTRA_DB_API_ENDPOINT",
        "ASTRA_DB_APPLICATION_TOKEN",
        "ASTRA_NOTES_COLLECTION",
    )
    return tuple(name for name in required if not values[name])


def sanitize_message(message: object, secret_values: Sequence[str]) -> str:
    sanitized = str(message)
    for value in secret_values:
        if value:
            sanitized = sanitized.replace(value, REDACTED)
    sanitized = re.sub(r"AstraCS:[A-Za-z0-9:_\\-\\.]+", REDACTED, sanitized)
    return sanitized


def _database_from_config(values: dict[str, str]):
    client = DataAPIClient(values["ASTRA_DB_APPLICATION_TOKEN"])
    if values["ASTRA_DB_KEYSPACE"]:
        return client.get_database(
            values["ASTRA_DB_API_ENDPOINT"],
            keyspace=values["ASTRA_DB_KEYSPACE"],
        )
    return client.get_database(values["ASTRA_DB_API_ENDPOINT"])


def _visible_provider_models(database) -> tuple[ProviderModel, ...]:
    providers = database.get_database_admin().find_embedding_providers().embedding_providers
    visible: list[ProviderModel] = []
    for provider_name, provider in sorted(providers.items()):
        for model in provider.models:
            visible.append(
                ProviderModel(
                    provider=provider_name,
                    model=model.name,
                    vector_dimension=model.vector_dimension,
                )
            )
    return tuple(visible)


def _target_model_available(models: Sequence[ProviderModel]) -> bool:
    return any(
        model.provider == TARGET_PROVIDER and model.model == TARGET_MODEL
        for model in models
    )


def _format_models(models: Sequence[ProviderModel]) -> str:
    if not models:
        return "No embedding provider models were visible."
    return "\n".join(
        f"- {model.provider}: {model.model} (dimension: {model.vector_dimension})"
        for model in models
    )


def _collection_descriptor(database, collection_name: str) -> Any | None:
    for descriptor in database.list_collections():
        descriptor_name = getattr(descriptor, "name", None)
        if descriptor_name is None and hasattr(descriptor, "as_dict"):
            descriptor_name = descriptor.as_dict().get("name")
        if descriptor_name == collection_name:
            return descriptor
    return None


def _descriptor_dict(descriptor: Any) -> dict[str, Any]:
    if hasattr(descriptor, "as_dict"):
        return descriptor.as_dict()
    if isinstance(descriptor, dict):
        return descriptor
    return getattr(descriptor, "__dict__", {})


def _vector_service(descriptor: Any) -> dict[str, Any]:
    descriptor_dict = _descriptor_dict(descriptor)
    vector_options = descriptor_dict.get("options", {}).get("vector", {})
    return vector_options.get("service", {}) if isinstance(vector_options, dict) else {}


def _is_compatible_vectorize_collection(descriptor: Any) -> bool:
    service = _vector_service(descriptor)
    return (
        service.get("provider") == TARGET_PROVIDER
        and service.get("modelName") == TARGET_MODEL
    )


def _vectorize_definition() -> CollectionDefinition:
    return (
        CollectionDefinition.builder()
        .with_vector_service(TARGET_PROVIDER, TARGET_MODEL)
        .with_vector_metric(VECTOR_METRIC)
    )


def setup_notes_collection() -> NotesSetupResult:
    values = _configured_values()
    collection_name = values["ASTRA_NOTES_COLLECTION"]
    missing = _missing_required(values)
    if missing:
        missing_names = ", ".join(missing)
        raise SetupStopped(f"Missing required environment variables: {missing_names}")

    database = _database_from_config(values)
    visible_models = _visible_provider_models(database)
    if not _target_model_available(visible_models):
        raise SetupStopped(
            f"Required Astra-hosted NVIDIA model is unavailable: "
            f"provider={TARGET_PROVIDER}, model={TARGET_MODEL}\n"
            f"Supported options visible to this database/token:\n{_format_models(visible_models)}"
        )

    existing_names = database.list_collection_names()
    if collection_name in existing_names:
        descriptor = _collection_descriptor(database, collection_name)
        if descriptor is None:
            raise SetupStopped(
                f"Collection '{collection_name}' exists but metadata could not be inspected."
            )
        if not _is_compatible_vectorize_collection(descriptor):
            raise SetupStopped(
                f"Collection '{collection_name}' already exists but is not compatible with "
                f"{TARGET_PROVIDER}/{TARGET_MODEL}. Changing collection vector settings "
                "requires a migration or a new collection."
            )
        return NotesSetupResult(
            collection_name=collection_name,
            action="reused",
            provider=TARGET_PROVIDER,
            model=TARGET_MODEL,
        )

    database.create_collection(collection_name, definition=_vectorize_definition())
    return NotesSetupResult(
        collection_name=collection_name,
        action="created",
        provider=TARGET_PROVIDER,
        model=TARGET_MODEL,
    )


def main() -> int:
    values = _configured_values()
    redaction_values = tuple(
        value
        for name, value in values.items()
        if name in {"ASTRA_DB_API_ENDPOINT", "ASTRA_DB_APPLICATION_TOKEN", "ASTRA_DB_KEYSPACE"}
    )

    print("Astra notes collection setup")
    print("Values are redacted; endpoint and token are never printed.")
    print(f"Required provider: {TARGET_PROVIDER}")
    print(f"Required model: {TARGET_MODEL}")

    try:
        result = setup_notes_collection()
    except SetupStopped as exc:
        print("Notes collection setup stopped.")
        print(f"Exception type: {type(exc).__name__}")
        print(f"Sanitized message: {sanitize_message(exc, redaction_values)}")
        return 1
    except (DataAPIException, InvalidEnvironmentException, OSError, ValueError) as exc:
        print("Notes collection setup failed.")
        print(f"Exception type: {type(exc).__name__}")
        print(f"Sanitized message: {sanitize_message(exc, redaction_values)}")
        print("Verify in Astra Portal:")
        print("- The database is active and is a Serverless vector database.")
        print("- ASTRA_DB_API_ENDPOINT matches the database API endpoint.")
        print("- ASTRA_DB_APPLICATION_TOKEN is valid and has collection management permissions.")
        print("- The Astra-hosted NVIDIA integration is available in this database region.")
        print("- If ASTRA_DB_KEYSPACE is configured, it exists and is accessible.")
        return 1

    print(f"Collection name: {result.collection_name}")
    if result.created:
        print("Action: created vectorize-enabled collection")
    else:
        print("Action: reused existing vectorize-enabled collection")
    print(f"Provider selected: {result.provider}")
    print(f"Model selected: {result.model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
