import logging
import re
import uuid

import streamlit as st

import ai
import auth
import config
import db
import profiles
from utils import NutritionParseError


logger = logging.getLogger(__name__)

AUTH_SESSION_DEFAULTS = {
    "authenticated": False,
    "account_id": None,
    "username": None,
    "auth_session_id": None,
}

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
    "profile_ui_mode": "view",
}

UI_THEME_SESSION_KEY = "ui_theme"
UI_THEME_OPTIONS = ("light", "dark")
DEFAULT_UI_THEME = "light"
PROFILE_UI_MODE_SESSION_KEY = "profile_ui_mode"
PROFILE_UI_MODE_VIEW = "view"
PROFILE_UI_MODE_EDIT = "edit"
PROFILE_UI_MODE_CREATE = "create"
PROFILE_UI_MODE_SELECTED = PROFILE_UI_MODE_VIEW
UI_THEME_TOKEN_NAMES = (
    "background",
    "surface",
    "surface_alt",
    "text",
    "text_muted",
    "border",
    "border_strong",
    "input_background",
    "input_hover",
    "accent",
    "accent_hover",
    "button_background",
    "button_hover",
    "button_text",
    "danger",
    "danger_hover",
    "tooltip_background",
    "tooltip_text",
    "tooltip_border",
    "focus_ring",
    "shadow",
    "success",
    "warning",
    "error",
)
UI_THEME_TOKENS = {
    "light": {
        "background": "#f7f8fb",
        "surface": "#ffffff",
        "surface_alt": "#eef2f7",
        "text": "#172033",
        "text_muted": "#586174",
        "border": "#d8dee9",
        "border_strong": "#b8c2d3",
        "input_background": "#ffffff",
        "input_hover": "#f8fafc",
        "accent": "#2563eb",
        "accent_hover": "#1d4ed8",
        "button_background": "#2563eb",
        "button_hover": "#1d4ed8",
        "button_text": "#ffffff",
        "danger": "#b42318",
        "danger_hover": "#fee4e2",
        "tooltip_background": "#111827",
        "tooltip_text": "#f9fafb",
        "tooltip_border": "#374151",
        "focus_ring": "rgba(37, 99, 235, 0.28)",
        "shadow": "0 10px 28px rgba(23, 32, 51, 0.08)",
        "success": "#047857",
        "warning": "#b45309",
        "error": "#b91c1c",
    },
    "dark": {
        "background": "#111827",
        "surface": "#1f2937",
        "surface_alt": "#273449",
        "text": "#f3f4f6",
        "text_muted": "#c5cbd6",
        "border": "#3f4b5f",
        "border_strong": "#64748b",
        "input_background": "#172033",
        "input_hover": "#1f2a3d",
        "accent": "#60a5fa",
        "accent_hover": "#93c5fd",
        "button_background": "#60a5fa",
        "button_hover": "#93c5fd",
        "button_text": "#0b1220",
        "danger": "#fb7185",
        "danger_hover": "#3b1823",
        "tooltip_background": "#f9fafb",
        "tooltip_text": "#111827",
        "tooltip_border": "#d1d5db",
        "focus_ring": "rgba(96, 165, 250, 0.35)",
        "shadow": "0 10px 28px rgba(0, 0, 0, 0.24)",
        "success": "#34d399",
        "warning": "#fbbf24",
        "error": "#f87171",
    },
}

GENDER_OPTIONS = ("Male", "Female", "Other")
ACTIVITY_LEVEL_OPTIONS = (
    "Sedentary",
    "Lightly Active",
    "Moderately Active",
    "Very Active",
    "Super Active",
)
GOAL_OPTIONS = ("Muscle Gain", "Fat Loss", "Stay Active")
DEFAULT_CREATE_GOALS = ("Muscle Gain",)
PROFILE_CHOICE_WIDGET_SUFFIXES = (
    "gender_choice",
    "activity_level_choice",
    "goals_multiselect",
)
EDIT_GOAL_EDITOR_PREFIXES = (
    "edit_profile_form_goals_editor_",
    "edit_profile_form_goal_input_",
    "edit_profile_form_goal_add_open_",
    "edit_profile_form_goal_error_",
)


def _sanitize_diagnostic(message: str) -> str:
    sanitized = str(message)
    for name in config.ALL_VARIABLES:
        value = config.get_env_value(name)
        if value and len(value) >= 4:
            sanitized = sanitized.replace(value, f"<redacted:{name}>")
    sanitized = re.sub(r"AstraCS:[A-Za-z0-9._:-]+", "<redacted:ASTRA_TOKEN>", sanitized)
    sanitized = re.sub(r"sk-[A-Za-z0-9._-]+", "<redacted:API_KEY>", sanitized)
    sanitized = re.sub(r"FAKE_[A-Z0-9_]*SECRET[A-Z0-9_]*", "<redacted:secret>", sanitized)
    sanitized = re.sub(r"(https?://)([^/@\s]+):([^/@\s]+)@", r"\1<redacted>@", sanitized)
    sanitized = re.sub(
        r"(?i)['\"]?\b(x-api-key|authorization|api[_-]?key|token|secret|password)\b['\"]?"
        r"\s*[:=]\s*['\"]?[^,'\"\s}]+['\"]?",
        "<redacted:secret_field>",
        sanitized,
    )
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


def _initialize_ui_theme_state() -> None:
    if st.session_state.get(UI_THEME_SESSION_KEY) not in UI_THEME_OPTIONS:
        st.session_state[UI_THEME_SESSION_KEY] = DEFAULT_UI_THEME


def _toggle_ui_theme() -> None:
    current_theme = st.session_state.get(UI_THEME_SESSION_KEY, DEFAULT_UI_THEME)
    st.session_state[UI_THEME_SESSION_KEY] = "dark" if current_theme == "light" else "light"


def _current_ui_theme() -> str:
    theme = st.session_state.get(UI_THEME_SESSION_KEY, DEFAULT_UI_THEME)
    return theme if theme in UI_THEME_OPTIONS else DEFAULT_UI_THEME


def _theme_declarations(theme: str) -> str:
    tokens = UI_THEME_TOKENS[theme if theme in UI_THEME_OPTIONS else DEFAULT_UI_THEME]
    return "\n".join(
        f"    --fit-{name.replace('_', '-')}: {value};"
        for name, value in ((name, tokens[name]) for name in UI_THEME_TOKEN_NAMES)
    )


def _apply_ui_theme() -> None:
    declarations = _theme_declarations(_current_ui_theme())
    st.markdown(
        f"""
<style>
:root {{
{declarations}
}}

[data-testid="stAppViewContainer"] {{
    background: var(--fit-background);
    color: var(--fit-text);
}}

[data-testid="stHeader"] {{
    background: var(--fit-background);
}}

[data-testid="stMainBlockContainer"] {{
    padding-top: 1.5rem;
}}

[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span,
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p,
[data-testid="stCaptionContainer"] span,
[data-testid="stText"],
[data-testid="stText"] p,
[data-testid="stText"] span {{
    color: var(--fit-text);
}}

[data-testid="stCaptionContainer"],
[data-testid="stMarkdownContainer"] small {{
    color: var(--fit-text-muted);
}}

[role="tooltip"] {{
    background-color: var(--fit-tooltip-background);
    border: 1px solid var(--fit-tooltip-border);
    box-shadow: var(--fit-shadow);
    color: var(--fit-tooltip-text);
}}

[role="tooltip"] * {{
    color: var(--fit-tooltip-text);
}}

[data-testid="stForm"],
[data-testid="stVerticalBlockBorderWrapper"] {{
    background-color: var(--fit-surface);
    border: 1px solid var(--fit-border);
    border-radius: 0.65rem;
    box-shadow: var(--fit-shadow);
}}

[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea,
div[data-baseweb="select"] > div {{
    background-color: var(--fit-input-background);
    color: var(--fit-text);
    border-color: var(--fit-border);
    border-radius: 0.45rem;
    box-shadow: none;
}}

[data-testid="stTextInput"] input:hover,
[data-testid="stNumberInput"] input:hover,
[data-testid="stTextArea"] textarea:hover,
div[data-baseweb="select"] > div:hover {{
    background-color: var(--fit-input-hover);
    border-color: var(--fit-border-strong);
}}

[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextArea"] textarea:focus,
div[data-baseweb="select"]:focus-within > div {{
    border-color: var(--fit-accent);
    box-shadow: 0 0 0 3px var(--fit-focus-ring);
}}

[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {{
    color: var(--fit-text-muted);
}}

[data-testid="stRadio"] label,
[data-testid="stSelectbox"] label,
[data-testid="stTextInput"] label,
[data-testid="stNumberInput"] label,
[data-testid="stTextArea"] label {{
    color: var(--fit-text);
}}

[data-testid="stRadio"] {{
    margin-bottom: 0.75rem;
}}

[data-testid="stRadio"] div[role="radiogroup"] {{
    gap: 0.15rem;
}}

[data-testid="stRadio"] div[role="radiogroup"] label {{
    border-radius: 0.45rem;
    padding: 0.1rem 0.2rem;
}}

[data-testid="stRadio"] div[role="radiogroup"] label:hover {{
    background-color: var(--fit-surface-alt);
}}

[data-testid="stSelectbox"] svg {{
    color: var(--fit-text-muted);
    fill: var(--fit-text-muted);
}}

[data-testid="stButton"] button,
[data-testid="stFormSubmitButton"] button {{
    border: 1px solid var(--fit-border);
    border-radius: 0.45rem;
    background-color: var(--fit-surface-alt);
    color: var(--fit-text);
    box-shadow: none;
    font-weight: 600;
    min-height: 2.25rem;
    transition: background-color 120ms ease, border-color 120ms ease, color 120ms ease;
}}

[data-testid="stButton"] button:hover,
[data-testid="stFormSubmitButton"] button:hover {{
    background-color: var(--fit-input-hover);
    border-color: var(--fit-border-strong);
    color: var(--fit-text);
}}

[data-testid="stButton"] button:focus-visible,
[data-testid="stFormSubmitButton"] button:focus-visible {{
    outline: 3px solid var(--fit-focus-ring);
    outline-offset: 2px;
}}

[data-testid="stButton"] button[kind="primary"],
[data-testid="stFormSubmitButton"] button[kind="primary"] {{
    background-color: var(--fit-button-background);
    color: var(--fit-button-text);
    border-color: var(--fit-button-background);
}}

[data-testid="stButton"] button[kind="primary"]:hover,
[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {{
    background-color: var(--fit-button-hover);
    border-color: var(--fit-button-hover);
    color: var(--fit-button-text);
}}
</style>
""",
        unsafe_allow_html=True,
    )


def _render_theme_button() -> None:
    theme = _current_ui_theme()
    label = "🌙 Dark" if theme == "light" else "☀️ Light"
    help_text = "Switch to dark mode" if theme == "light" else "Switch to light mode"
    st.button(
        label,
        key="ui_theme_toggle",
        help=help_text,
        on_click=_toggle_ui_theme,
        use_container_width=True,
    )


def _render_theme_control() -> None:
    _, control_col = st.columns((6, 1), vertical_alignment="center")
    with control_col:
        _render_theme_button()


def _initialize_auth_session_state() -> None:
    for key, value in AUTH_SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _is_authenticated_session() -> bool:
    return (
        st.session_state.get("authenticated") is True
        and isinstance(st.session_state.get("account_id"), str)
        and bool(st.session_state.get("account_id").strip())
        and isinstance(st.session_state.get("username"), str)
        and bool(st.session_state.get("username").strip())
        and isinstance(st.session_state.get("auth_session_id"), str)
        and bool(st.session_state.get("auth_session_id").strip())
    )


def _trusted_account_id() -> str:
    account_id = st.session_state["account_id"]
    if not isinstance(account_id, str) or not account_id.strip():
        raise RuntimeError("Authenticated account is missing.")
    return account_id


def _reset_session_for_logout() -> None:
    st.session_state.clear()
    _initialize_auth_session_state()


def _establish_authenticated_session(account: dict[str, str]) -> None:
    st.session_state["authenticated"] = True
    st.session_state["account_id"] = account["account_id"]
    st.session_state["username"] = account["username"]
    st.session_state["auth_session_id"] = str(uuid.uuid4())


def _render_login_form() -> None:
    st.header("Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", type="primary")

    if not submitted:
        return

    try:
        account = auth.authenticate(username, password)
    except auth.AuthenticationError:
        st.error("Invalid username or password.")
    except Exception as error:
        _record_ui_failure("Logging in", error)
        st.error("Unable to log in right now.")
    else:
        _establish_authenticated_session(account)
        st.rerun()


def _render_create_account_form() -> None:
    st.header("Create Account")
    with st.form("create_account_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Create Account", type="primary")

    if not submitted:
        return

    if password != confirm_password:
        st.error("Passwords do not match.")
        return

    try:
        account = auth.create_account(username, password)
    except auth.AccountAlreadyExistsError:
        st.error("That username is already in use.")
    except auth.AuthValidationError as error:
        st.error(str(error))
    except Exception as error:
        _record_ui_failure("Creating account", error)
        st.error("Unable to create account right now.")
    else:
        _establish_authenticated_session(account)
        st.rerun()


def _render_authentication_ui() -> None:
    st.info("Authentication required.")
    login_tab, create_tab = st.tabs(["Login", "Create Account"])
    with login_tab:
        _render_login_form()
    with create_tab:
        _render_create_account_form()


def _enforce_authentication_gate() -> None:
    if _is_authenticated_session():
        return

    _render_authentication_ui()
    st.stop()


def _render_authenticated_header() -> None:
    account_col, _, theme_col, create_col, logout_col = st.columns(
        (4, 2, 1, 1.6, 1),
        vertical_alignment="center",
    )
    with account_col:
        st.caption(f"Signed in as {st.session_state['username']}")
    with theme_col:
        _render_theme_button()
    with create_col:
        st.button(
            "Create Profile",
            key="profile_create_action",
            help="Create a new profile",
            on_click=_enter_create_profile_mode,
            use_container_width=True,
        )
    with logout_col:
        logout_clicked = st.button(
            "Logout",
            key="logout_button",
            help="Sign out",
            use_container_width=True,
        )
    if logout_clicked:
        _reset_session_for_logout()
        st.rerun()


def _current_profile_ui_mode() -> str:
    mode = st.session_state.get(PROFILE_UI_MODE_SESSION_KEY)
    if mode not in {PROFILE_UI_MODE_VIEW, PROFILE_UI_MODE_EDIT, PROFILE_UI_MODE_CREATE}:
        mode = PROFILE_UI_MODE_VIEW
        st.session_state[PROFILE_UI_MODE_SESSION_KEY] = mode
    return mode


def _enter_create_profile_mode() -> None:
    st.session_state[PROFILE_UI_MODE_SESSION_KEY] = PROFILE_UI_MODE_CREATE


def _enter_edit_profile_mode() -> None:
    _clear_edit_profile_form_state()
    st.session_state[PROFILE_UI_MODE_SESSION_KEY] = PROFILE_UI_MODE_EDIT


def _clear_create_profile_form_state() -> None:
    for key in (
        _profile_choice_widget_key("create_profile_form", "gender_choice"),
        _profile_choice_widget_key("create_profile_form", "activity_level_choice"),
        "create_profile_form_name",
        "create_profile_form_age",
        "create_profile_form_weight",
        "create_profile_form_height",
    ):
        st.session_state.pop(key, None)
    _clear_create_goal_editor_state()


def _exit_edit_profile_mode() -> None:
    st.session_state[PROFILE_UI_MODE_SESSION_KEY] = PROFILE_UI_MODE_VIEW
    _clear_edit_profile_form_state()


def _exit_create_profile_mode() -> None:
    st.session_state[PROFILE_UI_MODE_SESSION_KEY] = PROFILE_UI_MODE_VIEW
    _clear_create_profile_form_state()


def _goals_from_text(goals_text: str) -> list[str]:
    normalized = goals_text.replace(",", "\n")
    return [goal.strip() for goal in normalized.splitlines() if goal.strip()]


def _goals_to_text(profile: dict) -> str:
    goals = profile.get("goals", [])
    if not isinstance(goals, list):
        return str(goals)
    return "\n".join(str(goal) for goal in goals)


def _unique_meaningful_options(values) -> tuple[str, ...]:
    options = []
    for value in values or ():
        option = str(value).strip()
        if option and option not in options:
            options.append(option)
    return tuple(options)


def _single_choice_options_with_current(canonical_options, current_value) -> tuple[str, ...]:
    canonical = _unique_meaningful_options(canonical_options)
    if current_value is None:
        return canonical

    current_option = str(current_value).strip()
    if not current_option or current_option in canonical:
        return canonical

    # Legacy current values go first so edit-mode widgets can show them by default.
    return (current_option, *canonical)


def _goal_options_with_existing(canonical_options, existing_goals) -> tuple[str, ...]:
    options = list(_unique_meaningful_options(canonical_options))
    for goal in existing_goals or ():
        goal_option = str(goal).strip()
        if goal_option and goal_option not in options:
            options.append(goal_option)
    return tuple(options)


def _goals_from_profile(profile: dict | None) -> list[str]:
    profile = profile or {}
    goals = profile.get("goals", [])
    if not isinstance(goals, list):
        cleaned_goal = str(goals).strip()
        return [cleaned_goal] if cleaned_goal else []
    return [str(goal).strip() for goal in goals if str(goal).strip()]


def _normalize_goal_editor_state(goals) -> list[str]:
    if not isinstance(goals, list):
        return []
    return [str(goal).strip() for goal in goals if str(goal).strip()]


def _selected_option_index(options: tuple[str, ...], current_value) -> int | None:
    if current_value is None:
        return None
    current_option = str(current_value).strip()
    if not current_option:
        return None
    try:
        return options.index(current_option)
    except ValueError:
        return None


def _profile_choice_widget_key(form_key: str, suffix: str) -> str:
    return f"{form_key}_{suffix}"


def _goal_editor_key(form_key: str, suffix: str, profile: dict | None = None) -> str:
    if form_key != "edit_profile_form":
        return f"{form_key}_{suffix}"
    profile_id = (profile or {}).get("_id") or "unselected"
    return f"{form_key}_{suffix}_{profile_id}"


def _initialize_goal_editor_state(
    *,
    form_key: str,
    is_edit: bool,
    profile: dict | None = None,
) -> str:
    state_key = _goal_editor_key(form_key, "goals_editor", profile)
    if state_key not in st.session_state:
        st.session_state[state_key] = (
            _goals_from_profile(profile) if is_edit else list(DEFAULT_CREATE_GOALS)
        )
    else:
        st.session_state[state_key] = _normalize_goal_editor_state(st.session_state[state_key])
    return state_key


def _set_goal_editor_state(state_key: str, goals) -> None:
    st.session_state[state_key] = _normalize_goal_editor_state(goals)


def _show_goal_input(open_key: str, error_key: str) -> None:
    st.session_state[open_key] = True
    st.session_state[error_key] = None


def _add_goal_to_editor(state_key: str, input_key: str, error_key: str, open_key: str) -> None:
    new_goal = str(st.session_state.get(input_key) or "").strip()
    if not new_goal:
        st.session_state[error_key] = "Enter a goal before adding."
        return

    goals = _normalize_goal_editor_state(st.session_state.get(state_key, []))
    if new_goal in goals:
        st.session_state[error_key] = "That goal is already in the list."
        return

    goals.append(new_goal)
    st.session_state[state_key] = goals
    st.session_state[input_key] = ""
    st.session_state[open_key] = False
    st.session_state[error_key] = None


def _remove_goal_from_editor(state_key: str, index: int, error_key: str) -> None:
    goals = _normalize_goal_editor_state(st.session_state.get(state_key, []))
    if 0 <= index < len(goals):
        goals.pop(index)
    st.session_state[state_key] = goals
    st.session_state[error_key] = None


def _clear_edit_profile_choice_widget_state() -> None:
    for suffix in PROFILE_CHOICE_WIDGET_SUFFIXES:
        st.session_state.pop(_profile_choice_widget_key("edit_profile_form", suffix), None)
    for key in list(st.session_state.keys()):
        if any(str(key).startswith(prefix) for prefix in EDIT_GOAL_EDITOR_PREFIXES):
            st.session_state.pop(key, None)


def _clear_edit_profile_form_state() -> None:
    for key in (
        "edit_profile_form_name",
        "edit_profile_form_age",
        "edit_profile_form_weight",
        "edit_profile_form_height",
    ):
        st.session_state.pop(key, None)
    _clear_edit_profile_choice_widget_state()


def _clear_create_goal_editor_state() -> None:
    for key in (
        _goal_editor_key("create_profile_form", "goals_editor"),
        _goal_editor_key("create_profile_form", "goal_input"),
        _goal_editor_key("create_profile_form", "goal_add_open"),
        _goal_editor_key("create_profile_form", "goal_error"),
    ):
        st.session_state.pop(key, None)


def _render_goals_editor(form_key: str, state_key: str, profile: dict | None = None) -> None:
    input_key = _goal_editor_key(form_key, "goal_input", profile)
    open_key = _goal_editor_key(form_key, "goal_add_open", profile)
    error_key = _goal_editor_key(form_key, "goal_error", profile)
    goals = _normalize_goal_editor_state(st.session_state.get(state_key, []))
    st.session_state[state_key] = goals

    st.subheader("Goals")
    with st.container(border=True):
        if goals:
            for index, goal in enumerate(goals):
                goal_col, remove_col = st.columns((4, 1), vertical_alignment="center")
                with goal_col:
                    st.write(goal)
                with remove_col:
                    st.form_submit_button(
                        "−",
                        key=f"{state_key}_remove_{index}",
                        help=f"Remove {goal}",
                        on_click=_remove_goal_from_editor,
                        args=(state_key, index, error_key),
                        use_container_width=True,
                    )
        else:
            st.write("No goals added yet.")

        if st.session_state.get(open_key):
            input_col, add_col = st.columns((4, 1), vertical_alignment="bottom")
            with input_col:
                st.text_input("New Goal", key=input_key)
            with add_col:
                st.form_submit_button(
                    "Add Goal",
                    key=f"{state_key}_add_goal",
                    help="Confirm new goal",
                    on_click=_add_goal_to_editor,
                    args=(state_key, input_key, error_key, open_key),
                    use_container_width=True,
                )
        else:
            _, add_col = st.columns((4, 1))
            with add_col:
                st.form_submit_button(
                    "+",
                    key=f"{state_key}_show_add_goal",
                    help="Add goal",
                    on_click=_show_goal_input,
                    args=(open_key, error_key),
                    use_container_width=True,
                )

        if st.session_state.get(error_key):
            st.error(st.session_state[error_key])


def _safe_profile_error(action: str, error: Exception) -> str:
    if isinstance(error, (db.InvalidProfileError, profiles.ProfileDataError)):
        message = _sanitize_diagnostic(str(error))
        return f"{action} failed: {message}."
    return f"{action} failed ({type(error).__name__}). Check profile fields and database configuration."


def _safe_macro_error(action: str, error: Exception) -> str:
    ai_message = _safe_ai_error_message(action, error)
    if ai_message:
        return ai_message
    if isinstance(error, NutritionParseError):
        return f"{action} failed: The AI response was received but the nutrition output was not valid."
    return f"{action} failed ({type(error).__name__}). Check Langflow configuration and macro output."


def _safe_notes_error(action: str, error: Exception) -> str:
    return f"{action} failed ({type(error).__name__}). Check note text and Astra notes configuration."


def _safe_ask_ai_error(action: str, error: Exception) -> str:
    ai_message = _safe_ai_error_message(action, error)
    if ai_message:
        return ai_message
    return f"{action} failed ({type(error).__name__}). Check Langflow Ask AI configuration and try again."


def _safe_ai_error_message(action: str, error: Exception) -> str | None:
    if isinstance(error, ai.ProviderQuotaError):
        return (
            f"{action} failed: AI provider request was rejected because the OpenRouter "
            "credit/token budget is insufficient. Add OpenRouter credit or reduce the "
            "model's max-token setting in Langflow, then try again."
        )
    if isinstance(error, ai.LangflowConfigError):
        return (
            f"{action} failed: AI configuration is incomplete. "
            "Check the required Langflow configuration."
        )
    if isinstance(error, ai.LangflowConnectionError):
        return (
            f"{action} failed: Langflow could not be reached. "
            "Confirm the local Langflow server is running."
        )
    if isinstance(error, ai.LangflowTimeoutError):
        return (
            f"{action} failed: The AI request timed out. "
            "Try again or check the Langflow flow."
        )
    if isinstance(error, ai.LangflowHTTPError):
        return f"{action} failed: Langflow could not complete the AI workflow."
    if isinstance(error, ai.LangflowResponseError):
        return f"{action} failed: Langflow returned an unexpected response format."
    return None


def _profile_label(profile_id) -> str:
    for profile in st.session_state.get("profiles", []):
        if str(profile.get("_id")) == str(profile_id):
            name = profile.get("name") or "Unnamed profile"
            return str(name)
    return str(profile_id)


def _copy_nutrition(nutrition):
    if isinstance(nutrition, dict) and nutrition:
        return dict(nutrition)
    return None


def _set_selected_profile(profile: dict | None) -> None:
    st.session_state["selected_profile"] = profile
    _clear_edit_profile_form_state()
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
        account_id = _trusted_account_id()
        profile_list = profiles.get_all_profiles(account_id)
        st.session_state["profiles"] = profile_list
        profile_ids = [profile.get("_id") for profile in profile_list if profile.get("_id")]

        selected_profile_id = st.session_state.get("selected_profile_id")
        if select_profile_id is not None and any(
            str(profile_id) == str(select_profile_id) for profile_id in profile_ids
        ):
            selected_profile_id = select_profile_id
        elif selected_profile_id is not None and any(
            str(profile_id) == str(selected_profile_id) for profile_id in profile_ids
        ):
            selected_profile_id = selected_profile_id
        elif profile_ids:
            selected_profile_id = profile_ids[0]
        else:
            selected_profile_id = None

        st.session_state["selected_profile_id"] = selected_profile_id
        selected_id = st.session_state.get("selected_profile_id")
        if selected_id is not None:
            _set_selected_profile(profiles.get_profile_by_id(account_id, selected_id))
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


def _refresh_notes(profile_id: str) -> bool:
    try:
        st.session_state["notes"] = db.list_notes(
            _trusted_account_id(),
            profile_id,
            limit=50,
        )
        st.session_state["notes_profile_id"] = profile_id
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


def _display_profile_value(value, fallback: str = "not set") -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def _display_profile_measurement(value, unit: str) -> str:
    if value is None or value == "":
        return "not set"
    return f"{value} {unit}"


def _render_profile_summary(profile: dict) -> None:
    name = _display_profile_value(profile.get("name"), "Unnamed profile")
    goals = _goals_from_profile(profile)

    with st.container(border=True):
        st.subheader(name)
        measurement_cols = st.columns(3)
        with measurement_cols[0]:
            st.caption("Age")
            st.write(_display_profile_value(profile.get("age")))
        with measurement_cols[1]:
            st.caption("Weight")
            st.write(_display_profile_measurement(profile.get("weight"), "kg"))
        with measurement_cols[2]:
            st.caption("Height")
            st.write(_display_profile_measurement(profile.get("height"), "cm"))

        profile_cols = st.columns(2)
        with profile_cols[0]:
            st.caption("Gender")
            st.write(_display_profile_value(profile.get("gender")))
        with profile_cols[1]:
            st.caption("Activity Level")
            st.write(_display_profile_value(profile.get("activity_level")))

        st.caption("Goals")
        if goals:
            for goal in goals:
                st.write(f"- {goal}")
        else:
            st.caption("No goals added.")


def _render_profile_form(*, mode: str, profile: dict | None = None) -> None:
    defaults = _profile_form_defaults(profile)
    is_edit = mode == "edit"
    form_key = "edit_profile_form" if is_edit else "create_profile_form"
    submit_label = "Save Changes" if is_edit else "Create profile"
    gender_options = (
        _single_choice_options_with_current(GENDER_OPTIONS, defaults["gender"])
        if is_edit
        else GENDER_OPTIONS
    )
    activity_level_options = (
        _single_choice_options_with_current(ACTIVITY_LEVEL_OPTIONS, defaults["activity_level"])
        if is_edit
        else ACTIVITY_LEVEL_OPTIONS
    )
    goals_state_key = _initialize_goal_editor_state(
        form_key=form_key,
        is_edit=is_edit,
        profile=profile,
    )

    with st.form(form_key):
        name = st.text_input("Name", value=defaults["name"], key=f"{form_key}_name")
        age_col, weight_col, height_col = st.columns(3)
        with age_col:
            age = st.number_input(
                "Age",
                min_value=1,
                step=1,
                value=defaults["age"],
                key=f"{form_key}_age",
            )
        with weight_col:
            weight = st.number_input(
                "Weight",
                min_value=0.1,
                step=0.1,
                value=defaults["weight"],
                key=f"{form_key}_weight",
            )
        with height_col:
            height = st.number_input(
                "Height",
                min_value=0.1,
                step=0.1,
                value=defaults["height"],
                key=f"{form_key}_height",
            )
        gender = st.radio(
            "Gender",
            options=gender_options,
            index=_selected_option_index(gender_options, defaults["gender"]),
            key=_profile_choice_widget_key(form_key, "gender_choice"),
        )
        activity_level = st.selectbox(
            "Activity Level",
            options=activity_level_options,
            index=_selected_option_index(activity_level_options, defaults["activity_level"]),
            key=_profile_choice_widget_key(form_key, "activity_level_choice"),
            placeholder="Choose activity level",
        )
        _render_goals_editor(form_key, goals_state_key, profile)

        if is_edit:
            save_col, cancel_col, _ = st.columns((1, 1, 4))
            with save_col:
                submitted = st.form_submit_button(submit_label, type="primary")
            with cancel_col:
                cancelled = st.form_submit_button(
                    "Cancel",
                    key=f"{form_key}_cancel",
                    help="Discard unsaved profile changes",
                    type="secondary",
                )
        else:
            submitted = st.form_submit_button(submit_label, type="primary")
            cancelled = False

    if cancelled:
        _exit_edit_profile_mode()
        st.rerun()
    if not submitted:
        return

    profile_payload = {
        "name": name,
        "age": int(age),
        "weight": float(weight),
        "height": float(height),
        "gender": gender,
        "activity_level": activity_level,
        "goals": _normalize_goal_editor_state(st.session_state.get(goals_state_key, [])),
    }

    try:
        if is_edit:
            account_id = _trusted_account_id()
            profile_id = st.session_state.get("selected_profile_id")
            if not profile_id:
                raise ValueError("No profile selected")
            updated_profile = profiles.save_profile_changes(account_id, profile_id, **profile_payload)
            _set_goal_editor_state(goals_state_key, updated_profile.get("goals", profile_payload["goals"]))
            st.session_state["selected_profile_id"] = updated_profile.get("_id", profile_id)
            st.session_state["selected_profile"] = updated_profile
            _refresh_profiles(st.session_state["selected_profile_id"])
            st.session_state[PROFILE_UI_MODE_SESSION_KEY] = PROFILE_UI_MODE_VIEW
            st.session_state["profile_success"] = "Profile updated."
        else:
            new_profile_id = profiles.create_new_profile(
                account_id=_trusted_account_id(),
                **profile_payload,
            )
            st.session_state[PROFILE_UI_MODE_SESSION_KEY] = PROFILE_UI_MODE_VIEW
            _clear_create_profile_form_state()
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
        profile_mode = _current_profile_ui_mode()
        st.caption("Select or edit the active profile used by every section below.")
        if not st.session_state.get("profiles") and st.session_state.get("ui_error") is None:
            with st.spinner("Loading profiles..."):
                _refresh_profiles()

        if profile_mode == PROFILE_UI_MODE_CREATE:
            st.subheader("Create Profile")
            if st.button(
                "Back to selected profile",
                key="cancel_create_profile",
                help="Leave create mode without saving",
            ):
                _exit_create_profile_mode()
                st.rerun()
            _render_profile_form(mode="create")
            return

        refresh_col, selector_col = st.columns((1, 3))
        with refresh_col:
            if st.button("Refresh", use_container_width=True):
                with st.spinner("Loading profiles..."):
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

            with selector_col:
                selected_id = st.selectbox(
                    "Active profile",
                    options=profile_ids,
                    index=current_index,
                    format_func=_profile_label,
                )

            if str(selected_id) != str(st.session_state.get("selected_profile_id")):
                try:
                    account_id = _trusted_account_id()
                    st.session_state[PROFILE_UI_MODE_SESSION_KEY] = PROFILE_UI_MODE_VIEW
                    st.session_state["selected_profile_id"] = selected_id
                    _set_selected_profile(profiles.get_profile_by_id(account_id, selected_id))
                    st.session_state["ui_error"] = None
                    st.rerun()
                except Exception as error:
                    _record_ui_failure("Selecting profile", error)
                    st.session_state["ui_error"] = _safe_profile_error("Selecting profile", error)
                    st.rerun()
        else:
            with selector_col:
                st.info("No profiles yet. Use Create Profile in the top action row.")

        selected_profile = st.session_state.get("selected_profile")
        if profile_mode == PROFILE_UI_MODE_EDIT and not selected_profile:
            st.session_state[PROFILE_UI_MODE_SESSION_KEY] = PROFILE_UI_MODE_VIEW
            profile_mode = PROFILE_UI_MODE_VIEW

        if selected_profile:
            if profile_mode == PROFILE_UI_MODE_EDIT:
                st.subheader("Edit Profile")
                _render_profile_form(mode="edit", profile=selected_profile)
            else:
                _render_profile_summary(selected_profile)
                st.button(
                    "Edit Profile",
                    key="edit_profile_action",
                    help="Edit the selected profile",
                    on_click=_enter_edit_profile_mode,
                )
        else:
            st.info("No profile selected. Use Create Profile in the top action row.")


def render_nutrition_section() -> None:
    st.header("Nutrition / Macros")
    with st.container(border=True):
        selected_profile = st.session_state.get("selected_profile")
        if not selected_profile:
            st.info("Select or create a profile before generating nutrition targets.")
            st.button("Generate with AI", disabled=True, use_container_width=True)
            with st.form("nutrition_disabled_form"):
                disabled_cols = st.columns(4)
                disabled_cols[0].number_input("Calories (kcal/day)", value=0.0, disabled=True)
                disabled_cols[1].number_input("Protein (g/day)", value=0.0, disabled=True)
                disabled_cols[2].number_input("Fat (g/day)", value=0.0, disabled=True)
                disabled_cols[3].number_input("Carbs (g/day)", value=0.0, disabled=True)
                st.form_submit_button("Save / Apply nutrition", disabled=True)
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
            st.info("No saved nutrition targets yet. Generate a draft or enter targets manually.")

        if st.session_state.get("macro_success"):
            st.success(st.session_state["macro_success"])
        if st.session_state.get("macro_error"):
            st.error(st.session_state["macro_error"])

        if st.button("Generate with AI", type="primary", use_container_width=True):
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
            nutrition_cols = st.columns(4)
            with nutrition_cols[0]:
                calories = st.number_input(
                    "Calories (kcal/day)",
                    min_value=500.0,
                    max_value=10000.0,
                    step=50.0,
                    value=float(defaults.get("calories", 2000)),
                )
            with nutrition_cols[1]:
                protein = st.number_input(
                    "Protein (g/day)",
                    min_value=1.0,
                    max_value=500.0,
                    step=5.0,
                    value=float(defaults.get("protein", 120)),
                )
            with nutrition_cols[2]:
                fat = st.number_input(
                    "Fat (g/day)",
                    min_value=1.0,
                    max_value=400.0,
                    step=5.0,
                    value=float(defaults.get("fat", 70)),
                )
            with nutrition_cols[3]:
                carbs = st.number_input(
                    "Carbs (g/day)",
                    min_value=1.0,
                    max_value=1000.0,
                    step=5.0,
                    value=float(defaults.get("carbs", 250)),
                )
            submitted = st.form_submit_button("Save / Apply nutrition", type="primary")

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
            updated_profile = profiles.save_profile_changes(
                _trusted_account_id(),
                profile_id,
                nutrition=nutrition_payload,
            )
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
            with st.form("add_note_disabled_form"):
                st.text_area("Workout / fitness note", height=100, disabled=True)
                st.form_submit_button("Add Note", disabled=True)
            return

        profile_id = str(selected_profile.get("_id") or "").strip()
        if not profile_id:
            st.error("Selected profile is missing an ID.")
            return

        st.caption("Notes are saved and listed only for the selected profile.")

        if str(st.session_state.get("notes_profile_id")) != profile_id:
            with st.spinner("Loading notes..."):
                _refresh_notes(profile_id)

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
            submitted = st.form_submit_button("Add Note", type="primary")

        if submitted:
            try:
                db.add_note(_trusted_account_id(), profile_id, note_text)
                _refresh_notes(profile_id)
                st.session_state["notes_success"] = "Note added."
                st.session_state["notes_error"] = None
            except Exception as error:
                _record_ui_failure("Adding note", error)
                st.session_state["notes_success"] = None
                st.session_state["notes_error"] = _safe_notes_error("Adding note", error)
                st.rerun()
            else:
                st.rerun()

        notes = st.session_state.get("notes") or []
        list_col, refresh_col = st.columns((3, 1))
        list_col.subheader(f"Saved notes ({len(notes)})")
        with refresh_col:
            if st.button("Refresh notes", use_container_width=True):
                with st.spinner("Loading notes..."):
                    _refresh_notes(profile_id)
                st.rerun()

        if not notes:
            st.info("No notes saved for this profile yet.")
            return

        for index, note in enumerate(notes, start=1):
            note_id = note.get("_id")
            note_key = str(note_id)
            note_text = str(note.get("text") or "")

            with st.container(border=True):
                note_col, action_col = st.columns((4, 1))
                with note_col:
                    st.caption(f"Note {index}")
                    st.write(note_text)

                if st.session_state.get("confirm_delete_note_id") == note_key:
                    st.warning("Confirm deletion for this note.")
                    confirm_col, cancel_col = st.columns(2)
                    with confirm_col:
                        if st.button("Confirm delete", key=f"confirm_delete_note_{note_key}"):
                            try:
                                db.delete_note(_trusted_account_id(), profile_id, note_id)
                                st.session_state["confirm_delete_note_id"] = None
                                _refresh_notes(profile_id)
                                st.session_state["notes_success"] = "Note deleted."
                                st.session_state["notes_error"] = None
                            except Exception as error:
                                _record_ui_failure("Deleting note", error)
                                st.session_state["notes_success"] = None
                                st.session_state["notes_error"] = _safe_notes_error(
                                    "Deleting note",
                                    error,
                                )
                                st.rerun()
                            else:
                                st.rerun()
                    with cancel_col:
                        if st.button("Cancel", key=f"cancel_delete_note_{note_key}"):
                            st.session_state["confirm_delete_note_id"] = None
                            st.rerun()
                else:
                    with action_col:
                        if st.button("Delete", key=f"delete_note_{index}_{note_key}"):
                            st.session_state["confirm_delete_note_id"] = note_key
                            st.rerun()


def render_ask_ai_section() -> None:
    st.header("Ask AI")
    with st.container(border=True):
        selected_profile = st.session_state.get("selected_profile")
        if not selected_profile:
            st.info("Select or create a profile before asking AI.")
            with st.form("ask_ai_disabled_form"):
                st.text_area("Question", height=90, disabled=True)
                st.form_submit_button("Ask AI", disabled=True)
            return

        profile_id = str(selected_profile.get("_id") or "").strip()
        if not profile_id:
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
            submitted = st.form_submit_button("Ask AI", type="primary")

        if submitted:
            if not question.strip():
                st.session_state["ask_ai_error"] = "Ask AI failed: question cannot be empty."
                st.rerun()

            try:
                profile_context = profiles.build_profile_context(selected_profile)
                with st.spinner("Asking AI..."):
                    answer = ai.ask_ai(
                        question,
                        profile_context,
                        _trusted_account_id(),
                        profile_id,
                        session_id=st.session_state["auth_session_id"],
                    )
                st.session_state["last_ai_answer"] = answer
                st.session_state["ask_ai_error"] = None
            except Exception as error:
                _record_ui_failure("Ask AI", error)
                st.session_state["last_ai_answer"] = ""
                st.session_state["ask_ai_error"] = _safe_ask_ai_error("Ask AI", error)
                st.rerun()
            else:
                st.rerun()

        last_answer = st.session_state.get("last_ai_answer")
        if last_answer:
            st.subheader("Last answer")
            with st.container(border=True):
                st.markdown(last_answer)


def main() -> None:
    st.set_page_config(
        page_title="Personal Fitness AI Assistant",
        layout="wide",
    )
    _initialize_ui_theme_state()
    _apply_ui_theme()
    _initialize_auth_session_state()
    _enforce_authentication_gate()
    initialize_session_state()

    _render_authenticated_header()
    st.title("Personal Fitness AI Assistant")
    st.caption(
        "This app provides general fitness information for planning and learning. "
        "It is not medical advice."
    )
    st.divider()

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
