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

## FIX Prompt-09 — AI Error Classification

### Confirmed runtime architecture
- Macro path remains Streamlit -> `ai.get_macros(...)` -> Langflow -> OpenRouter.
- Ask AI path remains Streamlit -> `ai.ask_ai(...)` -> Langflow -> OpenRouter router/advice flow.
- The application still does not call OpenRouter directly.

### Proven external failure
- Live synthetic Macro and Ask AI diagnostics reached local Langflow after it was started on `127.0.0.1:7860`.
- Both live diagnostics failed inside Langflow because the upstream OpenRouter request reported HTTP 402.
- The application-side classification now reports this as provider billing/quota/token-budget failure rather than a generic Langflow HTTP failure.

### Error classes / categories
- Configuration: `LangflowConfigError`.
- Connection: `LangflowConnectionError`.
- Timeout: `LangflowTimeoutError`.
- Generic Langflow HTTP/graph failure: `LangflowHTTPError`.
- Provider billing/quota/token-budget failure: `ProviderQuotaError`.
- Response format/shape failure: `LangflowResponseError`.
- Macro parsing failure remains a nutrition parse failure after a response is received.

### Sanitization strategy
- Langflow HTTP failures now retain `status_code`, a capped `diagnostic_summary`, and optional `provider_status`.
- Diagnostic summaries are capped and compacted.
- API key values, auth header values, fake secret markers, credentialed URLs, Astra-style tokens, and user IDs in provider payloads are redacted.
- Full request payloads, prompts, profile context, auth headers, and complete response bodies are not surfaced in UI messages.

### Macro UI message
- Provider quota/billing failures display an actionable OpenRouter credit/token-budget message.
- Macro parsing failures display a distinct message that the AI response was received but the nutrition output was not valid.
- Generic Langflow HTTP, configuration, connection, timeout, and response-format failures remain distinguishable.

### Ask AI UI message
- Provider quota/billing failures display the same actionable OpenRouter credit/token-budget message.
- Generic Langflow HTTP, configuration, connection, timeout, and response-format failures remain distinguishable.
- Raw exception class names and provider payloads are not the primary user-facing explanation.

### Live Macro diagnostic
- Safe synthetic macro diagnostic was run against local Langflow.
- Result: `ProviderQuotaError`.
- Langflow status: 500.
- Provider status: 402.
- Successful macro generation remains blocked by the external OpenRouter credit/token-budget condition.

### Live Ask AI diagnostic
- Safe synthetic Ask AI diagnostic was run against local Langflow with non-real account/profile/session IDs.
- Result: `ProviderQuotaError`.
- Langflow status: 500.
- Provider status: 402.
- Successful Ask AI generation remains blocked by the external OpenRouter credit/token-budget condition.

### Provider remediation required
- The user must either ensure the OpenRouter account/key used by Langflow has sufficient usable credit/budget, or reduce the configured model output/max-token budget in the relevant Langflow OpenRouter component.
- No numeric token setting was chosen automatically.
- No model switch, OpenRouter account change, or Langflow flow edit was made.

### External blocker status
- AI application error handling: PASS.
- Live AI provider success: BLOCKED BY OPENROUTER 402.

### Backend impact
- `profiles.py`: unchanged.
- `db.py`: unchanged.
- Astra schema/data: unchanged.
- Langflow flow JSON: unchanged.
- Flow IDs/component IDs: unchanged.
- Requirements/dependencies: unchanged.

### Ready for FIX Prompt-10
- yes, after final Prompt-09 verification remains green.

## FIX Prompt-10 — Unified Top-Right Header

### Previous header structure
- Theme control rendered separately before authentication/session initialization.
- Signed-in account status and Logout rendered later through the authenticated header.
- Create Profile was available through the Profile section's Create profile tab.
- The application had separate header-like action areas instead of one coherent action row.

### New header structure
- Authenticated application action row now renders in one native Streamlit column layout.
- Action order is Theme -> Create Profile -> Logout.
- Logout is the furthest-right application action.
- The row renders after page setup/theme injection/authentication/session initialization and before the main Profile/Nutrition/Notes/Ask AI controls.

### Account status placement
- Signed-in username remains visible in the left side of the unified application header row.
- Internal account IDs are not displayed.

### Streamlit toolbar separation strategy
- The application action row stays in normal Streamlit content flow.
- No Streamlit Deploy/menu toolbar hiding or DOM manipulation was added.
- No JavaScript, fixed positioning, absolute positioning, or generated class hash selectors were added.

### Theme behavior
- The existing `ui_theme` session key, allowed values, default, and toggle logic are preserved.
- Light mode still presents `🌙 Dark`.
- Dark mode still presents `☀️ Light`.
- Theme toggling does not submit forms or persist profile data.

### Create Profile navigation/state
- A small `profile_ui_mode` session key controls whether the Profile section shows selected/edit mode or create mode.
- Clicking the top-row Create Profile button enters create mode without touching Astra or profile persistence.
- Create mode uses the existing `_render_profile_form(mode="create")` implementation and the existing `profiles.create_new_profile(...)` service path on submit.
- New-profile goal initialization remains `["Muscle Gain"]` once per create editor state.

### Cancel/back behavior
- Create mode includes `Back to selected profile`.
- Back exits create mode, clears unsaved create-form state, and preserves the selected stored profile, authentication, and theme.
- Back does not save, logout, or alter backend state.

### Successful create behavior
- Successful create still calls `profiles.create_new_profile(...)`.
- After create, profiles are refreshed with the new profile selected, create form state is cleared, and `profile_ui_mode` returns to selected mode.

### Logout behavior
- Logout is rendered in the same application action group and remains last.
- Existing logout semantics are preserved through `_reset_session_for_logout()`.
- Temporary authenticated/session data is cleared according to the existing security contract.

### Responsive strategy
- The header uses native `st.columns((4, 2, 1, 1.6, 1), vertical_alignment="center")`.
- It avoids fixed desktop coordinates and horizontal overlay positioning.
- Controls remain normal Streamlit buttons with native keyboard behavior.

### Theme visibility
- Header buttons reuse the centralized runtime theme button styling.
- Light and dark token contracts remain unchanged.
- No separate CSS system was added for the header.

### Tests
- Added/updated tests for header action order, logout-last placement, header-before-profile rendering, theme toggle behavior, Create Profile mode entry, no persistence on create entry, create default goals, theme/create-mode preservation, cancel/back behavior, successful create service path, removal of old Create profile tab navigation, static toolbar/JavaScript safety, and Prompt-09 AI message preservation.

### Manual verification
- Automated startup check is required for Prompt-10.
- Authenticated visual header verification may require user browser sign-off if credentials/session automation is not available.

### Ready for FIX Prompt-11
- yes, if final Prompt-10 verification remains green.

## FIX Prompt-11 — Selected Profile View/Edit Workflow

### Previous profile workflow
- After FIX Prompt-10, the global header contained Theme -> Create Profile -> Logout.
- The Profile section still rendered the selected profile edit form immediately after selection.
- Existing selected profiles therefore opened directly into editable inputs instead of a read-only summary.

### New mode contract
- `view`: selected profile is displayed as a read-only summary, or a no-profile message is shown.
- `edit`: selected profile edit form is displayed after the contextual Edit Profile action.
- `create`: new profile form is displayed after the header Create Profile action.
- Invalid or missing mode normalizes to `view`.

### Selected profile summary
- Fields: Name, Age, Weight, Height, Gender, Activity Level, Goals.
- Layout: read-only native Streamlit summary below the Active profile selector.
- Goals behavior: saved goals are displayed in stored order without normalization/mapping; empty existing goals show `No goals added.` and do not inject `Muscle Gain`.
- The summary uses the current `selected_profile` data rather than a second independent profile-summary data structure.

### Internal profile ID presentation
- The internal profile ID remains in session/profile data for selection, Notes, Ask AI, and ownership/RAG isolation.
- The ID is not editable and is no longer prominently displayed in the normal selected-profile summary.

### Edit Profile behavior
- The contextual Edit Profile button sets `profile_ui_mode` to `edit`.
- Clicking Edit Profile does not persist, does not change the selected profile, and clears stale edit-form state before the form is initialized from the selected stored profile.
- Gender remains `st.radio`, Activity Level remains `st.selectbox`, and Goals remain the dynamic add/remove editor.
- Legacy gender, activity, and custom goal values remain representable.

### Save behavior
- Save Changes remains the explicit edit persistence boundary.
- Successful saves use `profiles.save_profile_changes(...)`, refresh the selected profile, set `profile_ui_mode` to `view`, and preserve the current theme.
- No direct `db.py` write path was added in `main.py`.

### Cancel behavior
- Edit mode includes a secondary Cancel action beside Save Changes.
- Cancel exits to `view`, clears temporary edit form/goal state, preserves the selected stored profile and theme, and performs no persistence.
- Re-entering edit mode initializes from the stored selected profile again.

### Profile-switch behavior
- Selecting a different profile uses the existing profile service read path and sets `profile_ui_mode` to `view`.
- Stale edit-specific widget and goal state is cleared during selection changes.
- Unsaved edits from one profile are not saved and do not leak into another profile.

### Create-mode integration
- Header Create Profile still enters `create`.
- Create mode still uses the existing create profile form and service path.
- New-profile default goals remain `["Muscle Gain"]` once per create editor state.
- Back to selected profile and successful create both return to `view`.

### Theme integration
- Theme implementation and header order were not changed for FIX Prompt-11.
- Theme toggles preserve `view`, `edit`, or `create` mode and temporary edit/create goal state.

### Persistence boundaries
- Selecting a profile reads the selected profile but does not save profile edits.
- Edit Profile only changes UI mode.
- Temporary edit changes remain session/form state.
- Cancel discards temporary edit state without saving.
- Save Changes persists through `profiles.py`.
- Header Create Profile only changes UI mode until the create form is submitted.

### Tests
- Added/updated tests for view-mode default, read-only summary fields, hidden edit controls in view mode, empty goal summary, profile ID presentation, Edit Profile mode entry, edit initialization with legacy values, edit Save/Cancel buttons, theme preservation, cancel restore behavior, profile switching from edit, create/header regressions, logout/header regressions, and Prompt-09 AI regression.

### Manual verification
- Automated startup check is required for Prompt-11.
- Authenticated visual profile verification may require user browser sign-off if credentials/session automation is not available.

### Ready for FIX Prompt-12
- yes, if final Prompt-11 verification remains green.

## FIX Prompt-12 — Goal Tooltip Readability

### Defect
- Hovering the Goal remove control rendered Streamlit's native tooltip with unreadable contrast after the app theme CSS was applied.
- The same risk applied to Goal add controls because they also use Streamlit native `help`.

### Root cause
- The runtime theme CSS included broad global text selectors for `label`, `p`, and `span`.
- Those selectors could affect Streamlit tooltip portal content outside the intended app content area.

### Fix
- Removed the broad global text selector leak and scoped text color rules to Streamlit content containers.
- Added explicit light/dark tooltip tokens: `tooltip_background`, `tooltip_text`, and `tooltip_border`.
- Styled only the verified native tooltip role selector, `[role="tooltip"]`, and its descendants.
- Kept Goal `+`, `Add Goal`, and `−` tooltips on Streamlit native `help` strings.

### Theme behavior
- Light and dark themes define the same tooltip token names.
- Tooltip text/background contrast is tested at WCAG 4.5:1 or higher in both themes.
- Theme toggles still preserve dynamic Goal editor state.

### Safety
- No generated Streamlit class selectors were added.
- No JavaScript, `components.html`, or unsafe custom tooltip HTML was added.
- No profile IDs, account IDs, session keys, database IDs, or widget keys are exposed in Goal tooltip copy.

### Preserved behavior
- Goal add/remove callbacks and ordering are unchanged.
- Goal changes remain session-local until Profile Save/Create submit.
- View mode still renders no Goal editor controls.
- Create and edit modes still render the dynamic Goal editor.
- Header order and Prompt-09 AI error classification are unchanged.

### Tests
- Added/updated tests for tooltip token contract and contrast.
- Added/updated tests for CSS selector safety and removal of global `label, p, span` leakage.
- Added/updated tests for native public help strings on Goal `+`, `Add Goal`, and `−`, including long/special-character goal text.
- Existing regression tests continue to cover Goal add/remove behavior, non-persistence, list typing, view/edit/create profile flow, header order, theme state preservation, and ProviderQuotaError handling.

### Manual verification
- manual authenticated tooltip verification: NOT RUN — requires user browser sign-off

### Ready for FIX Prompt-13
- not started.

### FIX Prompt-13 Manual Browser Sign-Off Checklist

HEADER

[ ] Theme is visible
[ ] Create Profile is visible
[ ] Logout is visible
[ ] order is Theme -> Create Profile -> Logout
[ ] Logout is furthest right
[ ] app controls do not collide with Streamlit Deploy/menu

LIGHT MODE

[ ] page is clearly light
[ ] header buttons readable
[ ] profile summary readable
[ ] inputs readable
[ ] + readable
[ ] − readable
[ ] − tooltip readable
[ ] + tooltip readable
[ ] focus states visible

DARK MODE

[ ] page is clearly dark
[ ] header buttons readable
[ ] profile summary readable
[ ] inputs readable
[ ] + readable
[ ] − readable
[ ] − tooltip readable
[ ] + tooltip readable
[ ] focus states visible

PROFILE VIEW

[ ] selecting a profile shows summary
[ ] Name visible
[ ] Age visible
[ ] Weight visible
[ ] Height visible
[ ] Gender visible
[ ] Activity Level visible
[ ] Goals visible
[ ] edit fields are NOT immediately shown
[ ] internal profile ID is not prominent

PROFILE EDIT

[ ] Edit Profile opens editable form
[ ] Gender radio correct
[ ] Activity selectbox correct
[ ] Goals +/− editor correct
[ ] unsaved edits survive theme toggle
[ ] Cancel returns to saved summary
[ ] Save returns to updated summary

PROFILE CREATE

[ ] top-right Create Profile opens create form
[ ] default Muscle Gain appears once
[ ] Muscle Gain can be removed
[ ] removed default stays removed
[ ] custom goal can be added
[ ] blank rejected
[ ] duplicate rejected
[ ] Back/cancel does not persist
[ ] successful create returns to profile summary

PROFILE SWITCHING

[ ] A -> B shows B summary
[ ] B -> A shows A summary
[ ] unsaved edit from A does not appear in B
[ ] switching while editing does not auto-save

AI

[ ] Generate with AI shows actionable OpenRouter message while 402 persists
[ ] Ask AI shows actionable OpenRouter message while 402 persists

If provider issue is manually fixed:

[ ] Macro generation succeeds
[ ] Ask AI succeeds

GENERAL

[ ] Nutrition UI still works
[ ] Notes UI still works
[ ] Ask AI UI still works
[ ] Logout works
[ ] no obvious horizontal overflow
[ ] no duplicated labels/buttons
[ ] no unreadable tooltip
[ ] no obviously broken Light/Dark styles

## FIX Prompt-13 — Final Corrective Acceptance

### Final fixed scope
- Final integrated regression covered FIX Prompts 09-12 together.
- One dead staged UI helper, `_render_theme_control()`, was removed because the active header now owns the only theme action path.
- No new feature was added.

### Header acceptance
- The active authenticated header is one native `st.columns((4, 2, 1, 1.6, 1), vertical_alignment="center")` row.
- Right-side action order remains Theme -> Create Profile -> Logout.
- Logout is the last application action in the row.
- No Streamlit toolbar hiding, fixed/absolute overlay, JavaScript, or generated class selector is used.

### Profile view/edit/create acceptance
- Profile UI modes remain `view`, `edit`, and `create`.
- Selected authenticated profiles default to `view`.
- Edit Profile enters `edit` without persistence.
- Cancel and successful Save return to `view`.
- Header Create Profile enters `create` without persistence.
- Back/cancel create and successful create return to `view`.
- Profile switching returns to `view` and clears stale edit-specific state.
- Edit mode with no selected profile is normalized back to `view`.

### Goals acceptance
- New create forms initialize `["Muscle Gain"]` once per fresh create editor state.
- Removing the starter goal keeps it removed across reruns and theme toggles.
- Existing profiles load stored goals exactly.
- Arbitrary custom goals remain supported as `list[str]`.
- Blank additions are rejected, exact duplicates are rejected, and all goals may be removed.
- Goal add/remove controls remain temporary session-state actions until Create Profile or Save Changes.

### Tooltip acceptance
- Goal `+`, `Add Goal`, and `−` controls use native Streamlit `help`.
- Tooltip styling is scoped to verified `[role="tooltip"]` for installed Streamlit 1.61.1.
- Light and dark tooltip tokens satisfy the tested readable contrast target.
- No generated/hash selector, nth-child hack, JavaScript, or custom tooltip HTML was added.
- Tooltip help text does not expose profile IDs, account IDs, widget keys, or session keys.

### Theme acceptance
- `ui_theme` defaults to `light`, preserves valid values, and normalizes invalid values to `light`.
- Toggle behavior remains `light -> dark` and `dark -> light`.
- Theme toggles preserve authentication, selected profile, profile mode, temporary create/edit Goals, nutrition, notes, and Ask AI state.
- No private Streamlit theme API or runtime `config.toml` mutation is used.

### AI error-handling acceptance
- Runtime architecture remains Streamlit -> `ai.py` -> Langflow -> OpenRouter.
- Upstream OpenRouter 402 evidence inside Langflow HTTP 500 is classified as `ProviderQuotaError`.
- Macro and Ask AI user messages explain the OpenRouter credit/token budget issue without raw exception, key, header, or payload leaks.
- 401/403/404/generic 500, timeout, connection, and response-shape errors remain separate categories.

### External OpenRouter status
- Local Langflow reachability was confirmed at `http://127.0.0.1:7860`.
- Live OpenRouter success was not re-tested during this final milestone.
- OpenRouter provider HTTP 402 is an external provider/account/token-budget condition if still present.
- The application should not be called defective solely because provider billing or token budget remains blocked.

### Nutrition regression
- Existing tests verify Nutrition section rendering, `ai.get_macros` usage, ProviderQuotaError message mapping, and manual nutrition save behavior.
- No Goal/header/profile change altered the Nutrition persistence path.

### Notes regression
- Existing tests verify Notes rendering guards, add behavior, delete behavior, and account/profile isolation.
- No destructive live note test was performed.

### Ask AI regression
- Existing tests verify Ask AI rendering guards, selected profile context, account/profile/session arguments, flow/tweak path, ProviderQuotaError message mapping, and state preservation across theme toggles.

### Authentication/logout regression
- Existing tests verify logout clears authenticated/session state according to the current contract and does not trigger profile, notes, or AI backends.

### Safe test discovery
- Test files in `tests/` are safe unit/mock/local tests.
- Astra, Langflow, and OpenRouter clients are faked or monkeypatched in test code.
- No external/live or destructive tests were skipped from the safe suite.

### Automated verification
- Focused acceptance tests: 142 passed.
- Full safe suite: 367 passed.
- Compile verification: passed.
- `git diff --check`: passed.
- Static safety search: expected stable selectors, secret variable names, test assertions, and docs only.

### Startup verification
- Headless Streamlit startup on `127.0.0.1:8504` started successfully.
- HTTP endpoint responded with `200 OK`.
- No immediate Python exception was observed.
- The smoke process was stopped after verification.

### Static safety review
- No conflict markers, breakpoints, `pdb.set_trace`, active debug hooks, JavaScript injection, private Streamlit theme API, generated class selector, toolbar hiding, or fixed/absolute overlay were found in runtime code.
- Secret-related variable/header names are used for normal configuration, auth construction, sanitization, or tests.
- No evidence was found that secrets or raw sensitive payloads are dumped to users.

### Manual Browser Sign-Off Checklist
- Checklist is recorded above under `### FIX Prompt-13 Manual Browser Sign-Off Checklist`.
- Authenticated browser sign-off remains pending.

### Remaining limitations
- Authenticated visual browser checks remain manual because browser automation was unavailable in this Codex session and no authenticated user session was provided.
- Live AI success depends on Langflow/OpenRouter provider account state.
- OpenRouter provider HTTP 402 remains an external provider/account/token-budget limitation if it still occurs.

## FIX Prompt-14 — Light Contrast and Header Safe-Zone

### Manual defects observed
- The app-owned Theme, Create Profile, and Logout action row rendered too close to Streamlit's platform chrome in both themes.
- Light mode had reported weak readability on some foreground/background combinations, especially strongly colored primary actions such as Generate with AI.

### Header clipping root cause
- `_apply_ui_theme()` set `[data-testid="stMainBlockContainer"] { padding-top: 1.5rem; }`.
- That centralized rule reduced the normal top safe area enough for the first app row to sit under or too near Streamlit's fixed upper chrome.

### Header safe-zone strategy
- Restored a modest rem-based safe zone by increasing the main block top padding to `4.5rem`.
- This moves the entire app-owned first row lower without placing anything into or over the Streamlit platform toolbar.
- No large spacer, fixed overlay, absolute overlay, transform, or JavaScript positioning was added.

### Header selector / scope
- Selector used: `[data-testid="stMainBlockContainer"]`.
- This is the existing stable Streamlit main content container already used by the app theme CSS.
- No generated `.css-*` or `st-emotion-cache-*` selector is used.

### Streamlit chrome preservation
- Streamlit Share/menu/toolbar chrome remains untouched.
- No `display: none`, `visibility: hidden`, opacity-hiding, fixed positioning, or absolute positioning is used against Streamlit chrome.

### Light-mode contrast audit
- Audited light tokens for text/background, text/surface, muted/background, muted/surface, input text/input background, button text/primary background, button text/primary hover, secondary text/surface-alt, secondary text/input-hover, and tooltip text/background.
- All audited normal text pairs meet or exceed the 4.5:1 test target.
- Border tokens remain subtle by design and are not used as normal foreground text.

### Tokens changed
- No token values were changed.
- The declared light `button_text` value already provides high contrast against `button_background` and `button_hover`.

### Primary button foreground fix
- Primary styling now covers Streamlit form-submit primary buttons with `button[kind="primaryFormSubmit"]` in addition to normal `button[kind="primary"]`.
- This keeps strongly colored primary actions on `--fit-button-background` / `--fit-button-hover` with `--fit-button-text`.

### Muted/text/input contrast
- Light text, muted text, and input text/background pairs are covered by contrast tests.
- Input, selectbox, radio, caption, profile summary, section, and button text scopes remain centralized and narrow.

### Dark-mode regression result
- The same contrast test set runs for dark mode.
- Dark mode text, muted text, inputs, primary buttons, secondary buttons, and tooltip contrast remain readable by the test contract.

### Tooltip regression result
- The FIX Prompt-12 `[role="tooltip"]` strategy remains intact.
- Tooltip text/background contrast remains covered for both themes.
- Broad `label, p, span` color leakage was not reintroduced.

### Functional behavior preserved
- Header action order remains Theme -> Create Profile -> Logout.
- Profile view/edit/create semantics are unchanged.
- Goals behavior and temporary-state semantics are unchanged.
- Nutrition, Notes, Ask AI, AI error handling, Langflow flow JSON, Astra, backend modules, and requirements are unchanged.

### Tests
- Added/updated tests for broad light/dark contrast pairs.
- Added/updated tests for the header safe-zone CSS contract.
- Added/updated tests for primary form-submit button foreground coverage.
- Existing header order, profile flow, Goals, tooltip, theme state, and AI regression tests remain active.

### Manual browser verification
- manual authenticated Light/Dark verification: NOT RUN — requires user browser sign-off

### Ready for final manual sign-off
- yes, pending user visual recheck in an authenticated browser session.
