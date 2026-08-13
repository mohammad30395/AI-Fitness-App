#!/usr/bin/env python
import re
import sys
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from astrapy import DataAPIClient  # noqa: E402
from astrapy.exceptions import DataAPIException, InvalidEnvironmentException  # noqa: E402

import config  # noqa: E402


REDACTED = "[redacted]"


def _configured_astra_values() -> dict[str, str]:
    return {
        "ASTRA_DB_API_ENDPOINT": config.get_env_value("ASTRA_DB_API_ENDPOINT").strip(),
        "ASTRA_DB_APPLICATION_TOKEN": config.get_env_value("ASTRA_DB_APPLICATION_TOKEN").strip(),
        "ASTRA_DB_KEYSPACE": config.get_env_value("ASTRA_DB_KEYSPACE").strip(),
    }


def _missing_required(values: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        name
        for name in ("ASTRA_DB_API_ENDPOINT", "ASTRA_DB_APPLICATION_TOKEN")
        if not values[name]
    )


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


def run_smoke_test() -> int:
    values = _configured_astra_values()
    missing = _missing_required(values)
    redaction_values = tuple(value for value in values.values() if value)

    print("Astra DB smoke test")
    print("Values are redacted; endpoint and token are never printed.")

    if missing:
        print("Missing required variables:")
        for name in missing:
            print(f"- {name}")
        return 1

    try:
        database = _database_from_config(values)
        collection_names = database.list_collection_names()
    except (DataAPIException, InvalidEnvironmentException, OSError, ValueError) as exc:
        print("Astra DB smoke test failed.")
        print(f"Exception type: {type(exc).__name__}")
        print(f"Sanitized message: {sanitize_message(exc, redaction_values)}")
        print("Verify in Astra Portal:")
        print("- The database is active.")
        print("- ASTRA_DB_API_ENDPOINT matches the database API endpoint.")
        print("- ASTRA_DB_APPLICATION_TOKEN is valid and has Data API access.")
        print("- If you configured ASTRA_DB_KEYSPACE, it exists and is accessible.")
        return 1

    print("Astra DB smoke test passed.")
    print(f"Accessible collections inspected: {len(collection_names)}")
    if collection_names:
        print("Collection names:")
        for name in collection_names:
            print(f"- {name}")
    else:
        print("No collections are currently visible to this token/keyspace.")
    return 0


def main() -> int:
    return run_smoke_test()


if __name__ == "__main__":
    raise SystemExit(main())
