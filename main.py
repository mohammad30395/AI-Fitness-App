import logging
import re

import streamlit as st

import ai
import config
import db
import profiles


logger = logging.getLogger(__name__)

SESSION_DEFAULTS = {
    "selected_profile_id": None,
    "selected_profile": None,
    "profiles": [],
    "nutrition": None,
    "nutrition_draft": None,
    "nutrition_draft_profile_id": None,
    "nutrition_draft_version": 0,
    "last_ai_answer": "",
    "ui_error": None,
    "profile_success": None,
    "macro_success": None,
    "macro_error": None,
    "notes": [],
    "notes_profile_id": None,
    "notes_success": None,
    "notes_error": None,
    "confirm_delete_note_id": None,
    "ask_ai_error": None,
}


def _sanitize_diagnostic(message: str) -> str:
    sanitized = str(message)
    for name in config.ALL_VARIABLES:
        value = config.get_env_value(name)
        if value and len(value) >= 4:
            sanitized = sanitized.replace(value, f"<redacted:{name}>")
    sanitized = re.sub(r"AstraCS:[A-Za-z0-9._:-]+", "<redacted:ASTRA_TOKEN>", sanitized)
    sanitized = re.sub(r"sk-[A-Za-z0-9._-]+", "<redacted:API_KEY>", sanitized)
    sanitized = re.sub(r"(https?://)([^/@\s]+):([^/@\s]+)@", r"\1<redacted>@", sanitized)
    return sanitized


def _record_ui_failure(action: str, error: Exception) -> None:
    logger.warning(
        "%s failed: %s: %s",
        action,
        type(error).__name__,
        _sanitize_diagnostic(str(error)),
    )


def _default_session_value(value):
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return dict(value)
    return value


def initialize_session_state() -> None:
    for key, value in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = _default_session_value(value)


def _goals_from_text(goals_text: str) -> list[str]:
    normalized = goals_text.replace(",", "\n")
    return [goal.strip() for goal in normalized.splitlines() if goal.strip()]


def _goals_to_text(profile: dict) -> str:
    goals = profile.get("goals", [])
    if not isinstance(goals, list):
        return str(goals)
    return "\n".join(str(goal) for goal in goals)


def _safe_profile_error(action: str, error: Exception) -> str:
    return f"{action} failed ({type(error).__name__}). Check profile fields and database configuration."


def _safe_macro_error(action: str, error: Exception) -> str:
    return f"{action} failed ({type(error).__name__}). Check Langflow configuration and macro output."


def _safe_notes_error(action: str, error: Exception) -> str:
    return f"{action} failed ({type(error).__name__}). Check note text and Astra notes configuration."


def _safe_ask_ai_error(action: str, error: Exception) -> str:
    return f"{action} failed ({type(error).__name__}). Check Langflow Ask AI configuration and try again."


def _profile_label(profile_id) -> str:
    for profile in st.session_state.get("profiles", []):
        if str(profile.get("_id")) == str(profile_id):
            name = profile.get("name") or "Unnamed profile"
            return f"{name} ({profile_id})"
    return str(profile_id)


def _copy_nutrition(nutrition):
    if isinstance(nutrition, dict) and nutrition:
        return dict(nutrition)
    return None


def _set_selected_profile(profile: dict | None) -> None:
    st.session_state["selected_profile"] = profile
    stored_nutrition = _copy_nutrition(profile.get("nutrition")) if profile else None
    st.session_state["nutrition"] = stored_nutrition
    _set_nutrition_draft(profile.get("_id") if profile else None, stored_nutrition)
    st.session_state["notes"] = []
    st.session_state["notes_profile_id"] = None
    st.session_state["confirm_delete_note_id"] = None


def _set_nutrition_draft(profile_id, nutrition) -> None:
    st.session_state["nutrition_draft"] = _copy_nutrition(nutrition)
    st.session_state["nutrition_draft_profile_id"] = profile_id
    st.session_state["nutrition_draft_version"] = (
        int(st.session_state.get("nutrition_draft_version") or 0) + 1
    )


def _refresh_profiles(select_profile_id=None) -> bool:
    try:
        profile_list = profiles.get_all_profiles()
        st.session_state["profiles"] = profile_list

        if select_profile_id is not None:
            st.session_state["selected_profile_id"] = select_profile_id
        elif st.session_state.get("selected_profile_id") is None and profile_list:
            st.session_state["selected_profile_id"] = profile_list[0].get("_id")

        selected_id = st.session_state.get("selected_profile_id")
        if selected_id is not None:
            _set_selected_profile(profiles.get_profile_by_id(selected_id))
        else:
            _set_selected_profile(None)

        st.session_state["ui_error"] = None
        return True
    except Exception as error:
        _record_ui_failure("Loading profiles", error)
        st.session_state["ui_error"] = _safe_profile_error("Loading profiles", error)
        st.session_state["profiles"] = []
        _set_selected_profile(None)
        return False


def _refresh_notes(user_id: str) -> bool:
    try:
        st.session_state["notes"] = db.list_notes(user_id, limit=50)
        st.session_state["notes_profile_id"] = user_id
        st.session_state["notes_error"] = None
        return True
    except Exception as error:
        _record_ui_failure("Loading notes", error)
        st.session_state["notes"] = []
        st.session_state["notes_profile_id"] = None
        st.session_state["notes_error"] = _safe_notes_error("Loading notes", error)
        return False


def _profile_form_defaults(profile: dict | None = None) -> dict:
    profile = profile or {}
    return {
        "name": str(profile.get("name") or ""),
        "age": int(profile.get("age") or 30),
        "weight": float(profile.get("weight") or 70.0),
        "height": float(profile.get("height") or 170.0),
        "gender": str(profile.get("gender") or ""),
        "activity_level": str(profile.get("activity_level") or ""),
        "goals": _goals_to_text(profile),
    }


def _render_profile_form(*, mode: str, profile: dict | None = None) -> None:
    defaults = _profile_form_defaults(profile)
    is_edit = mode == "edit"
    form_key = "edit_profile_form" if is_edit else "create_profile_form"
    submit_label = "Save changes" if is_edit else "Create profile"

    with st.form(form_key):
        name = st.text_input("Name", value=defaults["name"], key=f"{form_key}_name")
        age = st.number_input(
            "Age",
            min_value=1,
            step=1,
            value=defaults["age"],
            key=f"{form_key}_age",
        )
        weight = st.number_input(
            "Weight",
            min_value=0.1,
            step=0.1,
            value=defaults["weight"],
            key=f"{form_key}_weight",
        )
        height = st.number_input(
            "Height",
            min_value=0.1,
            step=0.1,
            value=defaults["height"],
            key=f"{form_key}_height",
        )
        gender = st.text_input("Gender", value=defaults["gender"], key=f"{form_key}_gender")
        activity_level = st.text_input(
            "Activity level",
            value=defaults["activity_level"],
            key=f"{form_key}_activity_level",
        )
        goals_text = st.text_area(
            "Goals",
            value=defaults["goals"],
            placeholder="Build strength\nImprove endurance",
            key=f"{form_key}_goals",
        )

        submitted = st.form_submit_button(submit_label)

    if not submitted:
        return

    profile_payload = {
        "name": name,
        "age": int(age),
        "weight": float(weight),
        "height": float(height),
        "gender": gender,
        "activity_level": activity_level,
        "goals": _goals_from_text(goals_text),
    }

    try:
        if is_edit:
            profile_id = st.session_state.get("selected_profile_id")
            if not profile_id:
                raise ValueError("No profile selected")
            updated_profile = profiles.save_profile_changes(profile_id, **profile_payload)
            st.session_state["selected_profile_id"] = updated_profile.get("_id", profile_id)
            st.session_state["selected_profile"] = updated_profile
            _refresh_profiles(st.session_state["selected_profile_id"])
            st.session_state["profile_success"] = "Profile updated."
        else:
            new_profile_id = profiles.create_new_profile(**profile_payload)
            _refresh_profiles(new_profile_id)
            st.session_state["profile_success"] = "Profile created."
        st.session_state["ui_error"] = None
        st.rerun()
    except Exception as error:
        _record_ui_failure("Saving profile", error)
        st.session_state["profile_success"] = None
        st.session_state["ui_error"] = _safe_profile_error("Saving profile", error)
        st.rerun()


def render_profile_section() -> None:
    st.header("Profile")
    with st.container(border=True):
        if not st.session_state.get("profiles") and st.session_state.get("ui_error") is None:
            _refresh_profiles()

        if st.button("Refresh profiles"):
            _refresh_profiles()
            st.rerun()

        profile_list = st.session_state.get("profiles", [])
        profile_ids = [profile.get("_id") for profile in profile_list if profile.get("_id")]

        if profile_ids:
            current_id = st.session_state.get("selected_profile_id")
            current_index = 0
            for index, profile_id in enumerate(profile_ids):
                if str(profile_id) == str(current_id):
                    current_index = index
                    break

            selected_id = st.selectbox(
                "Select existing profile",
                options=profile_ids,
                index=current_index,
                format_func=_profile_label,
            )

            if str(selected_id) != str(st.session_state.get("selected_profile_id")):
                try:
                    st.session_state["selected_profile_id"] = selected_id
                    _set_selected_profile(profiles.get_profile_by_id(selected_id))
                    st.session_state["ui_error"] = None
                    st.rerun()
                except Exception as error:
                    _record_ui_failure("Selecting profile", error)
                    st.session_state["ui_error"] = _safe_profile_error("Selecting profile", error)
                    st.rerun()
        else:
            st.info("No profiles found yet. Create one below.")

        selected_profile = st.session_state.get("selected_profile")
        if selected_profile:
            st.caption(f"Selected profile ID: {selected_profile.get('_id')}")

        create_tab, edit_tab = st.tabs(["Create", "Edit selected"])
        with create_tab:
            _render_profile_form(mode="create")

        with edit_tab:
            if selected_profile:
                _render_profile_form(mode="edit", profile=selected_profile)
            else:
                st.write("Select or create a profile before editing.")


def render_nutrition_section() -> None:
    st.header("Nutrition / Macros")
    with st.container(border=True):
        selected_profile = st.session_state.get("selected_profile")
        if not selected_profile:
            st.info("Select or create a profile before generating nutrition targets.")
            return

        st.caption("Generated targets are approximate general fitness guidance.")

        nutrition = st.session_state.get("nutrition")
        if nutrition:
            st.subheader("Stored targets")
            calories, protein, fat, carbs = st.columns(4)
            calories.metric("Calories", f"{nutrition.get('calories', '-')} kcal/day")
            protein.metric("Protein", f"{nutrition.get('protein', '-')} g/day")
            fat.metric("Fat", f"{nutrition.get('fat', '-')} g/day")
            carbs.metric("Carbs", f"{nutrition.get('carbs', '-')} g/day")
        else:
            st.write("No nutrition targets are saved for this profile yet.")

        if st.session_state.get("macro_success"):
            st.success(st.session_state["macro_success"])
        if st.session_state.get("macro_error"):
            st.error(st.session_state["macro_error"])

        if st.button("Generate with AI"):
            try:
                profile_context = profiles.build_profile_context(selected_profile)
                goals = _goals_to_text(selected_profile).strip() or "No specific goals provided."
                with st.spinner("Generating approximate macro targets..."):
                    generated_nutrition = ai.get_macros(profile_context, goals)
                _set_nutrition_draft(selected_profile.get("_id"), generated_nutrition)
                st.session_state["macro_success"] = (
                    "AI suggestions generated. Review and save to apply them."
                )
                st.session_state["macro_error"] = None
                st.rerun()
            except Exception as error:
                _record_ui_failure("Generating macros", error)
                st.session_state["macro_success"] = None
                st.session_state["macro_error"] = _safe_macro_error("Generating macros", error)
                st.rerun()

        draft = st.session_state.get("nutrition_draft")
        if str(st.session_state.get("nutrition_draft_profile_id")) != str(selected_profile.get("_id")):
            draft = nutrition

        defaults = draft or nutrition or {
            "calories": 2000,
            "protein": 120,
            "fat": 70,
            "carbs": 250,
        }
        form_key = f"nutrition_form_{st.session_state.get('nutrition_draft_version', 0)}"

        st.subheader("Review and save")
        with st.form(form_key):
            calories = st.number_input(
                "Calories (kcal/day)",
                min_value=500.0,
                max_value=10000.0,
                step=50.0,
                value=float(defaults.get("calories", 2000)),
            )
            protein = st.number_input(
                "Protein (g/day)",
                min_value=1.0,
                max_value=500.0,
                step=5.0,
                value=float(defaults.get("protein", 120)),
            )
            fat = st.number_input(
                "Fat (g/day)",
                min_value=1.0,
                max_value=400.0,
                step=5.0,
                value=float(defaults.get("fat", 70)),
            )
            carbs = st.number_input(
                "Carbs (g/day)",
                min_value=1.0,
                max_value=1000.0,
                step=5.0,
                value=float(defaults.get("carbs", 250)),
            )
            submitted = st.form_submit_button("Save / Apply nutrition")

        if not submitted:
            return

        nutrition_payload = {
            "calories": float(calories),
            "protein": float(protein),
            "fat": float(fat),
            "carbs": float(carbs),
        }
        try:
            profile_id = selected_profile.get("_id")
            if not profile_id:
                raise ValueError("No profile selected")
            updated_profile = profiles.save_profile_changes(profile_id, nutrition=nutrition_payload)
            st.session_state["selected_profile_id"] = updated_profile.get("_id", profile_id)
            _refresh_profiles(st.session_state["selected_profile_id"])
            st.session_state["macro_success"] = "Nutrition targets saved."
            st.session_state["macro_error"] = None
            st.rerun()
        except Exception as error:
            _record_ui_failure("Saving nutrition", error)
            st.session_state["macro_success"] = None
            st.session_state["macro_error"] = _safe_macro_error("Saving nutrition", error)
            st.rerun()


def render_notes_section() -> None:
    st.header("Notes")
    with st.container(border=True):
        selected_profile = st.session_state.get("selected_profile")
        if not selected_profile:
            st.info("Select or create a profile before adding notes.")
            return

        user_id = str(selected_profile.get("_id") or "").strip()
        if not user_id:
            st.error("Selected profile is missing an ID.")
            return

        st.caption("Notes are saved only for the selected profile.")

        if str(st.session_state.get("notes_profile_id")) != user_id:
            _refresh_notes(user_id)

        if st.session_state.get("notes_success"):
            st.success(st.session_state["notes_success"])
        if st.session_state.get("notes_error"):
            st.error(st.session_state["notes_error"])

        with st.form("add_note_form"):
            note_text = st.text_area(
                "Workout / fitness note",
                placeholder="Example: Felt strong during squats today.",
                height=120,
            )
            submitted = st.form_submit_button("Add Note")

        if submitted:
            try:
                db.add_note(user_id, note_text)
                _refresh_notes(user_id)
                st.session_state["notes_success"] = "Note added."
                st.session_state["notes_error"] = None
                st.rerun()
            except Exception as error:
                _record_ui_failure("Adding note", error)
                st.session_state["notes_success"] = None
                st.session_state["notes_error"] = _safe_notes_error("Adding note", error)
                st.rerun()

        if st.button("Refresh notes"):
            _refresh_notes(user_id)
            st.rerun()

        notes = st.session_state.get("notes") or []
        if not notes:
            st.write("No notes saved for this profile yet.")
            return

        st.subheader("Saved notes")
        for index, note in enumerate(notes, start=1):
            note_id = note.get("_id")
            note_key = str(note_id)
            note_text = str(note.get("text") or "")

            with st.container(border=True):
                st.markdown(note_text)

                if st.session_state.get("confirm_delete_note_id") == note_key:
                    st.warning("Confirm deletion for this note.")
                    confirm_col, cancel_col = st.columns(2)
                    with confirm_col:
                        if st.button("Confirm delete", key=f"confirm_delete_note_{note_key}"):
                            try:
                                db.delete_note(user_id, note_id)
                                st.session_state["confirm_delete_note_id"] = None
                                _refresh_notes(user_id)
                                st.session_state["notes_success"] = "Note deleted."
                                st.session_state["notes_error"] = None
                                st.rerun()
                            except Exception as error:
                                _record_ui_failure("Deleting note", error)
                                st.session_state["notes_success"] = None
                                st.session_state["notes_error"] = _safe_notes_error(
                                    "Deleting note",
                                    error,
                                )
                                st.rerun()
                    with cancel_col:
                        if st.button("Cancel", key=f"cancel_delete_note_{note_key}"):
                            st.session_state["confirm_delete_note_id"] = None
                            st.rerun()
                elif st.button("Delete note", key=f"delete_note_{index}_{note_key}"):
                    st.session_state["confirm_delete_note_id"] = note_key
                    st.rerun()


def render_ask_ai_section() -> None:
    st.header("Ask AI")
    with st.container(border=True):
        selected_profile = st.session_state.get("selected_profile")
        if not selected_profile:
            st.info("Select or create a profile before asking AI.")
            return

        user_id = str(selected_profile.get("_id") or "").strip()
        if not user_id:
            st.error("Selected profile is missing an ID.")
            return

        st.caption(
            "Ask general fitness questions. For injury, severe pain, neurological symptoms, "
            "chest pain, or other concerning health issues, this assistant should not diagnose "
            "and should recommend appropriate professional care."
        )

        if st.session_state.get("ask_ai_error"):
            st.error(st.session_state["ask_ai_error"])

        with st.form("ask_ai_form"):
            question = st.text_area(
                "Question",
                placeholder="Example: Based on my notes, how should I structure next week?",
                height=100,
            )
            submitted = st.form_submit_button("Ask AI")

        if submitted:
            if not question.strip():
                st.session_state["ask_ai_error"] = "Ask AI failed: question cannot be empty."
                st.rerun()

            try:
                profile_context = profiles.build_profile_context(selected_profile)
                with st.spinner("Asking AI..."):
                    answer = ai.ask_ai(question, profile_context, user_id)
                st.session_state["last_ai_answer"] = answer
                st.session_state["ask_ai_error"] = None
                st.rerun()
            except Exception as error:
                _record_ui_failure("Ask AI", error)
                st.session_state["last_ai_answer"] = ""
                st.session_state["ask_ai_error"] = _safe_ask_ai_error("Ask AI", error)
                st.rerun()

        last_answer = st.session_state.get("last_ai_answer")
        if last_answer:
            st.subheader("Last answer")
            st.markdown(last_answer)


def main() -> None:
    st.set_page_config(
        page_title="Personal Fitness AI Assistant",
        layout="wide",
    )
    initialize_session_state()

    st.title("Personal Fitness AI Assistant")
    st.caption(
        "This app provides general fitness information for planning and learning. "
        "It is not medical advice."
    )

    if st.session_state.get("profile_success"):
        st.success(st.session_state["profile_success"])

    if st.session_state.get("ui_error"):
        st.error(st.session_state["ui_error"])

    left_column, right_column = st.columns((1, 1), gap="large")

    with left_column:
        render_profile_section()
        render_notes_section()

    with right_column:
        render_nutrition_section()
        render_ask_ai_section()


if __name__ == "__main__":
    main()
