import json

import pytest

from scripts import migrate_legacy_ownership as migration


TARGET_ACCOUNT_ID = "5ab329fa-8ddf-4e2e-993a-a50355ddd25d"


class FakeCollection:
    def __init__(self, documents):
        self.documents = [dict(document) for document in documents]
        self.update_calls = []

    def find(self, filter_doc):
        assert filter_doc == {}
        return [dict(document) for document in self.documents]

    def find_one(self, filter_doc):
        for document in self.documents:
            if all(document.get(key) == value for key, value in filter_doc.items()):
                return dict(document)
        return None

    def update_one(self, filter_doc, update_doc, **kwargs):
        self.update_calls.append((dict(filter_doc), dict(update_doc), dict(kwargs)))
        for document in self.documents:
            if _matches(document, filter_doc):
                document.update(update_doc.get("$set", {}))
                return {"modifiedCount": 1}
        return {"modifiedCount": 0}


def _matches(document, filter_doc):
    for key, expected in filter_doc.items():
        if isinstance(expected, dict) and "$exists" in expected:
            if (key in document) is not expected["$exists"]:
                return False
            continue
        if document.get(key) != expected:
            return False
    return True


def _collections(
    *,
    accounts=None,
    profiles=None,
    notes=None,
):
    return (
        FakeCollection(
            accounts
            if accounts is not None
            else [
                {
                    "_id": "tahmid2016",
                    "username": "tahmid2016",
                    "account_id": TARGET_ACCOUNT_ID,
                    "password_hash": "must-not-leak",
                }
            ]
        ),
        FakeCollection(
            profiles
            if profiles is not None
            else [
                {"_id": f"profile-{number}", "name": f"Profile {number}"}
                for number in range(5)
            ]
        ),
        FakeCollection(
            notes
            if notes is not None
            else [
                {
                    "_id": f"note-{number}",
                    "user_id": f"profile-{number}",
                    "text": f"private note {number}",
                    "$vectorize": f"private note {number}",
                    "$vector": [0.1],
                }
                for number in range(5)
            ]
        ),
    )


def _plan(accounts=None, profiles=None, notes=None, account_id=TARGET_ACCOUNT_ID):
    account_collection, profile_collection, notes_collection = _collections(
        accounts=accounts,
        profiles=profiles,
        notes=notes,
    )
    return migration.build_migration_plan(
        account_id,
        accounts_collection=account_collection,
        profile_collection=profile_collection,
        notes_collection=notes_collection,
    )


def test_dry_run_performs_zero_writes_with_eligible_profiles_and_notes():
    plan = _plan()
    result = migration.dry_run(plan)

    assert len(plan.eligible_profiles) == 5
    assert len(plan.eligible_notes) == 5
    assert result.mode == "DRY-RUN"
    assert result.writes_performed == 0
    assert plan.profile_collection.update_calls == []
    assert plan.notes_collection.update_calls == []


def test_target_account_required_for_planning_and_zero_writes():
    plan = _plan(accounts=[], account_id="missing-account")
    result = migration.dry_run(plan)

    assert plan.target_account is None
    assert plan.eligible_profiles == ()
    assert plan.eligible_notes == ()
    assert result.writes_performed == 0
    assert plan.profile_collection.update_calls == []
    assert plan.notes_collection.update_calls == []


def test_already_owned_profile_excluded():
    plan = _plan(
        profiles=[
            {"_id": "profile-legacy", "name": "Legacy"},
            {"_id": "profile-owned", "owner_account_id": "other-account"},
        ],
        notes=[],
    )

    assert [profile.profile_id for profile in plan.eligible_profiles] == ["profile-legacy"]
    assert plan.owned_profile_ids == ("profile-owned",)


def test_already_owned_note_excluded():
    plan = _plan(
        profiles=[{"_id": "profile-legacy"}],
        notes=[
            {"_id": "note-legacy", "user_id": "profile-legacy"},
            {
                "_id": "note-owned",
                "user_id": "profile-legacy",
                "owner_account_id": "other-account",
            },
        ],
    )

    assert [note.note_id for note in plan.eligible_notes] == ["note-legacy"]
    assert plan.owned_note_ids == ("note-owned",)


def test_orphan_note_excluded_and_flagged():
    plan = _plan(profiles=[{"_id": "profile-legacy"}], notes=[{"_id": "note-1", "user_id": "missing"}])

    assert plan.eligible_notes == ()
    assert [note.note_id for note in plan.orphaned_notes] == ["note-1"]
    assert not plan.can_apply


def test_note_linked_to_owned_profile_excluded():
    plan = _plan(
        profiles=[{"_id": "profile-owned", "owner_account_id": "other-account"}],
        notes=[{"_id": "note-1", "user_id": "profile-owned"}],
    )

    assert plan.eligible_notes == ()
    assert [note.note_id for note in plan.notes_linked_to_owned_profiles] == ["note-1"]
    assert not plan.can_apply


def test_apply_update_payload_changes_exactly_owner_account_id(tmp_path):
    plan = _plan(profiles=[{"_id": "profile-1"}], notes=[{"_id": "note-1", "user_id": "profile-1"}])

    result = migration.apply_migration(plan, manifest_dir=tmp_path)

    assert result.writes_performed == 2
    for _filter_doc, update_doc, kwargs in (
        plan.profile_collection.update_calls + plan.notes_collection.update_calls
    ):
        assert update_doc == {"$set": {"owner_account_id": TARGET_ACCOUNT_ID}}
        assert kwargs == {"upsert": False}


def test_conditional_update_filter_protects_unowned_state(tmp_path):
    plan = _plan(
        profiles=[
            {"_id": "missing-owner"},
            {"_id": "null-owner", "owner_account_id": None},
            {"_id": "blank-owner", "owner_account_id": "  "},
        ],
        notes=[],
    )

    migration.apply_migration(plan, manifest_dir=tmp_path)

    assert [call[0] for call in plan.profile_collection.update_calls] == [
        {"_id": "missing-owner", "owner_account_id": {"$exists": False}},
        {"_id": "null-owner", "owner_account_id": None},
        {"_id": "blank-owner", "owner_account_id": "  "},
    ]


def test_apply_reports_conditional_update_race(tmp_path):
    plan = _plan(profiles=[{"_id": "profile-1"}], notes=[])
    plan.profile_collection.documents[0]["owner_account_id"] = "race-winner"

    with pytest.raises(migration.MigrationError, match="Conditional ownership update"):
        migration.apply_migration(plan, manifest_dir=tmp_path)


def test_idempotency_after_successful_migration_plans_zero_writes(tmp_path):
    account_collection, profile_collection, notes_collection = _collections(
        profiles=[{"_id": "profile-1"}],
        notes=[{"_id": "note-1", "user_id": "profile-1"}],
    )
    first = migration.build_migration_plan(
        TARGET_ACCOUNT_ID,
        accounts_collection=account_collection,
        profile_collection=profile_collection,
        notes_collection=notes_collection,
    )

    migration.apply_migration(first, manifest_dir=tmp_path)
    second = migration.build_migration_plan(
        TARGET_ACCOUNT_ID,
        accounts_collection=account_collection,
        profile_collection=profile_collection,
        notes_collection=notes_collection,
    )

    assert second.eligible_profiles == ()
    assert second.eligible_notes == ()


def test_manifest_omits_note_text_password_hash_and_secret_words():
    plan = _plan()

    manifest = migration.build_manifest(
        plan,
        mode="DRY-RUN",
        generated_at="2026-08-27T00:00:00+00:00",
    )
    manifest_text = json.dumps(manifest)

    assert "private note" not in manifest_text
    assert "password" not in manifest_text
    assert "password_hash" not in manifest_text
    assert "token" not in manifest_text
    assert "eligible_profiles" in manifest
    assert "eligible_notes" in manifest


def test_cli_without_apply_is_dry_run(monkeypatch, capsys):
    plan = _plan()
    monkeypatch.setattr(migration, "build_migration_plan", lambda account_id: plan)

    exit_code = migration.main(["--account-id", TARGET_ACCOUNT_ID])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "MODE: DRY-RUN" in output
    assert "WRITES PERFORMED: 0" in output
    assert plan.profile_collection.update_calls == []
    assert plan.notes_collection.update_calls == []


def test_invalid_missing_account_id_fails_safely_with_zero_writes():
    with pytest.raises(migration.MigrationError, match="account_id must be a non-empty string"):
        _plan(account_id="   ")
