from numbers import Real
import re
from typing import Any
from urllib.parse import urlparse

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


class DatabaseError(RuntimeError):
    pass


class DatabaseConnectionError(DatabaseError):
    pass


class ProfileNotFoundError(LookupError):
    pass


class InvalidProfileError(ValueError):
    pass


class NoteNotFoundError(LookupError):
    pass


class InvalidNoteError(ValueError):
    pass


EXPECTED_APPLICATION_ERRORS = (
    ConfigurationError,
    ProfileNotFoundError,
    InvalidProfileError,
    NoteNotFoundError,
    InvalidNoteError,
)


def _sanitize_diagnostic(message: Any) -> str:
    sanitized = str(message)
    for name in getattr(config, "ALL_VARIABLES", ()):
        value = config.get_env_value(name)
        if value and len(value) >= 4:
            sanitized = sanitized.replace(value, f"<redacted:{name}>")
    sanitized = re.sub(r"AstraCS:[A-Za-z0-9._:-]+", "AstraCS:<redacted>", sanitized)
    sanitized = re.sub(r"(token|api[_ -]?key|authorization)=\S+", r"\1=<redacted>", sanitized, flags=re.I)
    return sanitized


def _wrap_database_error(action: str, error: Exception) -> DatabaseConnectionError:
    return DatabaseConnectionError(
        f"{action} failed ({type(error).__name__}): {_sanitize_diagnostic(str(error))}"
    )


def _get_required_env(name: str) -> str:
    value = config.get_env_value(name).strip()
    if not value:
        raise ConfigurationError(f"Missing required environment variable: {name}")
    return value


def _validate_https_url(name: str, value: str) -> None:
    parsed_url = urlparse(value)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise ConfigurationError(f"{name} must be a valid https URL.")


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
        if field in validated:
            if not isinstance(validated[field], str) or not validated[field].strip():
                raise InvalidProfileError(f"{field} must be a non-empty string")
            validated[field] = validated[field].strip()

    if "goals" in validated:
        goals = validated["goals"]
        if not isinstance(goals, list) or not all(isinstance(goal, str) for goal in goals):
            raise InvalidProfileError("goals must be a list of strings")
        cleaned_goals = []
        for goal in goals:
            cleaned_goal = goal.strip()
            if not cleaned_goal:
                raise InvalidProfileError("goals must be a list of non-empty strings")
            cleaned_goals.append(cleaned_goal)
        validated["goals"] = cleaned_goals

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


def _validate_account_id(account_id: Any) -> str:
    if not isinstance(account_id, str) or not account_id.strip():
        raise InvalidProfileError("account_id must be a non-empty string")
    return account_id.strip()


def _validate_user_id(user_id: Any) -> str:
    if not isinstance(user_id, str) or not user_id.strip():
        raise InvalidNoteError("user_id must be a non-empty string")
    return user_id.strip()


def _validate_note_id(note_id: Any) -> Any:
    if not note_id:
        raise InvalidNoteError("note_id is required")
    return note_id


def _validate_note_text(text: Any) -> str:
    if not isinstance(text, str) or not text.strip():
        raise InvalidNoteError("note text must be a non-empty string")
    return text.strip()


def _note_document(user_id: Any, text: Any) -> dict[str, Any]:
    validated_text = _validate_note_text(text)
    return {
        "user_id": _validate_user_id(user_id),
        "text": validated_text,
        "$vectorize": validated_text,
    }


def get_database():
    endpoint = _get_required_env("ASTRA_DB_API_ENDPOINT")
    token = _get_required_env("ASTRA_DB_APPLICATION_TOKEN")
    keyspace = config.get_env_value("ASTRA_DB_KEYSPACE").strip()
    _validate_https_url("ASTRA_DB_API_ENDPOINT", endpoint)

    try:
        client = DataAPIClient(token)
        if keyspace:
            return client.get_database(endpoint, keyspace=keyspace)
        return client.get_database(endpoint)
    except EXPECTED_APPLICATION_ERRORS:
        raise
    except Exception as error:
        raise _wrap_database_error("Connecting to Astra DB", error) from error


def get_personal_collection():
    collection_name = (
        config.get_env_value("ASTRA_PERSONAL_COLLECTION").strip()
        or config.ASTRA_PERSONAL_COLLECTION
        or "personal_data"
    )
    try:
        return get_database().get_collection(collection_name)
    except EXPECTED_APPLICATION_ERRORS:
        raise
    except Exception as error:
        raise _wrap_database_error("Opening personal profile collection", error) from error


def get_notes_collection():
    collection_name = (
        config.get_env_value("ASTRA_NOTES_COLLECTION").strip()
        or config.ASTRA_NOTES_COLLECTION
        or "notes"
    )
    try:
        return get_database().get_collection(collection_name)
    except EXPECTED_APPLICATION_ERRORS:
        raise
    except Exception as error:
        raise _wrap_database_error("Opening notes collection", error) from error


def get_accounts_collection():
    collection_name = (
        config.get_env_value("ASTRA_ACCOUNTS_COLLECTION").strip()
        or config.ASTRA_ACCOUNTS_COLLECTION
    )
    try:
        return get_database().get_collection(collection_name)
    except EXPECTED_APPLICATION_ERRORS:
        raise
    except Exception as error:
        raise _wrap_database_error("Opening accounts collection", error) from error


def list_profiles(account_id: Any) -> list[dict[str, Any]]:
    validated_account_id = _validate_account_id(account_id)
    try:
        return [
            _normalize_document(document)
            for document in get_personal_collection().find(
                {"owner_account_id": validated_account_id}
            )
        ]
    except EXPECTED_APPLICATION_ERRORS:
        raise
    except Exception as error:
        raise _wrap_database_error("Listing profiles", error) from error


def get_profile(account_id: Any, profile_id: Any) -> dict[str, Any]:
    validated_account_id = _validate_account_id(account_id)
    if not profile_id:
        raise InvalidProfileError("profile_id is required")

    try:
        document = get_personal_collection().find_one(
            {"_id": profile_id, "owner_account_id": validated_account_id}
        )
        normalized = _normalize_document(document)
        if normalized is None:
            raise ProfileNotFoundError("Profile not found.")
        return normalized
    except EXPECTED_APPLICATION_ERRORS:
        raise
    except Exception as error:
        raise _wrap_database_error("Loading profile", error) from error


def create_profile(account_id: Any, profile_data: dict[str, Any]) -> Any:
    validated_account_id = _validate_account_id(account_id)
    document = _validate_profile_fields(profile_data, partial=False)
    document["owner_account_id"] = validated_account_id
    try:
        result = get_personal_collection().insert_one(document)
        return _inserted_id(result)
    except EXPECTED_APPLICATION_ERRORS:
        raise
    except Exception as error:
        raise _wrap_database_error("Creating profile", error) from error


def update_personal_information(profile_id: Any, updates: dict[str, Any]) -> dict[str, Any]:
    if not profile_id:
        raise InvalidProfileError("profile_id is required")

    update_document = _validate_profile_fields(updates, partial=True)
    if not update_document:
        raise InvalidProfileError("updates cannot be empty")

    try:
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
    except EXPECTED_APPLICATION_ERRORS:
        raise
    except Exception as error:
        raise _wrap_database_error("Updating profile", error) from error


def add_note(user_id: Any, text: Any) -> Any:
    document = _note_document(user_id, text)
    try:
        result = get_notes_collection().insert_one(document)
        return _inserted_id(result)
    except EXPECTED_APPLICATION_ERRORS:
        raise
    except Exception as error:
        raise _wrap_database_error("Adding note", error) from error


def list_notes(user_id: Any, limit: int = 50) -> list[dict[str, Any]]:
    validated_user_id = _validate_user_id(user_id)
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        raise InvalidNoteError("limit must be a positive integer")

    try:
        documents = get_notes_collection().find(
            {"user_id": validated_user_id},
            limit=limit,
        )
        return [_normalize_document(document) for document in documents]
    except EXPECTED_APPLICATION_ERRORS:
        raise
    except Exception as error:
        raise _wrap_database_error("Listing notes", error) from error


def delete_note(user_id: Any, note_id: Any) -> bool:
    validated_user_id = _validate_user_id(user_id)
    validated_note_id = _validate_note_id(note_id)
    try:
        collection = get_notes_collection()
        note_filter = {"_id": validated_note_id, "user_id": validated_user_id}

        if collection.find_one(note_filter) is None:
            raise NoteNotFoundError(f"Note not found for this user: {validated_note_id}")

        collection.delete_one(note_filter)
        return True
    except EXPECTED_APPLICATION_ERRORS:
        raise
    except Exception as error:
        raise _wrap_database_error("Deleting note", error) from error


def update_note(user_id: Any, note_id: Any, text: Any) -> dict[str, Any]:
    validated_user_id = _validate_user_id(user_id)
    validated_note_id = _validate_note_id(note_id)
    validated_text = _validate_note_text(text)
    try:
        collection = get_notes_collection()
        note_filter = {"_id": validated_note_id, "user_id": validated_user_id}

        if collection.find_one(note_filter) is None:
            raise NoteNotFoundError(f"Note not found for this user: {validated_note_id}")

        collection.update_one(
            note_filter,
            {"$set": {"text": validated_text, "$vectorize": validated_text}},
            upsert=False,
        )

        updated = collection.find_one(note_filter)
        normalized = _normalize_document(updated)
        if normalized is None:
            raise NoteNotFoundError(f"Note not found after update: {validated_note_id}")
        return normalized
    except EXPECTED_APPLICATION_ERRORS:
        raise
    except Exception as error:
        raise _wrap_database_error("Updating note", error) from error
