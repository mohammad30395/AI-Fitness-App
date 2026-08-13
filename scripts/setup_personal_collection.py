#!/usr/bin/env python
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from astrapy import DataAPIClient  # noqa: E402
from astrapy.exceptions import DataAPIException, InvalidEnvironmentException  # noqa: E402

import config  # noqa: E402


REDACTED = "[redacted]"


@dataclass(frozen=True)
class SetupResult:
    collection_name: str
    action: str
    collection_count: int

    @property
    def created(self) -> bool:
        return self.action == "created"

    @property
    def reused(self) -> bool:
        return self.action == "reused"


def _configured_values() -> dict[str, str]:
    configured_name = (
        config.get_env_value("ASTRA_PERSONAL_COLLECTION").strip()
        or config.ASTRA_PERSONAL_COLLECTION
        or "personal_data"
    )
    return {
        "ASTRA_DB_API_ENDPOINT": config.get_env_value("ASTRA_DB_API_ENDPOINT").strip(),
        "ASTRA_DB_APPLICATION_TOKEN": config.get_env_value("ASTRA_DB_APPLICATION_TOKEN").strip(),
        "ASTRA_DB_KEYSPACE": config.get_env_value("ASTRA_DB_KEYSPACE").strip(),
        "ASTRA_PERSONAL_COLLECTION": configured_name,
    }


def _missing_required(values: dict[str, str]) -> tuple[str, ...]:
    required = (
        "ASTRA_DB_API_ENDPOINT",
        "ASTRA_DB_APPLICATION_TOKEN",
        "ASTRA_PERSONAL_COLLECTION",
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


def setup_personal_collection() -> SetupResult:
    values = _configured_values()
    collection_name = values["ASTRA_PERSONAL_COLLECTION"]
    missing = _missing_required(values)
    if missing:
        missing_names = ", ".join(missing)
        raise RuntimeError(f"Missing required environment variables: {missing_names}")

    database = _database_from_config(values)
    existing_names = database.list_collection_names()

    if collection_name in existing_names:
        # Non-destructive inspection only; descriptors may include collection options.
        database.list_collections()
        return SetupResult(
            collection_name=collection_name,
            action="reused",
            collection_count=len(existing_names),
        )

    try:
        database.create_collection(collection_name)
    except DataAPIException:
        refreshed_names = database.list_collection_names()
        if collection_name in refreshed_names:
            database.list_collections()
            return SetupResult(
                collection_name=collection_name,
                action="reused",
                collection_count=len(refreshed_names),
            )
        raise

    refreshed_names = database.list_collection_names()
    return SetupResult(
        collection_name=collection_name,
        action="created",
        collection_count=len(refreshed_names),
    )


def main() -> int:
    values = _configured_values()
    redaction_values = tuple(
        value
        for name, value in values.items()
        if name in {"ASTRA_DB_API_ENDPOINT", "ASTRA_DB_APPLICATION_TOKEN", "ASTRA_DB_KEYSPACE"}
    )

    print("Astra personal collection setup")
    print("Values are redacted; endpoint and token are never printed.")

    try:
        result = setup_personal_collection()
    except (DataAPIException, InvalidEnvironmentException, OSError, RuntimeError, ValueError) as exc:
        print("Personal collection setup failed.")
        print(f"Exception type: {type(exc).__name__}")
        print(f"Sanitized message: {sanitize_message(exc, redaction_values)}")
        print("Verify in Astra Portal:")
        print("- The database is active.")
        print("- ASTRA_DB_API_ENDPOINT matches the database API endpoint.")
        print("- ASTRA_DB_APPLICATION_TOKEN is valid and has Data API collection permissions.")
        print("- If ASTRA_DB_KEYSPACE is configured, it exists and is accessible.")
        return 1

    print(f"Collection name: {result.collection_name}")
    if result.created:
        print("Action: created normal non-vector collection")
    else:
        print("Action: reused existing collection")
    print(f"Visible collection count: {result.collection_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
