from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Mapping

from astrapy import DataAPIClient
from astrapy.exceptions import DataAPIException, InvalidEnvironmentException

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config


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
    return {
        "ASTRA_DB_API_ENDPOINT": config.get_env_value("ASTRA_DB_API_ENDPOINT").strip(),
        "ASTRA_DB_APPLICATION_TOKEN": config.get_env_value("ASTRA_DB_APPLICATION_TOKEN").strip(),
        "ASTRA_DB_KEYSPACE": config.get_env_value("ASTRA_DB_KEYSPACE").strip(),
        "ASTRA_ACCOUNTS_COLLECTION": (
            config.get_env_value("ASTRA_ACCOUNTS_COLLECTION").strip() or "accounts"
        ),
    }


def _missing_required(values: Mapping[str, str]) -> list[str]:
    required = (
        "ASTRA_DB_API_ENDPOINT",
        "ASTRA_DB_APPLICATION_TOKEN",
        "ASTRA_ACCOUNTS_COLLECTION",
    )
    return [name for name in required if not values.get(name, "").strip()]


def sanitize_message(message: str, values: Mapping[str, str]) -> str:
    sanitized = message
    for name in ("ASTRA_DB_API_ENDPOINT", "ASTRA_DB_APPLICATION_TOKEN"):
        value = values.get(name, "")
        if value:
            sanitized = sanitized.replace(value, REDACTED)
    return sanitized


def _database_from_config(values: Mapping[str, str]):
    client = DataAPIClient(values["ASTRA_DB_APPLICATION_TOKEN"])
    keyspace = values.get("ASTRA_DB_KEYSPACE", "")
    if keyspace:
        return client.get_database(values["ASTRA_DB_API_ENDPOINT"], keyspace=keyspace)
    return client.get_database(values["ASTRA_DB_API_ENDPOINT"])


def setup_accounts_collection() -> SetupResult:
    values = _configured_values()
    missing = _missing_required(values)
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    collection_name = values["ASTRA_ACCOUNTS_COLLECTION"]
    database = _database_from_config(values)
    existing_names = list(database.list_collection_names())

    if collection_name in existing_names:
        database.list_collections()
        return SetupResult(
            collection_name=collection_name,
            action="reused",
            collection_count=len(existing_names),
        )

    try:
        database.create_collection(collection_name)
    except DataAPIException:
        refreshed_names = list(database.list_collection_names())
        if collection_name in refreshed_names:
            return SetupResult(
                collection_name=collection_name,
                action="reused",
                collection_count=len(refreshed_names),
            )
        raise

    refreshed_names = list(database.list_collection_names())
    return SetupResult(
        collection_name=collection_name,
        action="created",
        collection_count=len(refreshed_names),
    )


def main() -> int:
    values = _configured_values()
    try:
        result = setup_accounts_collection()
    except (DataAPIException, InvalidEnvironmentException, ValueError, RuntimeError) as exc:
        print("Accounts collection setup failed.")
        print(f"{type(exc).__name__}: {sanitize_message(str(exc), values)}")
        return 1

    print(f"Accounts collection: {result.collection_name}")
    print(f"Action: {result.action}")
    print(f"Accessible collections: {result.collection_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
