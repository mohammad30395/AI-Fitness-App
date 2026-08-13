from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import ai
import config
import db
import profiles


TEST_PREFIX = "codex_test_"


@dataclass
class LayerResult:
    name: str
    passed: bool = False
    detail: str = "not run"


@dataclass
class AcceptanceContext:
    prefix: str
    profile_ids: list[Any] = field(default_factory=list)
    note_ids: list[tuple[Any, Any]] = field(default_factory=list)
    results: dict[str, LayerResult] = field(
        default_factory=lambda: {
            "Astra": LayerResult("Astra"),
            "Macro Flow": LayerResult("Macro Flow"),
            "Ask AI Math": LayerResult("Ask AI Math"),
            "Ask AI RAG": LayerResult("Ask AI RAG"),
            "Cross-profile isolation": LayerResult("Cross-profile isolation"),
            "Cleanup": LayerResult("Cleanup"),
        }
    )


def sanitize(message: Any) -> str:
    text = str(message)
    for name in getattr(config, "ALL_VARIABLES", ()):
        value = config.get_env_value(name)
        if value and len(value) >= 4:
            text = text.replace(value, f"<redacted:{name}>")
    text = re.sub(r"AstraCS:[A-Za-z0-9._:-]+", "AstraCS:<redacted>", text)
    text = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-<redacted>", text)
    return text


def mark(ctx: AcceptanceContext, layer: str, passed: bool, detail: str) -> None:
    ctx.results[layer] = LayerResult(layer, passed, detail)


def make_profile(name: str, goals: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "age": 34,
        "weight": 72.5,
        "height": 176.0,
        "gender": "unspecified",
        "activity_level": "moderate",
        "goals": goals,
    }


def require_test_profile(profile_id: Any, prefix: str) -> None:
    profile = db.get_profile(profile_id)
    name = str(profile.get("name", ""))
    if not name.startswith(prefix):
        raise RuntimeError(f"Refusing to delete non-test profile: {profile_id}")


def cleanup(ctx: AcceptanceContext) -> bool:
    cleanup_errors: list[str] = []

    for user_id, note_id in reversed(ctx.note_ids):
        try:
            if str(user_id).startswith(TEST_PREFIX) or str(user_id) in {
                str(profile_id) for profile_id in ctx.profile_ids
            }:
                db.delete_note(user_id, note_id)
            else:
                cleanup_errors.append(f"Skipped note with non-test user_id {user_id!r}")
        except db.NoteNotFoundError:
            continue
        except Exception as exc:  # noqa: BLE001 - report sanitized cleanup failures.
            cleanup_errors.append(sanitize(f"{type(exc).__name__}: {exc}"))

    for profile_id in reversed(ctx.profile_ids):
        try:
            require_test_profile(profile_id, ctx.prefix)
            db.get_personal_collection().delete_one({"_id": profile_id})
        except db.ProfileNotFoundError:
            continue
        except Exception as exc:  # noqa: BLE001 - report sanitized cleanup failures.
            cleanup_errors.append(sanitize(f"{type(exc).__name__}: {exc}"))

    if cleanup_errors:
        mark(ctx, "Cleanup", False, "; ".join(cleanup_errors))
        return False

    mark(ctx, "Cleanup", True, "temporary profiles and notes removed")
    return True


def assert_nutrition_shape(nutrition: dict[str, Any]) -> None:
    expected = {"calories", "protein", "fat", "carbs"}
    if set(nutrition) != expected:
        raise AssertionError(f"nutrition fields differ from expected set: {sorted(nutrition)}")
    for field, value in nutrition.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            raise AssertionError(f"nutrition field {field!r} is not a positive number")


def answer_mentions(answer: str, phrase: str) -> bool:
    return phrase.lower() in answer.lower()


def assert_numeric_answer(answer: str, expected: int) -> None:
    numbers = [int(match) for match in re.findall(r"-?\d+", answer)]
    if expected not in numbers:
        raise AssertionError(f"expected numeric answer {expected}, found numbers {numbers}")


def run_acceptance() -> AcceptanceContext:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    ctx = AcceptanceContext(prefix=f"{TEST_PREFIX}{timestamp}")

    profile_a_id: Any | None = None
    profile_b_id: Any | None = None

    try:
        db.get_database()
        profile_a_id = db.create_profile(
            make_profile(
                f"{ctx.prefix}_profile_a",
                ["build strength", "use private note context"],
            )
        )
        profile_b_id = db.create_profile(
            make_profile(
                f"{ctx.prefix}_profile_b",
                ["maintain mobility", "separate note context"],
            )
        )
        ctx.profile_ids.extend([profile_a_id, profile_b_id])
        profile_a_user_id = str(profile_a_id)
        profile_b_user_id = str(profile_b_id)

        unique_a = f"{ctx.prefix}_ORANGE_TIGER_7421"
        note_a_text = (
            f"My private test phrase is {unique_a}. "
            "For next week, prioritize two strength sessions and one recovery day."
        )
        note_a_id = db.add_note(profile_a_user_id, note_a_text)
        ctx.note_ids.append((profile_a_user_id, note_a_id))

        notes_a = db.list_notes(profile_a_user_id, limit=10)
        if not any(unique_a in str(note.get("text", "")) for note in notes_a):
            raise AssertionError("temporary note was not listed for profile A")
        mark(ctx, "Astra", True, "connected, temporary profiles created, note listed")

        profile_a = profiles.get_profile_by_id(profile_a_id)
        profile_context_a = profiles.build_profile_context(profile_a)
        nutrition = ai.get_macros(profile_context_a, ", ".join(profile_a["goals"]))
        assert_nutrition_shape(nutrition)
        profiles.save_profile_changes(profile_a_id, nutrition=nutrition)
        mark(ctx, "Macro Flow", True, f"parsed fields: {', '.join(sorted(nutrition))}")

        # Give server-side vectorize indexing a short bounded window before RAG retrieval.
        time.sleep(5)

        rag_question = "Based on my private test phrase note, how should I plan next week?"
        rag_answer = ai.ask_ai(
            rag_question,
            profiles.build_profile_context(profiles.get_profile_by_id(profile_a_id)),
            profile_a_user_id,
            session_id=f"{ctx.prefix}_rag_a",
        )
        rag_markers = (unique_a.lower(), "two strength", "2 strength", "recovery day")
        if not any(marker in rag_answer.lower() for marker in rag_markers):
            raise AssertionError("RAG answer was not consistent with profile A note context")
        mark(ctx, "Ask AI RAG", True, "profile A answer used its note context")

        math_answer = ai.ask_ai(
            "If my calorie target is 2400 and I ate 650 breakfast plus 780 lunch, how many calories remain?",
            profiles.build_profile_context(profiles.get_profile_by_id(profile_a_id)),
            profile_a_user_id,
            session_id=f"{ctx.prefix}_math",
        )
        assert_numeric_answer(math_answer, 970)
        mark(ctx, "Ask AI Math", True, "calculator route returned a coherent 970 answer")

        profile_b = profiles.get_profile_by_id(profile_b_id)
        isolation_answer = ai.ask_ai(
            "Based on my private test phrase note, what should I plan next week?",
            profiles.build_profile_context(profile_b),
            profile_b_user_id,
            session_id=f"{ctx.prefix}_rag_b",
        )
        forbidden_markers = (unique_a.lower(), "orange_tiger_7421", "orange", "tiger", "7421")
        if any(marker in isolation_answer.lower() for marker in forbidden_markers):
            raise AssertionError("profile B retrieved or repeated profile A's private note phrase")
        mark(ctx, "Cross-profile isolation", True, "profile B did not retrieve profile A note")

    except Exception as exc:  # noqa: BLE001 - live script reports sanitized failure.
        failed_layers = [name for name, result in ctx.results.items() if result.detail == "not run"]
        if failed_layers:
            mark(ctx, failed_layers[0], False, sanitize(f"{type(exc).__name__}: {exc}"))
        else:
            mark(ctx, "Cleanup", False, sanitize(f"{type(exc).__name__}: {exc}"))
    finally:
        cleanup(ctx)

    return ctx


def print_report(ctx: AcceptanceContext) -> None:
    print("Live acceptance results")
    print(f"test prefix: {ctx.prefix}")
    for name in (
        "Astra",
        "Macro Flow",
        "Ask AI Math",
        "Ask AI RAG",
        "Cross-profile isolation",
        "Cleanup",
    ):
        result = ctx.results[name]
        status = "PASS" if result.passed else "FAIL"
        print(f"{name}: {status} - {result.detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run disposable live acceptance checks.")
    parser.parse_args()

    ctx = run_acceptance()
    print_report(ctx)
    return 0 if all(result.passed for result in ctx.results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
