import json
import math
import re
from typing import Any, Mapping, Sequence


NUTRITION_FIELDS = ("calories", "protein", "fat", "carbs")
NUTRITION_LIMITS = {
    "calories": (500, 10000),
    "protein": (1, 500),
    "fat": (1, 400),
    "carbs": (1, 1000),
}


class NutritionParseError(ValueError):
    """Raised when model output cannot be parsed as valid macro targets."""


def dict_to_string(
    data: Mapping[str, Any],
    *,
    key_order: Sequence[str] | None = None,
    nested_key_orders: Mapping[str, Sequence[str]] | None = None,
    indent: int = 0,
) -> str:
    """Serialize nested dictionaries deterministically for prompt context.

    This is a project implementation choice, not copied tutorial code.
    """
    ordered_keys = list(key_order or [])
    ordered_keys.extend(sorted(key for key in data if key not in ordered_keys))

    lines: list[str] = []
    prefix = " " * indent
    for key in ordered_keys:
        if key not in data:
            continue
        value = data[key]
        label = str(key).replace("_", " ").capitalize()
        if isinstance(value, Mapping):
            lines.append(f"{prefix}{label}:")
            nested_order = (nested_key_orders or {}).get(key)
            lines.append(
                dict_to_string(
                    value,
                    key_order=nested_order,
                    nested_key_orders=nested_key_orders,
                    indent=indent + 2,
                )
            )
        elif isinstance(value, list):
            serialized = ", ".join(str(item) for item in value) if value else "none"
            lines.append(f"{prefix}{label}: {serialized}")
        elif value is None or value == "":
            lines.append(f"{prefix}{label}: not set")
        else:
            lines.append(f"{prefix}{label}: {value}")
    return "\n".join(lines)


def _extract_json_text(text: str) -> str:
    stripped = text.strip()
    fence_match = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    return stripped


def _normalize_nutrition_number(field: str, value: Any) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NutritionParseError(f"Nutrition field '{field}' must be a number.")

    number = float(value)
    if not math.isfinite(number):
        raise NutritionParseError(f"Nutrition field '{field}' must be finite.")

    low, high = NUTRITION_LIMITS[field]
    if number <= 0:
        raise NutritionParseError(f"Nutrition field '{field}' must be positive.")
    if number < low or number > high:
        raise NutritionParseError(
            f"Nutrition field '{field}' is outside broad UI sanity limits."
        )

    return int(number) if number.is_integer() else number


def parse_nutrition_json(text: str) -> dict[str, int | float]:
    """Parse approximate macro JSON from Langflow output.

    This validates broad UI sanity only; it is not medical validation.
    """
    if not isinstance(text, str) or not text.strip():
        raise NutritionParseError("Nutrition output must be a non-empty string.")

    json_text = _extract_json_text(text)
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise NutritionParseError("Nutrition output is not valid JSON.") from exc

    if not isinstance(parsed, Mapping):
        raise NutritionParseError("Nutrition output must be a JSON object.")

    keys = set(parsed)
    expected = set(NUTRITION_FIELDS)
    missing = sorted(expected - keys)
    extra = sorted(keys - expected)
    if missing:
        raise NutritionParseError(f"Nutrition output is missing fields: {', '.join(missing)}.")
    if extra:
        raise NutritionParseError(f"Nutrition output has unexpected fields: {', '.join(extra)}.")

    return {
        field: _normalize_nutrition_number(field, parsed[field])
        for field in NUTRITION_FIELDS
    }
