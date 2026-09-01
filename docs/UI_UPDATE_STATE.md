# Profile UI Update State

## UI Prompt-00 Audit

### Current implementation
- Exact UI file: `main.py`.
- Profile section: `render_profile_section()` at `main.py:416-483`.
- Profile form: `_render_profile_form()` at `main.py:324-412`, used by both create and edit tabs.
- Profile defaults: `_profile_form_defaults()` at `main.py:311-321`.
- Goals text helpers: `_goals_from_text()` and `_goals_to_text()` at `main.py:192-201`.
- Selected-profile display: `main.py:464-473` shows profile ID, activity text, and goal count.
- Current widgets:
  - Gender: `st.text_input("Gender", value=defaults["gender"], key=f"{form_key}_gender")`.
  - Activity level: `st.text_input("Activity level", value=defaults["activity_level"], key=f"{form_key}_activity_level")`.
  - Goals: `st.text_area("Goals", value=defaults["goals"], placeholder="Build strength\nImprove endurance", key=f"{form_key}_goals")`.
- Form keys:
  - Create: `create_profile_form`, widget keys prefixed with `create_profile_form_`.
  - Edit: `edit_profile_form`, widget keys prefixed with `edit_profile_form_`.

### Current data contract
- `gender`: `str`; required for create, allowed on update, must be non-empty after trimming in `db.py`.
- `activity_level`: `str`; required for create, allowed on update, must be non-empty after trimming in `db.py`.
- `goals`: `list[str]`; required for create, allowed on update, must contain only non-empty strings in `db.py`.
- `profiles.py` normalizes goals more leniently than `db.py`: non-list goal values become a one-item list if non-empty, and list items are stringified/truncated.

### Existing value vocabulary
- Gender has no finite UI option list. Repository examples use `female` and `unspecified`.
- Activity level has no finite UI option list. Repository examples use `moderate` and `active`.
- Goals have no finite UI option list. Repository examples include `Build strength`, `Improve endurance`, `build strength`, `improve endurance`, `strength`, `mobility`, `endurance`, `maintain mobility`, `use private note context`, and `separate note context`.
- The target labels `Sedentary`, `Lightly Active`, `Moderately Active`, `Very Active`, `Super Active`, `Muscle Gain`, `Fat Loss`, and `Stay Active` are not currently used in source, tests, docs, or flow exports.
- `flows/macro_flow.json` contains a sample goals value: `Build strength while maintaining energy for 4 workouts per week.`

### Persistence path
- Create: `main._render_profile_form()` builds `profile_payload` -> `profiles.create_new_profile(account_id=..., **profile_payload)` -> `db.create_profile(account_id, profile_data)` -> Astra personal collection `insert_one(document)` with `owner_account_id`.
- Edit: `main._render_profile_form()` builds `profile_payload` -> `profiles.save_profile_changes(account_id, profile_id, **profile_payload)` -> `db.update_personal_information(account_id, profile_id, cleaned_updates)` -> Astra personal collection `update_one(..., {"$set": update_document}, upsert=False)`.
- Read/select: `main._refresh_profiles()` -> `profiles.get_all_profiles(account_id)` / `profiles.get_profile_by_id(account_id, selected_id)` -> `db.list_profiles()` / `db.get_profile()` -> `profiles.normalize_profile()`.

### Existing-profile compatibility risks
- Gender edit prefill currently accepts any stored string via `defaults["gender"]`. A future `st.radio` can fail or lose the current value if a legacy value such as `unspecified`, lowercase `female`, blank-like data, or another arbitrary string is not represented.
- Activity edit prefill currently accepts any stored string via `defaults["activity_level"]`. A future `st.selectbox` can fail or silently change meaning if legacy values such as `moderate` or `active` are not represented.
- Goals edit prefill currently converts stored list values to newline text. A future `st.multiselect` can reject or omit arbitrary legacy goals unless unknown values are added to the options or otherwise preserved.
- Current text-area parsing splits goals on commas and newlines. A multiselect would stop supporting ad hoc comma/newline entry unless an explicit custom-entry path is added.
- Database validation does not restrict vocabulary, so UI constraints would become the first finite vocabulary boundary.

### Session-state risks
- Relevant session keys: `selected_profile_id`, `selected_profile`, `profiles`, `nutrition`, `nutrition_draft`, `nutrition_draft_profile_id`, `nutrition_draft_version`, `profile_success`, `ui_error`, `macro_success`, `macro_error`, `notes`, `notes_profile_id`, `confirm_delete_note_id`, `ask_ai_error`, and `last_ai_answer`.
- Profile widget keys are deterministic per form mode: `create_profile_form_gender`, `create_profile_form_activity_level`, `create_profile_form_goals`, `edit_profile_form_gender`, `edit_profile_form_activity_level`, and `edit_profile_form_goals`.
- Changing widget type while reusing keys may leave stale incompatible values in Streamlit widget state during reruns or profile switching.
- Create and edit forms render in separate tabs during the same run, so create/edit keys must remain distinct.
- After saving, `_refresh_profiles()` reloads and resets `selected_profile` before `st.rerun()`. Widget defaults for edit mode depend on the selected profile reloading cleanly.

### Downstream AI dependencies
- `profiles.build_profile_context()` includes `gender`, `activity_level`, and `goals` in deterministic prompt text.
- `render_nutrition_section()` sends `profiles.build_profile_context(selected_profile)` plus `_goals_to_text(selected_profile).strip() or "No specific goals provided."` to `ai.get_macros()`.
- `ai.get_macros()` sends goals as a string tweak to the configured Langflow goals component.
- `render_ask_ai_section()` sends `profiles.build_profile_context(selected_profile)` to `ai.ask_ai()`.
- `ai.ask_ai()` sends profile context through the configured Ask AI profile component and does not separately send goals.
- No code enforces exact activity or goal labels, but changing persisted labels will change the literal semantic text passed to Langflow.

### Styling/theme observations
- No `.streamlit/config.toml` theme file was found.
- `main.py` uses `st.set_page_config(page_title="Personal Fitness AI Assistant", layout="wide")`.
- No custom CSS or `unsafe_allow_html=True` styling was found in `main.py`.
- Layout is standard Streamlit:
  - App body split into two wide columns at `main.py:810-818`.
  - Profile content inside `st.container(border=True)`.
  - Gender and activity are side-by-side inside `st.columns(2)`.
  - Goals spans the form width below those columns.
- Current styling risk is low because there are no custom DOM selectors, but switching gender to vertical radio could increase form height inside the bordered profile container.

### Relevant tests
- `tests/test_main_resilience.py` covers profile create/edit payloads and selected-profile refresh behavior.
- `tests/test_profiles.py` covers profile normalization, profile-context generation, create/update pass-through, goal-list preservation, and optional nutrition normalization.
- `tests/test_db.py` covers DB validation for required fields, non-empty `gender` / `activity_level`, `goals: list[str]`, owner scoping, create, and update.
- `tests/test_utils_serialization.py` covers list serialization in prompt context.
- `tests/test_ai.py` covers Macro Flow goals tweak construction and Ask AI profile-context passing with mocked Langflow calls.
- `docs/ACCEPTANCE_TESTS.md` includes manual profile create/select/edit/refresh checks.
- Missing regression coverage before implementation:
  - UI helper behavior for mapping legacy `gender` values to a radio default without data loss.
  - UI helper behavior for mapping legacy `activity_level` values to a selectbox default without data loss.
  - UI helper behavior for preserving arbitrary legacy goals in multiselect defaults/options.
  - Create/edit tests updated for `st.radio`, `st.selectbox`, and `st.multiselect` in the fake Streamlit test double.
  - Downstream context tests showing selected display labels/persisted values still serialize as intended.

### Recommended minimal implementation scope
- Change only `main.py` for the next UI milestone if persisted values remain strings/list strings.
- Add small UI-layer option constants and compatibility helper functions near `_profile_form_defaults()` / goals helpers.
- Keep `profiles.py`, `db.py`, `ai.py`, Astra schema/data, flow JSON, and Langflow configuration unchanged.
- Preserve existing stored values when editing profiles, especially values not present in the new finite option candidates.
- Consider whether visible labels should equal persisted values. If they differ, keep a deliberate display-value mapping in the UI layer and test it.

### Blockers / decisions required
- Decide how to handle legacy gender values outside `Male`, `Female`, and `Other`.
- Decide how to map existing activity strings such as `moderate` and `active` to display options such as `Moderately Active` and `Very Active`, or whether to preserve legacy strings as additional options.
- Decide whether goals should be limited to fixed labels or allow legacy/custom values to survive edits.
- Decide whether new display labels should become the stored semantic values sent to AI, or whether existing lowercase/domain values should remain the storage contract.

### Baseline verification result
- Working directory: `/Users/macbook/Desktop/Fahmid/Target/7.AI App/2.Date.13.08.2026/AI-Fitness-App`.
- Git branch: `main`.
- Initial `git status --short`: clean.
- Top-level project files/directories include `main.py`, `profiles.py`, `db.py`, `ai.py`, `auth.py`, `config.py`, `utils.py`, `requirements.txt`, `requirements-dev.txt`, `tests/`, `docs/`, `flows/`, `scripts/`, and `migration_manifests/`.
- Project virtualenv Python: 3.11.15.
- System `python3`: 3.9.6.
- Streamlit version in `.venv`: 1.61.1. Streamlit is not importable from system `python3`.
- Safe checks run:
  - `./.venv/bin/python -m compileall main.py profiles.py db.py ai.py utils.py`: passed.
  - `./.venv/bin/python -m pytest tests/test_profiles.py tests/test_db.py tests/test_utils_serialization.py tests/test_ai.py tests/test_main_resilience.py`: 154 passed.
- Skipped live/setup scripts such as `scripts/live_acceptance.py`, `scripts/check_astra.py`, setup scripts, and macro-flow smoke scripts because they can require cloud credentials or call Astra/Langflow.
