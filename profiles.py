from typing import Any

import db
from utils import dict_to_string


class ProfileDataError(ValueError):
    """Raised when profile data cannot be normalized safely."""


PROFILE_FIELD_ORDER = (
    "_id",
    "name",
    "age",
    "weight",
    "height",
    "gender",
    "activity_level",
    "goals",
    "nutrition",
)

NUTRITION_FIELD_ORDER = ("calories", "protein", "fat", "carbs")


def normalize_profile(profile: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(profile, dict):
        raise ProfileDataError("Profile data must be a dictionary.")

    normalized: dict[str, Any] = {}
    for field in PROFILE_FIELD_ORDER:
        if field in profile:
            normalized[field] = profile[field]

    normalized["goals"] = _normalize_goals(normalized.get("goals", []))

    nutrition = normalized.get("nutrition")
    if isinstance(nutrition, dict) and nutrition:
        normalized["nutrition"] = {
            field: nutrition[field]
            for field in NUTRITION_FIELD_ORDER
            if field in nutrition
        }
    else:
        normalized.pop("nutrition", None)

    return normalized


def get_all_profiles(account_id: Any) -> list[dict[str, Any]]:
    return [normalize_profile(profile) for profile in db.list_profiles(account_id)]


def get_profile_by_id(account_id: Any, profile_id: Any) -> dict[str, Any]:
    return normalize_profile(db.get_profile(account_id, profile_id))


def create_new_profile(
    *,
    account_id: Any,
    name: str,
    age: int,
    weight: float,
    height: float,
    gender: str,
    activity_level: str,
    goals: list[str],
    nutrition: dict[str, Any] | None = None,
) -> Any:
    profile_data: dict[str, Any] = {
        "name": name,
        "age": age,
        "weight": weight,
        "height": height,
        "gender": gender,
        "activity_level": activity_level,
        "goals": _normalize_goals(goals),
    }
    if nutrition:
        profile_data["nutrition"] = _normalize_nutrition(nutrition)
    return db.create_profile(account_id, profile_data)


def save_profile_changes(account_id: Any, profile_id: Any, **updates: Any) -> dict[str, Any]:
    cleaned_updates = _clean_profile_updates(updates)
    return normalize_profile(db.update_personal_information(account_id, profile_id, cleaned_updates))


def build_profile_context(profile: dict[str, Any]) -> str:
    normalized = normalize_profile(profile)
    context_data: dict[str, Any] = {
        "profile_id": normalized.get("_id", "not set"),
        "name": normalized.get("name", "not set"),
        "age": normalized.get("age", "not set"),
        "weight": normalized.get("weight", "not set"),
        "height": normalized.get("height", "not set"),
        "gender": normalized.get("gender", "not set"),
        "activity_level": normalized.get("activity_level", "not set"),
        "goals": normalized.get("goals", []),
    }

    nutrition = normalized.get("nutrition")
    if nutrition:
        context_data["nutrition"] = {
            field: nutrition.get(field, "not set")
            for field in NUTRITION_FIELD_ORDER
        }
    else:
        context_data["nutrition"] = "not generated yet"

    return dict_to_string(
        context_data,
        key_order=(
            "profile_id",
            "name",
            "age",
            "weight",
            "height",
            "gender",
            "activity_level",
            "goals",
            "nutrition",
        ),
        nested_key_orders={"nutrition": NUTRITION_FIELD_ORDER},
    )


def _normalize_goals(goals: Any) -> list[str]:
    if goals is None:
        return []
    if not isinstance(goals, list):
        cleaned_goal = str(goals).strip()
        return [cleaned_goal] if cleaned_goal else []
    return [str(goal).strip() for goal in goals if str(goal).strip()]


def _normalize_nutrition(nutrition: dict[str, Any]) -> dict[str, Any]:
    return {
        field: nutrition[field]
        for field in NUTRITION_FIELD_ORDER
        if field in nutrition
    }


def _clean_profile_updates(updates: dict[str, Any]) -> dict[str, Any]:
    cleaned = {key: value for key, value in updates.items() if value is not None}
    if "goals" in cleaned:
        cleaned["goals"] = _normalize_goals(cleaned["goals"])
    if "nutrition" in cleaned and isinstance(cleaned["nutrition"], dict):
        cleaned["nutrition"] = _normalize_nutrition(cleaned["nutrition"])
    return cleaned
