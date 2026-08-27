#!/usr/bin/env python
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import db  # noqa: E402


MANIFEST_DIR = PROJECT_ROOT / "migration_manifests"


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class TargetAccount:
    account_id: str
    username: str | None


@dataclass(frozen=True)
class LegacyProfile:
    profile_id: Any
    previous_owner_state: str
    previous_owner_value: Any


@dataclass(frozen=True)
class LegacyNote:
    note_id: Any
    user_id: Any
    previous_owner_state: str
    previous_owner_value: Any


@dataclass(frozen=True)
class MigrationPlan:
    target_account: TargetAccount | None
    eligible_profiles: tuple[LegacyProfile, ...]
    eligible_notes: tuple[LegacyNote, ...]
    orphaned_notes: tuple[LegacyNote, ...]
    notes_linked_to_owned_profiles: tuple[LegacyNote, ...]
    invalid_notes: tuple[LegacyNote, ...]
    owned_profile_ids: tuple[Any, ...]
    owned_note_ids: tuple[Any, ...]
    profile_collection: Any
    notes_collection: Any

    @property
    def target_found(self) -> bool:
        return self.target_account is not None

    @property
    def ambiguous_notes(self) -> tuple[LegacyNote, ...]:
        return self.orphaned_notes + self.notes_linked_to_owned_profiles + self.invalid_notes

    @property
    def can_apply(self) -> bool:
        return self.target_found and not self.ambiguous_notes


@dataclass(frozen=True)
class MigrationResult:
    mode: str
    profile_writes: int
    note_writes: int
    manifest_path: Path | None = None

    @property
    def writes_performed(self) -> int:
        return self.profile_writes + self.note_writes


def _validate_account_id(account_id: Any) -> str:
    if not isinstance(account_id, str) or not account_id.strip():
        raise MigrationError("account_id must be a non-empty string")
    return account_id.strip()


def _owner_state(document: dict[str, Any]) -> tuple[str, Any]:
    if "owner_account_id" not in document:
        return "missing", None
    value = document.get("owner_account_id")
    if value is None:
        return "null", None
    if isinstance(value, str) and not value.strip():
        return "blank", value
    return "owned", value


def _is_legacy(document: dict[str, Any]) -> bool:
    state, _value = _owner_state(document)
    return state in {"missing", "null", "blank"}


def _valid_id(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _all_documents(collection: Any) -> list[dict[str, Any]]:
    return [dict(document) for document in collection.find({})]


def _target_account(accounts_collection: Any, account_id: str) -> TargetAccount | None:
    account = accounts_collection.find_one({"account_id": account_id})
    if not account:
        return None
    username = account.get("username") if isinstance(account, dict) else None
    return TargetAccount(
        account_id=account_id,
        username=username if isinstance(username, str) and username.strip() else None,
    )


def build_migration_plan(
    account_id: Any,
    *,
    accounts_collection: Any | None = None,
    profile_collection: Any | None = None,
    notes_collection: Any | None = None,
) -> MigrationPlan:
    target_account_id = _validate_account_id(account_id)
    accounts = accounts_collection or db.get_accounts_collection()
    profiles = profile_collection or db.get_personal_collection()
    notes = notes_collection or db.get_notes_collection()

    target = _target_account(accounts, target_account_id)
    if target is None:
        return MigrationPlan(
            target_account=None,
            eligible_profiles=(),
            eligible_notes=(),
            orphaned_notes=(),
            notes_linked_to_owned_profiles=(),
            invalid_notes=(),
            owned_profile_ids=(),
            owned_note_ids=(),
            profile_collection=profiles,
            notes_collection=notes,
        )

    eligible_profiles: list[LegacyProfile] = []
    eligible_profile_ids = set()
    owned_profile_ids: list[Any] = []

    for profile in _all_documents(profiles):
        profile_id = profile.get("_id")
        state, value = _owner_state(profile)
        if _is_legacy(profile) and _valid_id(profile_id):
            eligible_profiles.append(LegacyProfile(profile_id, state, value))
            eligible_profile_ids.add(profile_id)
        elif state == "owned" and _valid_id(profile_id):
            owned_profile_ids.append(profile_id)

    eligible_notes: list[LegacyNote] = []
    orphaned_notes: list[LegacyNote] = []
    notes_linked_to_owned_profiles: list[LegacyNote] = []
    invalid_notes: list[LegacyNote] = []
    owned_note_ids: list[Any] = []

    for note in _all_documents(notes):
        note_id = note.get("_id")
        user_id = note.get("user_id")
        state, value = _owner_state(note)

        if state == "owned":
            if _valid_id(note_id):
                owned_note_ids.append(note_id)
            continue

        legacy_note = LegacyNote(note_id, user_id, state, value)
        if not _valid_id(note_id) or not _valid_id(user_id):
            invalid_notes.append(legacy_note)
        elif user_id in eligible_profile_ids:
            eligible_notes.append(legacy_note)
        elif user_id in owned_profile_ids:
            notes_linked_to_owned_profiles.append(legacy_note)
        else:
            orphaned_notes.append(legacy_note)

    return MigrationPlan(
        target_account=target,
        eligible_profiles=tuple(eligible_profiles),
        eligible_notes=tuple(eligible_notes),
        orphaned_notes=tuple(orphaned_notes),
        notes_linked_to_owned_profiles=tuple(notes_linked_to_owned_profiles),
        invalid_notes=tuple(invalid_notes),
        owned_profile_ids=tuple(owned_profile_ids),
        owned_note_ids=tuple(owned_note_ids),
        profile_collection=profiles,
        notes_collection=notes,
    )


def _owner_filter(record_id: Any, previous_owner_state: str, previous_owner_value: Any) -> dict[str, Any]:
    filter_doc = {"_id": record_id}
    if previous_owner_state == "missing":
        filter_doc["owner_account_id"] = {"$exists": False}
    elif previous_owner_state == "null":
        filter_doc["owner_account_id"] = None
    elif previous_owner_state == "blank":
        filter_doc["owner_account_id"] = previous_owner_value
    else:
        raise MigrationError("Cannot update a record that was not planned as legacy.")
    return filter_doc


def _confirmed_update_count(update_result: Any) -> int | None:
    modified_count = getattr(update_result, "modified_count", None)
    if isinstance(modified_count, int):
        return modified_count

    update_info = getattr(update_result, "update_info", None)
    if isinstance(update_info, dict):
        for key in ("n", "modifiedCount", "modified_count"):
            value = update_info.get(key)
            if isinstance(value, int):
                return value

    if isinstance(update_result, dict):
        for key in ("modifiedCount", "modified_count", "n"):
            value = update_result.get(key)
            if isinstance(value, int):
                return value

    return None


def _update_legacy_owner(
    collection: Any,
    record_id: Any,
    previous_owner_state: str,
    previous_owner_value: Any,
    target_account_id: str,
) -> int:
    update_result = collection.update_one(
        _owner_filter(record_id, previous_owner_state, previous_owner_value),
        {"$set": {"owner_account_id": target_account_id}},
        upsert=False,
    )
    confirmed_count = _confirmed_update_count(update_result)
    if confirmed_count is not None and confirmed_count != 1:
        raise MigrationError(f"Conditional ownership update did not modify {record_id}.")
    return confirmed_count if confirmed_count is not None else 1


def build_manifest(
    plan: MigrationPlan,
    *,
    mode: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    if plan.target_account is None:
        raise MigrationError("Cannot build a manifest without a target account.")

    timestamp = generated_at or datetime.now(timezone.utc).isoformat()
    return {
        "migration_timestamp": timestamp,
        "mode": mode,
        "target_account_id": plan.target_account.account_id,
        "target_username": plan.target_account.username,
        "counts": {
            "eligible_profiles": len(plan.eligible_profiles),
            "eligible_notes": len(plan.eligible_notes),
            "orphaned_notes": len(plan.orphaned_notes),
            "notes_linked_to_owned_profiles": len(plan.notes_linked_to_owned_profiles),
            "invalid_notes": len(plan.invalid_notes),
        },
        "eligible_profiles": [
            {
                "profile_id": profile.profile_id,
                "previous_owner_account_id_state": profile.previous_owner_state,
                "previous_owner_account_id": profile.previous_owner_value,
            }
            for profile in plan.eligible_profiles
        ],
        "eligible_notes": [
            {
                "note_id": note.note_id,
                "user_id": note.user_id,
                "previous_owner_account_id_state": note.previous_owner_state,
                "previous_owner_account_id": note.previous_owner_value,
            }
            for note in plan.eligible_notes
        ],
    }


def write_manifest(plan: MigrationPlan, *, mode: str, manifest_dir: Path = MANIFEST_DIR) -> Path:
    manifest = build_manifest(plan, mode=mode)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = manifest_dir / f"legacy_ownership_{timestamp}.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return path


def dry_run(plan: MigrationPlan) -> MigrationResult:
    return MigrationResult(mode="DRY-RUN", profile_writes=0, note_writes=0)


def apply_migration(plan: MigrationPlan, *, manifest_dir: Path = MANIFEST_DIR) -> MigrationResult:
    if not plan.target_found:
        raise MigrationError("Target account was not found.")
    if plan.ambiguous_notes:
        raise MigrationError("Ambiguous legacy notes must be reviewed before apply.")

    manifest_path = write_manifest(plan, mode="APPLY", manifest_dir=manifest_dir)
    target_account_id = plan.target_account.account_id
    profile_writes = 0
    note_writes = 0

    # Parent profiles are assigned before child notes so note ownership never points
    # at profiles that remain intentionally legacy after a partial failure.
    for profile in plan.eligible_profiles:
        profile_writes += _update_legacy_owner(
            plan.profile_collection,
            profile.profile_id,
            profile.previous_owner_state,
            profile.previous_owner_value,
            target_account_id,
        )

    for note in plan.eligible_notes:
        note_writes += _update_legacy_owner(
            plan.notes_collection,
            note.note_id,
            note.previous_owner_state,
            note.previous_owner_value,
            target_account_id,
        )

    return MigrationResult(
        mode="APPLY",
        profile_writes=profile_writes,
        note_writes=note_writes,
        manifest_path=manifest_path,
    )


def _print_plan(plan: MigrationPlan, result: MigrationResult) -> None:
    print(f"MODE: {result.mode}")
    if plan.target_account is None:
        print("TARGET ACCOUNT: NOT FOUND")
    else:
        username = plan.target_account.username or "<unknown>"
        print(f"TARGET ACCOUNT: {plan.target_account.account_id} ({username})")
    print(f"ELIGIBLE PROFILES: {len(plan.eligible_profiles)}")
    print(f"ELIGIBLE NOTES: {len(plan.eligible_notes)}")
    print(f"ORPHANED NOTES: {len(plan.orphaned_notes)}")
    print(f"NOTES LINKED TO OWNED PROFILES: {len(plan.notes_linked_to_owned_profiles)}")
    print(f"INVALID NOTES: {len(plan.invalid_notes)}")
    print(f"WRITES PERFORMED: {result.writes_performed}")
    if result.manifest_path is not None:
        print(f"MANIFEST: {result.manifest_path}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migrate legacy unowned profiles and notes to a target account."
    )
    parser.add_argument("--account-id", required=True, help="Target account_id for ownership.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform writes. Omit this flag for the default dry-run mode.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        plan = build_migration_plan(args.account_id)
        if not plan.target_found:
            _print_plan(plan, dry_run(plan))
            return 1
        if args.apply:
            result = apply_migration(plan)
        else:
            result = dry_run(plan)
        _print_plan(plan, result)
        return 0
    except MigrationError as error:
        print(f"Migration stopped: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
