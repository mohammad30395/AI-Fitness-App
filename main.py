import streamlit as st

import profiles


SESSION_DEFAULTS = {
    "selected_profile_id": None,
    "selected_profile": None,
    "profiles": [],
    "nutrition": None,
    "last_ai_answer": "",
    "ui_error": None,
    "profile_success": None,
}


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


def _profile_label(profile_id) -> str:
    for profile in st.session_state.get("profiles", []):
        if str(profile.get("_id")) == str(profile_id):
            name = profile.get("name") or "Unnamed profile"
            return f"{name} ({profile_id})"
    return str(profile_id)


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
            st.session_state["selected_profile"] = profiles.get_profile_by_id(selected_id)
        else:
            st.session_state["selected_profile"] = None

        st.session_state["ui_error"] = None
        return True
    except Exception as error:
        st.session_state["ui_error"] = _safe_profile_error("Loading profiles", error)
        st.session_state["profiles"] = []
        st.session_state["selected_profile"] = None
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
                    st.session_state["selected_profile"] = profiles.get_profile_by_id(selected_id)
                    st.session_state["ui_error"] = None
                    st.rerun()
                except Exception as error:
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
        nutrition = st.session_state.get("nutrition")
        if nutrition:
            calories, protein, fat, carbs = st.columns(4)
            calories.metric("Calories", nutrition.get("calories", "-"))
            protein.metric("Protein", nutrition.get("protein", "-"))
            fat.metric("Fat", nutrition.get("fat", "-"))
            carbs.metric("Carbs", nutrition.get("carbs", "-"))
        else:
            st.write("Macro targets will appear here after generation is wired.")


def render_notes_section() -> None:
    st.header("Notes")
    with st.container(border=True):
        st.write("Profile-specific notes will appear here after note storage is wired.")


def render_ask_ai_section() -> None:
    st.header("Ask AI")
    with st.container(border=True):
        st.write("Ask AI responses will appear here after Langflow calls are wired.")
        last_answer = st.session_state.get("last_ai_answer")
        if last_answer:
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
