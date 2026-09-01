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

## UI Prompt-01 — Option Contract & Legacy Compatibility

### Canonical UI options

Gender:
- Male
- Female
- Other

Activity:
- Sedentary
- Lightly Active
- Moderately Active
- Very Active
- Super Active

Goals:
- Muscle Gain
- Fat Loss
- Stay Active

### Legacy compatibility strategy
- Canonical options are defined as immutable tuples in `main.py`; they are UI choices only, not database enums.
- `_single_choice_options_with_current()` returns canonical options unchanged when the current value is already canonical, `None`, empty, or blank.
- `_single_choice_options_with_current()` prepends a meaningful non-canonical current value to the canonical options. This keeps a stored legacy value representable by a future radio/selectbox without rewriting it.
- `_goal_options_with_existing()` returns canonical goals plus any meaningful existing goals that are not already present.
- Existing custom goals are appended in their current order, with duplicates removed, so edit-mode multiselect options can include every stored value.
- Helper logic does not mutate caller-owned lists or tuples.

### Mapping policy
- NO automatic semantic mapping.
- `moderate` != automatically `Moderately Active`.
- `active` != automatically `Very Active`.
- `unspecified` != automatically `Other`.
- `Build strength` != automatically `Muscle Gain`.
- `Improve endurance` != automatically `Stay Active`.

### Helpers added
- `_unique_meaningful_options()` in `main.py`: shared pure dedupe/blank-filter helper for UI option preparation.
- `_single_choice_options_with_current()` in `main.py`: prepares future radio/selectbox options while preserving non-canonical current stored strings.
- `_goal_options_with_existing()` in `main.py`: prepares future multiselect options while preserving legacy/custom goal strings.
- Streamlit 1.61.1 exposes `format_func` on `st.radio`, `st.selectbox`, and `st.multiselect`; UI Prompt-02 can use that for display-only legacy labels if needed without changing stored values.

### Test coverage added
- Added `tests/test_profile_ui_options.py`.
- Covers exact canonical constants, canonical deduplication, unknown gender preservation, unknown activity preservation for `moderate` and `active`, no semantic activity mapping, blank single-choice handling, canonical goal availability, legacy goal preservation, goal deduplication, deterministic existing-goal order, helper non-mutation, and unchanged `gender: str`, `activity_level: str`, `goals: list[str]` storage validation.

### Files changed
- `main.py`
- `tests/test_profile_ui_options.py`
- `docs/UI_UPDATE_STATE.md`

### Verification result
- Focused helper tests: `./.venv/bin/python -m pytest tests/test_profile_ui_options.py` passed with 11 tests.
- Safe regression subset: `./.venv/bin/python -m pytest tests/test_profile_ui_options.py tests/test_profiles.py tests/test_db.py tests/test_utils_serialization.py tests/test_ai.py tests/test_main_resilience.py` passed with 165 tests.
- Compile verification: `./.venv/bin/python -m compileall main.py profiles.py db.py ai.py utils.py` passed.
- No live Astra, Langflow, OpenRouter, setup, or smoke scripts should be run for this milestone.

### Ready for UI Prompt-02
- Yes.

## UI Prompt-02 — Functional Widget Replacement

### Widgets implemented

Gender:
- `st.radio`

Activity Level:
- `st.selectbox`

Goals:
- `st.multiselect`

### Create-mode behavior
- Gender uses only `GENDER_OPTIONS` and starts with no selected value by passing `index=None`, matching the old form's lack of a meaningful text default.
- Activity Level uses only `ACTIVITY_LEVEL_OPTIONS` and starts with no selected value by passing `index=None`, matching the old form's lack of a meaningful text default.
- Goals uses only `GOAL_OPTIONS` and starts with an empty selected list.
- Create-mode goals do not include arbitrary legacy goals from existing profiles.

### Edit-mode behavior
- Canonical gender and activity values initialize by exact option match.
- Legacy single-choice values are prepended to the canonical options and selected by index.
- Existing goals initialize as the multiselect default list.
- Legacy/custom goals are appended to the available goal options and remain selected.
- Mixed canonical and legacy goals initialize without duplicate options.

### Legacy preservation
- `unspecified` remains an exact editable gender value and is not converted to `Other`.
- `moderate` remains an exact editable activity value and is not converted to `Moderately Active`.
- `active` remains an exact editable activity value and is not converted to `Very Active`.
- `Build strength` remains an exact editable goal and is not converted to `Muscle Gain`.
- `Improve endurance` remains an exact editable goal and is not converted to `Stay Active`.

### Session-state handling
- New target widget keys:
  - `create_profile_form_gender_choice`
  - `create_profile_form_activity_level_choice`
  - `create_profile_form_goals_multiselect`
  - `edit_profile_form_gender_choice`
  - `edit_profile_form_activity_level_choice`
  - `edit_profile_form_goals_multiselect`
- The old target widget keys are no longer used for the replaced fields.
- `_set_selected_profile()` clears only the edit-mode choice widget keys so switching selected profiles forces edit widgets to reinitialize from the selected profile instead of stale widget state.
- Selection state such as `selected_profile_id`, `selected_profile`, `profiles`, nutrition, notes, and AI answer state is not cleared by this targeted cleanup.

### Goals submission contract
- `st.multiselect` returns a list.
- The active submission path now passes `list(goals or [])` directly through `profiles.create_new_profile()` / `profiles.save_profile_changes()`.
- Goals remain `list[str]` for storage and downstream profile context.
- The active Goals submission path no longer uses the old textarea comma/newline parsing helper.

### Backend impact
- `profiles.py`: unchanged.
- `db.py`: unchanged.
- `ai.py`: unchanged.
- Langflow: unchanged.
- Astra schema: unchanged.

### Tests
- Updated `tests/test_main_resilience.py` fake Streamlit support for `radio`, `selectbox`, and `multiselect`.
- Added coverage for create-mode canonical options and empty defaults.
- Added coverage for edit-mode canonical initialization.
- Added coverage for legacy gender, legacy activity values `moderate` and `active`, legacy goals, mixed canonical/legacy goals, no unrelated legacy goals in create mode, list submission without textarea parsing, intentional canonical replacements, and targeted stale-state clearing.
- Existing `tests/test_profile_ui_options.py` continues to cover the option contract and helper behavior.

### Ready for UI Prompt-03
- Yes.

## UI Prompt-03 — Layout & Visual Polish

### Final target layout

Gender
-> vertical radio

Activity Level
-> full-row selectbox

Goals
-> section heading + `Select Your Goals` multiselect

### Layout change
- The old Gender/Activity Level `st.columns(2)` arrangement was removed from the profile form.
- Gender, Activity Level, and Goals now render sequentially in the form.
- Unrelated columns remain unchanged, including the age/weight/height profile row and unrelated note confirmation layout.

### Styling strategy
- Native Streamlit widgets are used for all three target controls.
- Custom CSS added: no.
- JavaScript added: no.
- Global theme changed: no.
- Orange screenshot annotation borders and artificial focus borders were not recreated.

### Responsive behavior
- Activity Level relies on the native full-row `st.selectbox` width in the form container.
- Goals relies on the native full-row `st.multiselect` width in the form container.
- No fixed pixel widths were added.

### Functional behavior preserved
- Canonical options unchanged.
- Legacy values remain representable through the existing Prompt-01 helpers.
- Goals remain `list[str]`.
- Profile switching targeted widget-state clearing is unchanged.
- Persistence continues through the existing explicit form submit path.
- Backend files and cloud integrations are unchanged.

### Visual verification
- Method: source/layout inspection plus mocked Streamlit UI tests.
- Result: verified Gender is a vertical `st.radio`, Activity Level is below Gender as a full-row `st.selectbox`, and Goals is below Activity Level with one `Goals` heading and a `Select Your Goals` multiselect label.
- Manual browser visual verification: not run because rendering the authenticated profile form with real Streamlit would require logging in and loading profile data through the live Astra-backed path. No safe local/mock visual mode exists in the repository.

### Tests
- Focused UI tests: `./.venv/bin/python -m pytest tests/test_profile_ui_options.py tests/test_main_resilience.py` passed with 56 tests.
- Safe regression suite: `./.venv/bin/python -m pytest tests/test_profile_ui_options.py tests/test_profiles.py tests/test_db.py tests/test_utils_serialization.py tests/test_ai.py tests/test_main_resilience.py` passed with 174 tests.
- Compile verification: `./.venv/bin/python -m compileall main.py profiles.py db.py ai.py utils.py` passed.

### Ready for UI Prompt-04
- Yes.

## UI Prompt-04 — Dynamic Goals Editor

### Goal editor implementation
- Replaced the active `st.multiselect("Select Your Goals", ...)` Goals interaction with a native Streamlit editor.
- Streamlit APIs used: `st.subheader`, `st.container(border=True)`, `st.columns`, `st.write`, `st.text_input`, and callback-capable `st.form_submit_button`.
- The editor stays inside the existing profile `st.form`; add/remove controls are keyed `st.form_submit_button` callbacks, and only the existing Create/Save submit button reaches the persistence path.
- Each current goal is rendered as a row with the goal text and a `−` remove control.
- The add control is rendered as a right-aligned `+` row inside the bordered editor area as closely as native Streamlit layout permits.

### Default new-profile goal
- `Muscle Gain`.
- Create-mode goal editor initializes once to `["Muscle Gain"]` only when the create editor state key is absent.
- If the user removes `Muscle Gain`, the empty list remains in session state and the default is not reinserted on rerun.

### Add behavior
- Pressing `+` opens an inline `New Goal` text input and `Add Goal` submit control.
- New goals are arbitrary plain strings.
- Surrounding whitespace is trimmed for newly entered goals.
- Blank input is rejected with concise feedback.
- Exact duplicates already present in the current editor state are rejected.
- Successful add clears the temporary input, closes the add row, and keeps the updated list in temporary session state.

### Remove behavior
- Every current goal has a `−` control.
- Remove keys are index-scoped under the current editor state key instead of using goal text directly.
- Pressing `−` removes only that goal from temporary session state.
- Removing the last goal leaves a valid empty list `[]`.

### Existing-profile behavior
- Existing profiles initialize from their stored goals exactly.
- Existing empty goal lists initialize empty.
- `Muscle Gain` is not injected into existing profiles.
- Legacy/custom goals such as `Build strength` and `Improve endurance` render as normal editable/removable goals.

### Session state
- Create keys:
  - `create_profile_form_goals_editor`
  - `create_profile_form_goal_input`
  - `create_profile_form_goal_add_open`
  - `create_profile_form_goal_error`
- Edit keys are profile-scoped:
  - `edit_profile_form_goals_editor_<profile_id>`
  - `edit_profile_form_goal_input_<profile_id>`
  - `edit_profile_form_goal_add_open_<profile_id>`
  - `edit_profile_form_goal_error_<profile_id>`
- Goal editor state is always normalized to `list[str]`.
- `_set_selected_profile()` clears only edit-mode choice/editor keys so profile switching reinitializes from the newly selected stored profile.
- Successful create clears create-mode goal editor keys so the next new-profile editor gets the one-time default again.
- Successful edit synchronizes the edit goal editor state with the saved goals before rerun/refresh.

### Persistence
- `+` does not persist.
- `−` does not persist.
- Create/Save persists the current temporary goal list through the existing `profiles.py` service path.
- No direct Astra write was introduced in the goal editor.

### Data contract
- Goals remain `list[str]`.
- Goals are not JSON-encoded, comma-joined, or newline-joined.

### Tests
- Focused UI tests: `./.venv/bin/python -m pytest tests/test_profile_ui_options.py tests/test_main_resilience.py` passed with 62 tests.
- Safe regression suite: `./.venv/bin/python -m pytest tests/test_profile_ui_options.py tests/test_profiles.py tests/test_db.py tests/test_utils_serialization.py tests/test_ai.py tests/test_main_resilience.py` passed with 180 tests.
- Compile verification: `./.venv/bin/python -m compileall main.py profiles.py db.py ai.py utils.py` passed.
- Coverage includes one-time new-profile default, removal without reinsertion, existing/empty/legacy profile initialization, add validation, duplicate prevention, multiple custom goals, removing all goals, list-state preservation, add/remove non-persistence, Create/Save persistence boundary, profile switching, save synchronization, and Gender/Activity regression behavior.

### Visual verification
- Method: source/layout inspection plus mocked Streamlit UI tests.
- Result: verified Goals heading, bordered editor grouping, goal rows with `−` controls, right-side `+` control, add input flow, empty state, and no active `st.multiselect` in the profile form.
- Manual browser visual verification: not run because rendering and interacting with the authenticated profile form against the real app would require live Astra-backed login/profile data. No safe local/mock visual mode exists in the repository.

### Ready for UI Prompt-05
- Yes.

## UI Prompt-05 — Light/Dark Runtime Theme

### Streamlit runtime theme capability
- Installed Streamlit version checked in the project virtualenv: 1.61.1.
- No supported public API was found for switching Streamlit's built-in theme at runtime.
- Private Streamlit theme/config internals were not used.
- Implementation uses `st.session_state` plus centralized CSS custom properties.

### Theme state
- Session key: `ui_theme`.
- Allowed values: `light` and `dark`.
- Default behavior: unsupported, absent, or invalid values initialize to `light`.
- Rerun behavior: existing valid theme state is preserved by `_initialize_ui_theme_state()`.
- `_toggle_ui_theme()` changes only `ui_theme`.

### Theme control
- The control is a native `st.button`, rendered through a top-right `st.columns((6, 1))` layout.
- Light mode shows `🌙 Dark`.
- Dark mode shows `☀️ Light`.
- It is rendered immediately after `st.set_page_config()` and before authentication/profile controls.
- No JavaScript or HTML-based functional control was added.

### Theme tokens and CSS
- Theme tokens are centralized in `UI_THEME_TOKENS`.
- Token contract includes background, surface, surface_alt, text, text_muted, border, input_background, accent, button_background, button_text, success, warning, and error.
- CSS is injected from `_apply_ui_theme()` with custom properties and stable selectors such as `data-testid` and `data-baseweb`.
- Generated/hash selectors are not used.
- Runtime `.streamlit/config.toml` mutation was not added.
- No dependencies were added.

### Light theme
- Background: `#f7f8fb`.
- Surface: `#ffffff`.
- Alternate surface: `#eef2f7`.
- Text: `#172033`.
- Muted text: `#586174`.
- Input background: `#ffffff`.
- Accent/button: `#2563eb`.

### Dark theme
- Background: `#111827`.
- Surface: `#1f2937`.
- Alternate surface: `#273449`.
- Text: `#f3f4f6`.
- Muted text: `#c5cbd6`.
- Input background: `#172033`.
- Accent/button: `#60a5fa`.

### State preservation
- Theme toggling does not reset `selected_profile_id`.
- Theme toggling does not clear `selected_profile`.
- Theme toggling does not clear create-mode Goals editor state.
- Theme toggling does not clear edit-mode Goals editor state.
- Removing the starter `Muscle Gain` goal remains preserved across a theme switch.
- Custom create/edit goals remain preserved across a theme switch.
- Theme toggling does not clear nutrition, notes, note confirmation, Ask AI answer, or Ask AI error state.

### Backend isolation
- Theme toggling does not write to profile persistence.
- Theme toggling does not call Astra directly.
- Theme toggling does not call Langflow.
- Theme toggling does not call OpenRouter.
- The Goals `+` and `−` controls remain temporary session-state actions only.
- Profile Create/Save remains the only profile-form persistence boundary.

### Existing UI preservation
- Gender remains `st.radio`.
- Activity Level remains `st.selectbox`.
- Goals remain the dynamic native `+` / `−` editor.
- `st.multiselect` is not active in the profile Goals editor.

### Tests
- Focused UI/theme tests: `./.venv/bin/python -m pytest tests/test_profile_ui_options.py tests/test_main_resilience.py` passed with 76 tests.
- Safe regression suite should remain: `./.venv/bin/python -m pytest tests/test_profile_ui_options.py tests/test_profiles.py tests/test_db.py tests/test_utils_serialization.py tests/test_ai.py tests/test_main_resilience.py`.
- Compile verification should remain: `./.venv/bin/python -m compileall main.py profiles.py db.py ai.py utils.py`.
- Coverage includes initialization, allowed values, default fallback, both toggle directions, rerun persistence, selected-profile preservation, create/edit Goals preservation, removed starter goal preservation, custom Goals preservation, backend isolation, control ordering, no private API, no JavaScript, Gender regression, Activity regression, and Goals editor regression.

### Visual verification
- Method: source/layout inspection plus mocked Streamlit UI tests.
- Manual browser visual verification: not run because rendering and interacting with the authenticated profile UI requires live Astra-backed login/profile loading, and the repository has no safe local/mock visual mode.

### Backend impact
- `profiles.py`: unchanged.
- `db.py`: unchanged.
- `ai.py`: unchanged.
- Langflow: unchanged.
- Astra DB/schema: unchanged.

## UI Prompt-06 — Theme and Goals Visual Integration

### Visual design strategy
- Continued the existing Prompt-05 centralized runtime theme system.
- Used a restrained SaaS visual style with soft light backgrounds, deep neutral dark backgrounds, subtle borders, modest radius, and light shadowing.
- Kept native Streamlit widgets and improved their visual consistency through shared theme tokens.

### Theme tokens changed/added
- Added a shared `UI_THEME_TOKEN_NAMES` contract.
- Added `border_strong`, `input_hover`, `accent_hover`, `button_hover`, `danger`, `danger_hover`, `focus_ring`, and `shadow`.
- Light and Dark themes define the same token names.
- Existing core tokens for background, surface, text, muted text, input background, accent, primary button, and status colors remain.

### Goals editor styling
- The bordered editor uses the existing `st.container(border=True)` surface, styled centrally through the theme CSS.
- Goal rows now use conservative `(4, 1)` columns so the text column remains dominant while the remove control stays compact.
- Long goal text remains in a native text column and can wrap without overlapping the remove control.
- Empty state copy is now `No goals added yet.` and does not reinsert defaults.

### Add/remove control styling
- Auxiliary buttons use the shared secondary button styling: subtle surface background, theme-aware border, hover state, and focus ring.
- The `+` control remains compact in the right-side control column and has native help text.
- The `−` controls remain compact in each row and have native help text identifying the goal being removed.
- Individual danger styling for only `−` controls was not added because Streamlit does not expose a stable per-button selector for that intent without brittle label/DOM targeting.

### Input styling
- Text inputs, number inputs, text areas, and selectbox inputs share theme-aware backgrounds, borders, hover states, focus rings, and placeholder color.
- Selectbox arrow SVG color follows the muted text token.
- New Goal input uses the same central styling as other text inputs.

### Button hierarchy
- Primary Create/Save buttons remain visually dominant through `kind="primary"` styling.
- Theme toggle, `+`, `−`, and Add Goal use restrained secondary styling.
- Auxiliary controls are intentionally less prominent than profile persistence actions.

### Responsive behavior
- No fixed pixel widths were added.
- Goal row columns use conservative ratios instead of extreme desktop-only spacing.
- The form remains native Streamlit-responsive and does not introduce horizontal scrolling.

### Light mode result
- Page background is soft light.
- Major surfaces are white with subtle borders and a modest shadow.
- Inputs stay neutral and readable.
- Text and muted text use dark readable tokens.
- Goals editor, `+`, `−`, Add Goal, and theme toggle all share the light theme styling.

### Dark mode result
- Page background is deep neutral/navy.
- Surfaces are slightly lighter than the page background.
- Inputs remain distinct from surfaces and page background.
- Text and muted text use readable light tokens.
- Goals editor, `+`, `−`, Add Goal, and theme toggle all share the dark theme styling.

### CSS safety
- Styling remains in one centralized `_apply_ui_theme()` block.
- Stable `data-testid`, `data-baseweb`, element, pseudo-class, and ARIA-role selectors are used.
- Generated/hash selectors are not used.
- No JavaScript, HTML event handlers, custom component package, config mutation, or dependency additions were introduced.

### Functional behavior preserved
- `ui_theme` semantics, default, and toggle direction are unchanged.
- Gender remains vertical `st.radio`.
- Activity Level remains full-row `st.selectbox`.
- Goals remain dynamic native `+` / `−` with arbitrary custom goal support.
- Duplicate and blank goal validation are unchanged.
- Create-mode default `Muscle Gain` still initializes only once and is not reinserted after removal.
- Goals remain `list[str]`.
- `+` and `−` remain non-persistent session-state actions.
- Profile Create/Save remains the persistence boundary.
- Profile switching logic is unchanged.

### Tests
- Focused UI/theme tests: `./.venv/bin/python -m pytest tests/test_profile_ui_options.py tests/test_main_resilience.py` passed with 78 tests.
- Coverage includes shared token names, distinct light/dark tokens, theme toggle behavior, no generated/hash selectors, no JavaScript, no runtime config mutation, Gender/Activity/Goals regression behavior, empty Goals state, default removal persistence, non-persistent add/remove actions, Save/Create persistence boundary, and Goals state preservation across theme toggles.

### Manual verification
- Manual browser visual verification: not run because rendering and interacting with the authenticated profile UI requires live Astra-backed login/profile loading, and the repository has no safe local/mock visual mode.

### Ready for UI Prompt-07
- yes

## UI Prompt-07 — Final Acceptance

### Final implemented scope
- Gender uses vertical `st.radio` with canonical `Male`, `Female`, and `Other` options while preserving legacy current values.
- Activity Level uses full-row `st.selectbox` with canonical activity values while preserving legacy current values.
- Goals use a dynamic native Streamlit `+` / `−` editor with `list[str]` state and persistence only on explicit profile Create/Save.
- Runtime theme uses the session-state key `ui_theme`, allowed values `light` and `dark`, default `light`, and centralized CSS tokens.
- Runtime theme preference is session-state based and is not intended to persist to Astra or browser localStorage.

### Automated acceptance
- Final focused UI/profile acceptance tests passed.
- Full local/mock test suite passed.
- Compile, diff whitespace, startup, static safety, and backend/dependency diff checks passed.

### Test discovery
- safe: all 15 files under `tests/` are local/mock tests and were run with `./.venv/bin/python -m pytest`.
- skipped external: none from `tests/`.
- skipped external: live/manual scripts such as live Astra/Langflow smoke checks were not run because they require external credentials/services or can touch cloud state.

### New-profile acceptance
- Create-mode Goals initialize once to `["Muscle Gain"]`.
- Removing `Muscle Gain` leaves `[]` and a normal rerun does not reinsert it.
- Custom goals `Fat Loss`, `Run a half marathon`, and `Improve flexibility` can be added.
- Blank and duplicate additions are rejected.
- Removing a custom goal leaves the expected ordered list.
- Theme toggling preserves the temporary Goals state.
- No profile persistence call occurs before explicit Create Profile submission.

### Existing-profile acceptance
- Legacy gender `unspecified` remains representable and unchanged save preserves it.
- Legacy activity `moderate` remains representable and unchanged save preserves it.
- Legacy goals `Build strength` and `Improve endurance` initialize and save exactly as stored.
- Existing empty goals remain `[]`; `Muscle Gain` is not injected.

### Legacy compatibility
- No automatic semantic mapping is performed.
- `moderate` is not converted to `Moderately Active`.
- `active` is not converted to `Very Active`.
- `unspecified` is not converted to `Other`.
- Custom/legacy goals remain ordinary strings.

### Goals state acceptance
- Goals remain `list[str]`.
- Long, special-character, and 20-goal state tests pass.
- Ordering is deterministic.
- Exact duplicates remain prevented.
- Individual removal targets only the requested index.

### Theme acceptance
- Absent theme initializes to `light`.
- Invalid theme state normalizes to `light`.
- Toggle changes `light` to `dark` and `dark` to `light`.
- Valid theme survives initialization reruns.
- Theme toggles preserve selected profile state, Goals editor state, nutrition, notes, and Ask AI state.
- Light and Dark themes define the same `UI_THEME_TOKEN_NAMES` contract and have distinct background/surface/text/input tokens.

### Persistence-boundary verification
- Gender selection does not persist without form submission.
- Activity selection does not persist without form submission.
- Pressing `+`, typing New Goal, pressing Add Goal, pressing `−`, and toggling theme do not persist.
- Create Profile and Save changes remain the only profile-form persistence boundary.
- `main.py` continues to call `profiles.py` for profile persistence and does not bypass it with direct Astra profile writes.

### Unrelated-feature regression result
- Nutrition / Macros tests passed.
- Notes tests passed.
- Ask AI tests passed.
- Profile service tests passed.
- AI/Langflow client tests passed with mocked requests.

### Static safety review
- No runtime generated/hash CSS selectors were found.
- No JavaScript or custom component HTML path was introduced.
- No private Streamlit theme API was found.
- No runtime `config.toml` mutation was found.
- Environment variable names appear only in expected config/test/flow contexts; no real secret values were exposed.
- Merge-conflict markers, breakpoints, and relevant debug leftovers were not found in runtime UI code.

### Startup verification
- `./.venv/bin/streamlit run main.py --server.headless true --server.port 8507 --browser.gatherUsageStats false` started successfully and was stopped.
- Startup alone did not require profile mutation.

### Manual Browser Sign-Off Checklist

LIGHT MODE

[ ] theme button is top-right
[ ] page is visibly light
[ ] Gender is vertical
[ ] Activity Level is below Gender
[ ] Goals editor is below Activity
[ ] + is clearly visible
[ ] each goal has a visible −
[ ] Add Goal input is readable
[ ] long goal text does not overlap −
[ ] empty Goals state looks intentional

DARK MODE

[ ] page is visibly dark
[ ] text remains readable
[ ] inputs remain readable
[ ] selectbox remains readable
[ ] Goals editor border/surface is visible
[ ] + is visible
[ ] − is visible
[ ] focus states are visible

INTERACTION

[ ] new profile starts with Muscle Gain
[ ] Muscle Gain can be removed
[ ] removed Muscle Gain stays removed
[ ] custom goal can be added
[ ] multiple custom goals can be added
[ ] custom goal can be removed
[ ] blank goal is rejected
[ ] duplicate goal is rejected
[ ] theme can be toggled without losing temporary goals
[ ] profile A/B switching shows correct goals
[ ] Save persists current goals
[ ] browser refresh/reselect shows saved goals

GENERAL

[ ] Nutrition still works
[ ] Notes still work
[ ] Ask AI still works
[ ] no obvious layout overflow
[ ] no unreadable text
[ ] no duplicated labels

### Remaining limitations
- Automated acceptance passed, but final visual sign-off requires the manual browser checklist.
- Runtime theme preference is session-state based only and does not persist to Astra or browser localStorage.

## FIX Prompt-08 - Runtime/UI Failure Audit

### AI failure observations
- `Generate with AI` calls `ai.get_macros(...)` from the Nutrition section after building profile context and goal text from the selected profile.
- `Ask AI` calls `ai.ask_ai(...)` from the Ask AI section after building profile context and passing trusted account/profile/session identifiers.
- Both live diagnostic calls reached local Langflow and failed after Langflow started executing the graph.

### Langflow client contract
- Langflow run endpoint shape is `LANGFLOW_URL/api/v1/run/{flow_id}`.
- Requests use `input_type="chat"` and `output_type="chat"`.
- Macro flow sends the profile context as `input_value` and sends goals through the configured goals component tweak.
- Ask AI sends the question as `input_value`, profile context through the configured profile prompt tweak, and a JSON metadata filter through the configured vector-store/search component tweak.
- Current HTTP error handling raises a sanitized `LangflowHTTPError` with only the status code and does not expose the response body to the UI.

### Sanitized configuration status
- `LANGFLOW_URL`: SET, safe host `127.0.0.1`, port `7860`, scheme `http`.
- `LANGFLOW_API_KEY`: SET.
- `MACRO_FLOW_ID`: SET.
- `ASK_AI_FLOW_ID`: SET.
- `MACRO_PROFILE_COMPONENT_ID`: SET.
- `MACRO_GOALS_COMPONENT_ID`: SET.
- `ASK_PROFILE_COMPONENT_ID`: SET.
- `ASK_USER_ID_COMPONENT_ID`: SET.

### Local Langflow reachability
- Langflow root returned HTTP 200.
- `/health` returned HTTP 200 with an OK status.
- `/api/v1/version` returned HTTP 200 and reported Langflow `1.11.3`.
- `/api/v1/config` returned HTTP 200.
- `/api/v1/` returned HTTP 404, which is expected for that generic path and does not disprove run endpoint availability.

### Macro diagnostic result
- Diagnostic run: synthetic local macro request through `scripts/test_macro_flow.py`, followed by one sanitized direct POST to the configured macro flow endpoint.
- Failure layer: inside Langflow graph execution while building the OpenRouter component.
- HTTP status: Langflow returned 500 to the client.
- Sanitized error: upstream OpenRouter returned 402 because the request requires more credits or fewer max tokens.
- Proven root cause: local Langflow is reachable and the configured macro flow endpoint is executing; the macro failure is caused by upstream OpenRouter credit/token budget rejection.
- Remaining candidate causes: future failures may still occur from malformed model output, invalid flow/component tweaks, network interruption, or config drift, but those were not the observed cause of this run.

### Ask AI diagnostic result
- Diagnostic run: synthetic local Ask AI request using non-real account/profile/session IDs, followed by one sanitized direct POST to the configured Ask AI flow endpoint.
- Failure layer: inside Langflow graph execution while building the router OpenRouter model component.
- HTTP status: Langflow returned 500 to the client.
- Sanitized error: upstream OpenRouter returned 402 because the request requires more credits or fewer max tokens.
- Proven root cause: local Langflow is reachable and the configured Ask AI flow endpoint is executing; the Ask AI failure is caused by upstream OpenRouter credit/token budget rejection before downstream advice generation can complete.
- Remaining candidate causes: vector-store filtering, profile tweak shape, downstream advice prompt behavior, malformed model output, and config drift remain candidates for separate future issues because this run failed earlier at the router model.

### Error-handling findings
- The app currently shows generic AI failure text and logs a sanitized exception path through the existing `LangflowHTTPError`.
- `ai.run_flow` intentionally discards Langflow response bodies on HTTP errors, so the Streamlit UI cannot distinguish local Langflow downtime, missing flow IDs, upstream provider billing failures, provider rate limits, or invalid graph configuration.
- Recommended safe distinctions: separate configuration errors, local connection errors, Langflow 4xx/5xx graph errors, upstream provider billing/quota errors, timeout errors, and response-shape/JSON-parse errors without displaying secrets or raw provider payloads.

### Current top-right header structure
- The theme toggle renders near the top-right before authentication initialization.
- The authenticated header later renders signed-in account text and a Logout button.
- Create profile remains inside the Profile section tab UI, not in the top-right header.
- Recommended future header order: Theme toggle, Create Profile entry point, Logout.

### Desired header structure
- Keep the runtime theme control first.
- Add a compact top-right Create Profile action after the theme control.
- Keep Logout last.
- Avoid toolbar collision by using one shared header row instead of separate top-right column groups rendered at different points in startup.

### Current profile workflow
- The Profile section shows a selector for the active profile.
- The selected profile summary currently shows profile ID, activity, and goals count.
- Create profile is always available in a tab beside Edit selected.
- Edit selected is always present when a selected profile exists and saves directly through the existing profile service boundary.

### Desired profile workflow
- Select a profile first.
- Show a concise selected-profile summary.
- Enter edit mode explicitly.
- Save or cancel edits without mixing create and edit forms in adjacent always-visible tabs.
- Keep persistence limited to the profile service layer.

### Goal tooltip findings
- The current help mechanism is Streamlit button `help` text on the add and remove goal form submit buttons.
- Light-mode issue to verify visually: tooltip/popover contrast may be weak against the custom light theme tokens.
- Dark-mode issue to verify visually: tooltip/popover contrast may be weak or inconsistent if Streamlit renders it outside the themed form container.
- Probable CSS cause: runtime CSS customizes broad Streamlit button, input, select, radio, expander, tab, and tooltip selectors while Streamlit tooltip markup can vary by version.
- Stable fix strategy: style only documented/stable wrapper scopes where possible, keep tooltip colors tokenized for both themes, and prefer robust labels/ARIA help over brittle generated class selectors.

### Theme CSS findings
- The runtime theme uses CSS custom properties generated from `UI_THEME_TOKENS`.
- Light and dark themes share the same token names.
- The CSS avoids generated hash class selectors and private Streamlit theme mutation.
- Risk remains around broad selectors affecting future Streamlit markup, especially tooltips and header-adjacent controls.

### Session-state risks
- Theme state is session-only and does not persist across a fresh browser session.
- Goals editor state is form/session driven and intentionally does not persist until Create Profile or Save changes is submitted.
- Multiple top-level rerun triggers are present, so future header/profile workflow changes should preserve selected profile, temporary goals, nutrition draft, notes state, and Ask AI history.
- Create and edit form keys are distinct, reducing direct state collision risk.

### Test gaps
- Existing tests cover option contracts, legacy profile values, goals add/remove state, theme token behavior, persistence boundaries, AI client behavior with mocked requests, and broad app resilience.
- Missing tests: live Langflow/OpenRouter provider error classification, top-right header ordering, create-profile header action state flow, save/cancel edit workflow, and tooltip contrast/visibility in light and dark themes.

### Recommended milestone scope
- FIX Prompt-09: implement safe AI error classification and user-facing distinctions without exposing secrets.
- FIX Prompt-10: consolidate the top-right header into a single Theme -> Create Profile -> Logout control row.
- FIX Prompt-11: simplify the profile workflow to Select -> Summary -> Edit -> Save/Cancel.
- FIX Prompt-12: harden goal tooltip styling and accessibility across light/dark themes.
- FIX Prompt-13: add regression coverage for the new header/profile/tooltip/error-handling behavior and run final release readiness checks.

### Baseline verification
- Application source and tests were not intentionally changed for this audit.
- The only intended repository change for FIX Prompt-08 is this documentation update.
- Safe verification commands are listed in the final audit response.
