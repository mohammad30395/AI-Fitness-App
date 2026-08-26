# Authentication Plan

Audit date: 2026-08-26 15:03:07 +06

## Scope

This document plans a real username/password authentication extension for the existing Personal Fitness AI Assistant. It does not implement authentication, create collections, migrate data, alter Langflow flows, or change current runtime behavior.

The current architecture remains:

```text
Streamlit app -> Python service layer -> Astra DB
Streamlit app -> ai.py -> Langflow -> OpenRouter
Langflow Ask AI V2 -> Astra DB vector search for notes
```

## Current Vulnerability

The application currently provides profile separation, not real account authentication or authorization.

At the moment, a profile document ID is treated as enough authority to read or modify profile-owned data. In a private local tutorial app this was acceptable, but in a public multi-user app it is unsafe because a person who can guess, capture, or submit another profile ID could access or modify another person's data.

The current Ask AI V2 RAG path also filters notes by profile ID through `user_id`, but it does not include an authenticated account owner field. This means `user_id` is a profile selector, not an authorization boundary.

## Current Data Flow

Profiles are stored in the Astra `personal_data` collection. The current profile shape includes:

- `_id`
- `name`
- `age`
- `weight`
- `height`
- `gender`
- `activity_level`
- `goals`
- `nutrition`

Notes are stored in the Astra `notes` collection. Current note documents include at least:

- `_id`
- `user_id`
- `text`
- `$vectorize`
- Astra-managed `$vector`

In current code, `user_id` means the selected fitness profile ID. It does not mean authenticated account ID.

## Current Profile Behavior

The UI loads profiles through `profiles.py`, which delegates to `db.py`.

Current profile operations:

- `profiles.get_all_profiles()` calls `db.list_profiles()`.
- `db.list_profiles()` runs an unscoped collection query and returns all profiles.
- `profiles.get_profile_by_id(profile_id)` calls `db.get_profile(profile_id)`.
- `db.get_profile(profile_id)` looks up a profile by `_id` only.
- `profiles.create_new_profile(...)` calls `db.create_profile(...)`.
- `db.create_profile(profile_data)` inserts a profile without an owner field.
- `profiles.save_profile_changes(profile_id, ...)` calls `db.update_personal_information(profile_id, updates)`.
- `db.update_personal_information(profile_id, updates)` updates by `_id` only.

The Streamlit UI stores the selected profile in `st.session_state.selected_profile_id` and `st.session_state.selected_profile`. There is no authenticated account in session state today.

## Current Notes Behavior

Notes are currently scoped only by selected profile ID.

Current note operations:

- `db.add_note(user_id, text)` stores `user_id`, `text`, and `$vectorize`.
- `db.list_notes(user_id, limit=...)` queries notes by `{"user_id": user_id}`.
- `db.delete_note(user_id, note_id)` deletes by `{"_id": note_id, "user_id": user_id}`.
- `db.update_note(user_id, note_id, text)` updates by `{"_id": note_id, "user_id": user_id}`.

This prevents accidental cross-profile note access in the current local app, but it is not sufficient for public multi-user authorization because the caller controls or derives the profile ID.

## Current Ask AI V2 Behavior

The exported `flows/ask_ai_v2.json` contains:

- `question` input: `ChatInput-sk4My`
- router prompt: `Prompt Template-Ep1bw`
- router model: `ext:openrouter:OpenRouterComponent@official-lyVR9`
- conditional router: `ConditionalRouter-pJ6SL`
- math path: `Agent-8TtHH` with `CalculatorComponent-Q8RgL`
- non-math RAG path: `ext:datastax:AstraDBVectorStoreComponent@official-2VBhC`, `ParserComponent-Vi5va`, `Prompt Template-GtOCM`, and `ext:openrouter:OpenRouterComponent@official-N7r20`

This is one tool-calling agent plus one normal RAG chain, not multiple peer agents.

The current Python integration supplies the RAG filter through the exported Astra component:

```text
ext:datastax:AstraDBVectorStoreComponent@official-2VBhC.advanced_search_filter
```

The current filter shape is:

```json
{"user_id": "<selected_profile_id>"}
```

The exported flow does not contain `owner_account_id` today. Public multi-user authorization requires adding account ownership to the RAG filter later, after the database records contain that field and the Langflow Astra component is confirmed to support the required filter shape.

## Sensitive Streamlit Session State

Current user-sensitive state includes:

- `selected_profile_id`
- `selected_profile`
- `profiles`
- `nutrition`
- `nutrition_draft`
- `nutrition_draft_profile_id`
- `nutrition_draft_version`
- `last_ai_answer`
- `ui_error`
- `profile_success`
- `macro_success`
- `macro_error`
- `notes`
- `notes_profile_id`
- `notes_success`
- `notes_error`
- `confirm_delete_note_id`
- `ask_ai_error`

When logout is implemented, all account-specific and profile-specific values must be cleared. The app must not leave a previous account's selected profile, notes, nutrition draft, or AI answer in session state.

## Proposed Accounts Collection

Add a new Astra collection:

```text
accounts
```

Account document concept:

```json
{
  "_id": "normalized_username",
  "account_id": "random-uuid",
  "username": "display username",
  "password_hash": "argon2id hash",
  "created_at": "ISO-8601 timestamp"
}
```

Rules:

- `_id` is the normalized username so duplicate usernames are naturally rejected.
- `account_id` is a random UUID and is the authorization ownership identifier.
- Usernames are not used as ownership identifiers.
- Plaintext passwords are never stored.
- `password_hash` is never sent to Streamlit UI, Langflow, OpenRouter, logs, profile context, or model prompts.
- Password verification should use Argon2id through a maintained Python package such as `argon2-cffi`, added in a later implementation milestone.

## Ownership Model

Profile documents in `personal_data` gain:

```json
{
  "owner_account_id": "account uuid"
}
```

Note documents in `notes` gain:

```json
{
  "owner_account_id": "account uuid",
  "user_id": "profile id"
}
```

Meanings:

- `owner_account_id` identifies the authenticated account that owns the data.
- `user_id` remains the selected fitness profile ID for note/profile RAG retrieval.
- Existing Langflow RAG semantics can remain profile-based, but must also be owner-scoped before public multi-user deployment.

## Required Authorization Changes

Profile operations must become account-scoped:

- `list_profiles(owner_account_id)` must query only `{"owner_account_id": account_id}`.
- `get_profile(profile_id, owner_account_id)` must query by both `_id` and `owner_account_id`.
- `create_profile(profile_data, owner_account_id)` must insert `owner_account_id`.
- `update_personal_information(profile_id, owner_account_id, updates)` must update by both `_id` and `owner_account_id`.

Notes operations must become account-scoped:

- Before adding a note, verify the selected profile belongs to the authenticated account.
- `add_note(owner_account_id, user_id, text)` must store both `owner_account_id` and `user_id`.
- `list_notes(owner_account_id, user_id, limit=...)` must query by both fields.
- `delete_note(owner_account_id, user_id, note_id)` must delete by `_id`, `user_id`, and `owner_account_id`.
- `update_note(owner_account_id, user_id, note_id, text)` must update by `_id`, `user_id`, and `owner_account_id`.

Ask AI/RAG must become account-scoped:

- The Streamlit UI must only call Ask AI for a profile that belongs to the authenticated account.
- The Langflow Astra runtime filter should include both profile and owner fields, for example:

```json
{"user_id": "<profile_id>", "owner_account_id": "<account_id>"}
```

The exact filter syntax must be validated in the current Langflow/Astra component before implementation. If multi-field filtering is not supported or is ambiguous, the app is not safe for public multi-user Ask AI RAG.

## Session Model

Future Streamlit session state should include only non-secret auth state:

- `authenticated_account_id`
- `authenticated_username`
- `auth_error`

It must not store:

- plaintext passwords
- password hashes
- Astra tokens
- Langflow API keys
- OpenRouter keys

Logout must clear:

- authenticated account state
- selected profile state
- loaded profiles
- notes
- nutrition drafts
- last AI answer
- transient success/error messages tied to the account

## Legacy Data Migration Plan

Existing profiles and notes without `owner_account_id` are legacy/unowned data.

Default rule:

- Legacy/unowned profiles are not visible to any newly created account.
- Legacy/unowned notes are not retrievable through the authenticated app.
- No account automatically claims existing records.

Later migration tool plan:

- Create a script such as `scripts/migrate_legacy_ownership.py`.
- Require explicit operator confirmation.
- Support dry-run mode by default.
- Accept an explicit mapping from legacy profile IDs to an existing account username or account ID.
- Resolve the target account to `account_id`.
- Update only selected legacy profile records.
- Update only notes whose `user_id` matches those selected profile IDs.
- Print counts and sanitized IDs only.
- Never drop collections or modify unrelated records.

## Files Expected To Change Later

Expected implementation files:

- `requirements.txt` for an Argon2id password hashing dependency.
- `config.py` for `ACCOUNTS_COLLECTION` or related configuration.
- `db.py` for account CRUD, password hash storage, and owner-scoped profile/note operations.
- `profiles.py` for owner-aware service functions.
- `ai.py` if Ask AI tweak construction must include `owner_account_id` in the Langflow RAG filter.
- `main.py` for register/login/logout UI and account-scoped data loading.
- `tests/` for account, authorization, session clearing, and cross-account isolation tests.
- `docs/LANGFLOW_SETUP.md` if Ask AI V2 filter tweaks change.
- `docs/SECURITY_REVIEW.md` after implementation.
- `.env.example` only if new non-secret placeholder names are needed.

## Risks And Blockers

- Secrets previously appeared in chat/screenshots. Astra, Langflow, and OpenRouter credentials should be rotated before any public deployment.
- Current exported Ask AI V2 only filters by `user_id`; it does not filter by `owner_account_id`.
- Langflow/Astra must be verified to support a runtime multi-field metadata filter before public multi-user RAG can be considered safe.
- The current app has no rate limiting, password reset, account lockout, or abuse controls.
- Streamlit session state is server-side per browser session, but it is not a complete authentication system by itself.
- Public multi-user deployment remains unsafe until every profile, note, and RAG retrieval path enforces `owner_account_id`.

## Success Criteria For A Later Implementation

- A user can register with username and password.
- Login verifies Argon2id password hashes.
- Password hashes never leave server-side code.
- Profiles are listed only for the authenticated `account_id`.
- Profile reads and updates require both profile ID and owner account ID.
- Notes store both owner account ID and profile ID.
- Notes reads, updates, and deletes require both owner account ID and profile ID.
- Ask AI RAG filters by both `user_id` and `owner_account_id`.
- Logout clears all user-specific Streamlit state.
- Legacy data remains inaccessible until explicitly migrated.
