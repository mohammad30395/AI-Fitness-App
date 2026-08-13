import streamlit as st


SESSION_DEFAULTS = {
    "selected_profile_id": None,
    "selected_profile": None,
    "profiles": [],
    "nutrition": None,
    "last_ai_answer": "",
    "ui_error": None,
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


def render_profile_section() -> None:
    st.header("Profile")
    with st.container(border=True):
        st.write("Profile selection and editing will appear here in a later milestone.")


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
