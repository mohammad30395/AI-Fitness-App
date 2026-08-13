#!/usr/bin/env python
import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import db  # noqa: E402


TEST_NOTE_TEXT = "[SMOKE TEST NOTE - SAFE TO DELETE] Astra notes round-trip check"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manually smoke-test notes insert/read/delete for one profile."
    )
    parser.add_argument(
        "--user-id",
        default=os.getenv("SMOKE_PROFILE_ID", ""),
        help="Profile/user id to attach the test note to. Defaults to SMOKE_PROFILE_ID.",
    )
    parser.add_argument(
        "--confirm-write-delete",
        action="store_true",
        help="Required to insert and delete the marked smoke-test note.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    user_id = args.user_id.strip()

    if not user_id:
        print("Missing user id. Pass --user-id or set SMOKE_PROFILE_ID.")
        return 1

    print("Notes smoke test")
    print(f"Target user_id: {user_id}")
    print(f"Test note text: {TEST_NOTE_TEXT}")

    if not args.confirm_write_delete:
        print("Dry run only. Re-run with --confirm-write-delete to insert and delete this test note.")
        return 0

    note_id = db.add_note(user_id, TEST_NOTE_TEXT)
    print(f"Inserted test note id: {note_id}")

    matching_notes = [
        note
        for note in db.list_notes(user_id, limit=25)
        if note.get("_id") == note_id or note.get("text") == TEST_NOTE_TEXT
    ]
    if not matching_notes:
        print("Inserted note was not found during read-back. Stopping before delete.")
        return 1

    print("Read-back found the inserted test note.")
    db.delete_note(user_id, note_id)
    print("Deleted the inserted test note.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
