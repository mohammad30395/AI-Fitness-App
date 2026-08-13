#!/usr/bin/env python
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
import profiles
from ai import LangflowClientError, LangflowConfigError, get_macros, run_flow
from utils import NutritionParseError


SYNTHETIC_PROFILE = {
    "_id": "synthetic-macro-test",
    "name": "Synthetic Macro User",
    "age": 30,
    "weight": 70.5,
    "height": 175,
    "gender": "unspecified",
    "activity_level": "moderate",
    "goals": ["build strength", "improve endurance"],
}

SYNTHETIC_GOALS = "Build strength while maintaining energy for 4 workouts per week."


def _sanitize_preview(text: str, limit: int = 500) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) > limit:
        return f"{collapsed[:limit]}..."
    return collapsed


def _input_summary(profile: dict[str, Any], goals: str) -> dict[str, Any]:
    return {
        "profile_id": profile.get("_id"),
        "age": profile.get("age"),
        "activity_level": profile.get("activity_level"),
        "goal_count": len(profile.get("goals", [])),
        "runtime_goals_preview": _sanitize_preview(goals, limit=120),
    }


def _macro_tweaks(goals: str) -> dict[str, dict[str, str]]:
    goals_component_id = config.get_env_value("MACRO_GOALS_COMPONENT_ID").strip()
    if not goals_component_id:
        raise LangflowConfigError("Missing required environment variable: MACRO_GOALS_COMPONENT_ID")
    return {goals_component_id: {"goals": goals}}


def _fetch_raw_macro_output(profile_context: str, goals: str) -> str:
    flow_id = config.get_env_value("MACRO_FLOW_ID").strip()
    if not flow_id:
        raise LangflowConfigError("Missing required environment variable: MACRO_FLOW_ID")
    return run_flow(flow_id, profile_context, tweaks=_macro_tweaks(goals))


def main() -> int:
    profile_context = profiles.build_profile_context(SYNTHETIC_PROFILE)

    print("Macro Flow manual integration test")
    print(f"Sanitized input summary: {_input_summary(SYNTHETIC_PROFILE, SYNTHETIC_GOALS)}")

    started = time.perf_counter()
    try:
        nutrition = get_macros(profile_context, SYNTHETIC_GOALS)
    except NutritionParseError as exc:
        duration = time.perf_counter() - started
        print(f"FAILED: Macro Flow response parsing failed after {duration:.2f}s.")
        print(f"Parser error: {exc}")
        try:
            raw_output = _fetch_raw_macro_output(profile_context, SYNTHETIC_GOALS)
        except Exception as raw_exc:  # noqa: BLE001 - diagnostic path must not mask original failure.
            print(f"Raw output preview unavailable: {type(raw_exc).__name__}: {raw_exc}")
        else:
            print(f"Raw sanitized output preview: {_sanitize_preview(raw_output)}")
        print("Fix the Langflow Macro Flow prompt/model so it returns JSON only, then rerun this script.")
        return 1
    except (LangflowClientError, requests.RequestException, ValueError) as exc:
        duration = time.perf_counter() - started
        print(f"FAILED: Macro Flow call failed after {duration:.2f}s.")
        print(f"Error type: {type(exc).__name__}")
        print(f"Sanitized error: {exc}")
        return 1

    duration = time.perf_counter() - started
    required = {"calories", "protein", "fat", "carbs"}
    if set(nutrition) != required:
        print(f"FAILED: Parsed nutrition dict has unexpected keys: {sorted(nutrition)}")
        return 1

    print(f"Parsed nutrition dict: {nutrition}")
    print(f"Request duration: {duration:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
