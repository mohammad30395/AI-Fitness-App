from typing import Any, Mapping, Sequence


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
