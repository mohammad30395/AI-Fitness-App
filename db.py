from numbers import Real
from typing import Any

from astrapy import DataAPIClient

import config


PROFILE_FIELDS = {
    "name",
    "age",
    "weight",
    "height",
    "gender",
    "activity_level",
    "goals",
    "nutrition",
}

REQUIRED_PROFILE_FIELDS = {
    "name",
    "age",
    "weight",
    "height",
    "gender",
    "activity_level",
    "goals",
}

NUTRITION_FIELDS = {"calories", "protein", "fat", "carbs"}


class ConfigurationError(RuntimeError):
    pass


class ProfileNotFoundError(LookupError):
    pass


class InvalidProfileError(ValueError):
    pass


def _get_required_env(name: str) -> str:
    value = config.get_env_value(name).strip()
    if not value:
        raise ConfigurationError(f"Missing required environment variable: {name}")
    return value


def _positive_number(value: Any) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and value > 0


def _validate_nutrition(nutrition: Any) -> dict[str, Any]:
    if not isinstance(nutrition, dict):
        raise InvalidProfileError("nutrition must be a dictionary")

    unknown_fields = set(nutrition) - NUTRITION_FIELDS
    if unknown_fields:
        unknown = ", ".join(sorted(unknown_fields))
        raise InvalidProfileError(f"nutrition contains unsupported fields: {unknown}")

    validated = dict(nutrition)
    for field in NUTRITION_FIELDS & set(validated):
        if not _positive_number(validated[field]):
            raise InvalidProfileError(f"nutrition.{field} must be a positive number")
    return validated


def _validate_profile_fields(data: dict[str, Any], *, partial: bool) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise InvalidProfileError("profile data must be a dictionary")

    if "_id" in data:
        raise InvalidProfileError("_id cannot be created or updated by the application")

    unknown_fields = set(data) - PROFILE_FIELDS
    if unknown_fields:
        unknown = ", ".join(sorted(unknown_fields))
        raise InvalidProfileError(f"profile contains unsupported fields: {unknown}")

    if not partial:
        missing = REQUIRED_PROFILE_FIELDS - set(data)
        if missing:
            missing_names = ", ".join(sorted(missing))
            raise InvalidProfileError(f"profile is missing required fields: {missing_names}")

    validated = dict(data)

    if "name" in validated:
        if not isinstance(validated["name"], str) or not validated["name"].strip():
            raise InvalidProfileError("name must be a non-empty string")
        validated["name"] = validated["name"].strip()

    if "age" in validated:
        if (
            not isinstance(validated["age"], int)
            or isinstance(validated["age"], bool)
            or validated["age"] <= 0
        ):
            raise InvalidProfileError("age must be a positive integer")

    for field in ("weight", "height"):
        if field in validated and not _positive_number(validated[field]):
            raise InvalidProfileError(f"{field} must be a positive number")

    for field in ("gender", "activity_level"):
        if field in validated and not isinstance(validated[field], str):
            raise InvalidProfileError(f"{field} must be a string")

    if "goals" in validated:
        goals = validated["goals"]
        if not isinstance(goals, list) or not all(isinstance(goal, str) for goal in goals):
            raise InvalidProfileError("goals must be a list of strings")

    if "nutrition" in validated and validated["nutrition"] is not None:
        validated["nutrition"] = _validate_nutrition(validated["nutrition"])

    return validated


def _normalize_document(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    return dict(document)


def _inserted_id(insert_result: Any) -> Any:
    if hasattr(insert_result, "inserted_id"):
        return insert_result.inserted_id
    if isinstance(insert_result, dict):
        return insert_result.get("inserted_id") or insert_result.get("insertedId")
    return insert_result


def get_database():
    endpoint = _get_required_env("ASTRA_DB_API_ENDPOINT")
    token = _get_required_env("ASTRA_DB_APPLICATION_TOKEN")
    keyspace = config.get_env_value("ASTRA_DB_KEYSPACE").strip()

    client = DataAPIClient(token)
    if keyspace:
        return client.get_database(endpoint, keyspace=keyspace)
    return client.get_database(endpoint)


def get_personal_collection():
    collection_name = (
        config.get_env_value("ASTRA_PERSONAL_COLLECTION").strip()
        or config.ASTRA_PERSONAL_COLLECTION
        or "personal_data"
    )
    return get_database().get_collection(collection_name)


def list_profiles() -> list[dict[str, Any]]:
    return [_normalize_document(document) for document in get_personal_collection().find({})]


def get_profile(profile_id: Any) -> dict[str, Any]:
    if not profile_id:
        raise InvalidProfileError("profile_id is required")

    document = get_personal_collection().find_one({"_id": profile_id})
    normalized = _normalize_document(document)
    if normalized is None:
        raise ProfileNotFoundError(f"Profile not found: {profile_id}")
    return normalized


def create_profile(profile_data: dict[str, Any]) -> Any:
    document = _validate_profile_fields(profile_data, partial=False)
    result = get_personal_collection().insert_one(document)
    return _inserted_id(result)


def update_personal_information(profile_id: Any, updates: dict[str, Any]) -> dict[str, Any]:
    if not profile_id:
        raise InvalidProfileError("profile_id is required")

    update_document = _validate_profile_fields(updates, partial=True)
    if not update_document:
        raise InvalidProfileError("updates cannot be empty")

    collection = get_personal_collection()
    existing = collection.find_one({"_id": profile_id})
    if existing is None:
        raise ProfileNotFoundError(f"Profile not found: {profile_id}")

    collection.update_one({"_id": profile_id}, {"$set": update_document}, upsert=False)

    updated = collection.find_one({"_id": profile_id})
    normalized = _normalize_document(updated)
    if normalized is None:
        raise ProfileNotFoundError(f"Profile not found after update: {profile_id}")
    return normalized
