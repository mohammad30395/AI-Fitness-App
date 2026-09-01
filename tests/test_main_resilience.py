import pytest

import main


class FakeSessionState(dict):
    pass


class StopCalled(Exception):
    pass


class RerunCalled(Exception):
    pass


class FakeForm:
    def __init__(self, fake_st):
        self.fake_st = fake_st

    def __enter__(self):
        return self.fake_st

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeTab:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeColumn(FakeTab):
    def __init__(self, fake_st=None):
        self.fake_st = fake_st

    def caption(self, *args, **kwargs):
        if self.fake_st is not None:
            self.fake_st.caption(*args, **kwargs)
        return None

    def metric(self, *args, **kwargs):
        return None

    def number_input(self, *args, **kwargs):
        if self.fake_st is not None:
            return self.fake_st.number_input(*args, **kwargs)
        return kwargs.get("value")

    def subheader(self, *args, **kwargs):
        if self.fake_st is not None:
            self.fake_st.subheader(*args, **kwargs)
        return None


class FakeStreamlit:
    def __init__(self):
        self.session_state = FakeSessionState()
        self.info_messages = []
        self.error_messages = []
        self.caption_messages = []
        self.markdown_calls = []
        self.page_config = None
        self.input_values = {}
        self.text_input_calls = []
        self.radio_calls = []
        self.selectbox_calls = []
        self.multiselect_calls = []
        self.columns_calls = []
        self.subheader_calls = []
        self.submit_value = False
        self.form_submit_values = {}
        self.form_submit_calls = []
        self.button_calls = []
        self.button_values = {}
        self.tab_labels = []
        self.headers = []
        self.private_ui_allowed = False
        self.events = []

    def set_page_config(self, **kwargs):
        self.page_config = kwargs

    def info(self, message):
        self.info_messages.append(message)

    def error(self, message):
        self.error_messages.append(message)

    def header(self, message):
        self.headers.append(message)
        self.events.append(("header", message))

    def subheader(self, *args, **kwargs):
        self.subheader_calls.append((args, kwargs))
        self.events.append(("subheader", args[0] if args else ""))
        return None

    def tabs(self, labels):
        self.tab_labels.append(tuple(labels))
        return [FakeTab() for _ in labels]

    def columns(self, spec, **kwargs):
        self.columns_calls.append((spec, kwargs))
        count = spec if isinstance(spec, int) else len(spec)
        return [FakeColumn(self) for _ in range(count)]

    def container(self, **kwargs):
        return FakeTab()

    def form(self, key):
        return FakeForm(self)

    def text_input(self, label, **kwargs):
        self.text_input_calls.append((label, kwargs))
        key = kwargs.get("key")
        if label in self.input_values:
            return self.input_values[label]
        if key in self.session_state:
            return self.session_state[key]
        return kwargs.get("value", "")

    def text_area(self, label, **kwargs):
        return self.input_values.get(label, kwargs.get("value", ""))

    def radio(self, label, **kwargs):
        self.radio_calls.append((label, kwargs))
        self.events.append(("radio", label))
        if label in self.input_values:
            return self.input_values[label]
        options = tuple(kwargs.get("options", ()))
        index = kwargs.get("index", 0)
        return options[index] if index is not None else None

    def selectbox(self, label, options, index=0, **kwargs):
        self.selectbox_calls.append((label, {"options": options, "index": index, **kwargs}))
        self.events.append(("selectbox", label))
        if label in self.input_values:
            return self.input_values[label]
        options = tuple(options)
        return options[index] if index is not None else None

    def multiselect(self, label, options, default=None, **kwargs):
        self.multiselect_calls.append(
            (label, {"options": options, "default": default, **kwargs})
        )
        self.events.append(("multiselect", label))
        if label in self.input_values:
            return self.input_values[label]
        return list(default or [])

    def number_input(self, label, **kwargs):
        return self.input_values.get(label, kwargs.get("value"))

    def form_submit_button(self, label, **kwargs):
        self.form_submit_calls.append((label, kwargs))
        self.events.append(("form_submit_button", label))
        key = kwargs.get("key")
        clicked = self.form_submit_values.get(key, False)
        if key is None:
            clicked = self.submit_value
        if clicked and kwargs.get("on_click"):
            kwargs["on_click"](*(kwargs.get("args") or ()), **(kwargs.get("kwargs") or {}))
        return clicked

    def button(self, label, **kwargs):
        self.button_calls.append((label, kwargs))
        self.events.append(("button", label))
        key = kwargs.get("key")
        clicked = self.button_values.get(key, self.button_values.get(label, False))
        if clicked and kwargs.get("on_click"):
            kwargs["on_click"](*(kwargs.get("args") or ()), **(kwargs.get("kwargs") or {}))
        return clicked

    def stop(self):
        raise StopCalled

    def rerun(self):
        raise RerunCalled

    def title(self, *args, **kwargs):
        if not self.private_ui_allowed:
            raise AssertionError("private UI must not render before authentication")

    def caption(self, *args, **kwargs):
        self.caption_messages.append(args[0] if args else "")
        self.events.append(("caption", args[0] if args else ""))
        if not self.private_ui_allowed:
            raise AssertionError("private UI must not render before authentication")

    def success(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def write(self, *args, **kwargs):
        return None

    def markdown(self, *args, **kwargs):
        self.markdown_calls.append((args, kwargs))
        return None

    def spinner(self, *args, **kwargs):
        return FakeTab()

    def divider(self, *args, **kwargs):
        if not self.private_ui_allowed:
            raise AssertionError("private UI must not render before authentication")


def seed_authenticated_session(fake_st, account_id="account-a", username="UserA"):
    fake_st.session_state.update(
        {
            "authenticated": True,
            "account_id": account_id,
            "username": username,
            "auth_session_id": f"session-{account_id}",
        }
    )


def test_auth_session_defaults_initialize_fresh_state(monkeypatch):
    fake_st = FakeStreamlit()
    monkeypatch.setattr(main, "st", fake_st)

    main._initialize_auth_session_state()

    assert fake_st.session_state["authenticated"] is False
    assert fake_st.session_state["account_id"] is None
    assert fake_st.session_state["username"] is None
    assert fake_st.session_state["auth_session_id"] is None


def test_auth_session_defaults_preserve_existing_authenticated_state(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.session_state.update(
        {
            "authenticated": True,
            "account_id": "account-1",
            "username": "casey",
            "auth_session_id": "session-1",
        }
    )
    monkeypatch.setattr(main, "st", fake_st)

    main._initialize_auth_session_state()

    assert fake_st.session_state["authenticated"] is True
    assert fake_st.session_state["account_id"] == "account-1"
    assert fake_st.session_state["username"] == "casey"
    assert fake_st.session_state["auth_session_id"] == "session-1"


def test_ui_theme_initializes_to_light_once(monkeypatch):
    fake_st = FakeStreamlit()
    monkeypatch.setattr(main, "st", fake_st)

    main._initialize_ui_theme_state()
    main._initialize_ui_theme_state()

    assert fake_st.session_state[main.UI_THEME_SESSION_KEY] == "light"


def test_ui_theme_allowed_values_are_exact_contract():
    assert main.UI_THEME_OPTIONS == ("light", "dark")
    assert set(main.UI_THEME_TOKENS) == {"light", "dark"}


def test_ui_theme_token_sets_share_required_visual_contract():
    required_tokens = set(main.UI_THEME_TOKEN_NAMES)

    assert required_tokens == {
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
        "focus_ring",
        "shadow",
        "success",
        "warning",
        "error",
    }
    assert set(main.UI_THEME_TOKENS["light"]) == required_tokens
    assert set(main.UI_THEME_TOKENS["dark"]) == required_tokens


def test_light_and_dark_theme_tokens_are_visually_distinct():
    assert main.UI_THEME_TOKENS["light"]["background"] != main.UI_THEME_TOKENS["dark"]["background"]
    assert main.UI_THEME_TOKENS["light"]["surface"] != main.UI_THEME_TOKENS["dark"]["surface"]
    assert main.UI_THEME_TOKENS["light"]["text"] != main.UI_THEME_TOKENS["dark"]["text"]


def test_ui_theme_defaults_to_light_without_public_runtime_theme_api(monkeypatch):
    fake_st = FakeStreamlit()
    monkeypatch.setattr(main, "st", fake_st)

    main._initialize_ui_theme_state()

    assert not hasattr(fake_st, "theme")
    assert fake_st.session_state[main.UI_THEME_SESSION_KEY] == "light"


def test_ui_theme_toggle_light_to_dark(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.session_state[main.UI_THEME_SESSION_KEY] = "light"
    monkeypatch.setattr(main, "st", fake_st)

    main._toggle_ui_theme()

    assert fake_st.session_state[main.UI_THEME_SESSION_KEY] == "dark"


def test_ui_theme_toggle_dark_to_light(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.session_state[main.UI_THEME_SESSION_KEY] = "dark"
    monkeypatch.setattr(main, "st", fake_st)

    main._toggle_ui_theme()

    assert fake_st.session_state[main.UI_THEME_SESSION_KEY] == "light"


def test_ui_theme_persists_across_initialization_reruns(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.session_state[main.UI_THEME_SESSION_KEY] = "dark"
    monkeypatch.setattr(main, "st", fake_st)

    main._initialize_ui_theme_state()
    main._initialize_ui_theme_state()

    assert fake_st.session_state[main.UI_THEME_SESSION_KEY] == "dark"


def test_invalid_ui_theme_state_normalizes_to_light(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.session_state[main.UI_THEME_SESSION_KEY] = "sepia"
    monkeypatch.setattr(main, "st", fake_st)

    main._initialize_ui_theme_state()

    assert fake_st.session_state[main.UI_THEME_SESSION_KEY] == "light"


def test_ui_theme_toggle_preserves_profile_and_workflow_state(monkeypatch):
    fake_st = FakeStreamlit()
    selected_profile = {"_id": "profile-a", "name": "A", "goals": ["Fat Loss"]}
    fake_st.session_state.update(
        {
            main.UI_THEME_SESSION_KEY: "light",
            "selected_profile_id": "profile-a",
            "selected_profile": selected_profile,
            "profiles": [selected_profile],
            "create_profile_form_goals_editor": [],
            "edit_profile_form_goals_editor_profile-a": ["Stay Active"],
            "nutrition": {"calories": 2100},
            "nutrition_draft": {"calories": 2200},
            "nutrition_draft_profile_id": "profile-a",
            "nutrition_draft_version": 3,
            "notes": [{"_id": "note-a", "text": "private note"}],
            "notes_profile_id": "profile-a",
            "confirm_delete_note_id": "note-a",
            "last_ai_answer": "existing answer",
            "ask_ai_error": "existing error",
        }
    )
    before = dict(fake_st.session_state)
    monkeypatch.setattr(main, "st", fake_st)

    main._toggle_ui_theme()

    expected = dict(before)
    expected[main.UI_THEME_SESSION_KEY] = "dark"
    assert fake_st.session_state == expected


def test_removed_starter_goal_does_not_reappear_after_theme_switch(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.session_state.update(
        {
            main.UI_THEME_SESSION_KEY: "light",
            "create_profile_form_goals_editor": [],
        }
    )
    monkeypatch.setattr(main, "st", fake_st)

    main._toggle_ui_theme()
    state_key = main._initialize_goal_editor_state(
        form_key="create_profile_form",
        is_edit=False,
    )

    assert fake_st.session_state[main.UI_THEME_SESSION_KEY] == "dark"
    assert fake_st.session_state[state_key] == []


def test_custom_goal_survives_theme_switch(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.session_state.update(
        {
            main.UI_THEME_SESSION_KEY: "dark",
            "create_profile_form_goals_editor": ["Run a marathon"],
            "edit_profile_form_goals_editor_profile-a": ["Improve mobility"],
        }
    )
    monkeypatch.setattr(main, "st", fake_st)

    main._toggle_ui_theme()

    assert fake_st.session_state["create_profile_form_goals_editor"] == ["Run a marathon"]
    assert fake_st.session_state["edit_profile_form_goals_editor_profile-a"] == [
        "Improve mobility"
    ]


def test_ui_theme_toggle_does_not_call_profile_or_ai_backends(monkeypatch):
    fake_st = FakeStreamlit()
    monkeypatch.setattr(main, "st", fake_st)

    def fail_backend_call(*args, **kwargs):
        raise AssertionError("theme toggle must not call backends")

    monkeypatch.setattr(main.profiles, "create_new_profile", fail_backend_call)
    monkeypatch.setattr(main.profiles, "save_profile_changes", fail_backend_call)
    monkeypatch.setattr(main.db, "create_profile", fail_backend_call)
    monkeypatch.setattr(main.db, "update_personal_information", fail_backend_call)
    monkeypatch.setattr(main.ai, "get_macros", fail_backend_call)
    monkeypatch.setattr(main.ai, "ask_ai", fail_backend_call)

    main._initialize_ui_theme_state()
    main._toggle_ui_theme()

    assert fake_st.session_state[main.UI_THEME_SESSION_KEY] == "dark"


def test_ui_theme_control_uses_top_right_button_and_callback(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.session_state[main.UI_THEME_SESSION_KEY] = "light"
    fake_st.button_values["ui_theme_toggle"] = True
    monkeypatch.setattr(main, "st", fake_st)

    main._render_theme_control()

    assert fake_st.columns_calls == [((6, 1), {"vertical_alignment": "center"})]
    assert fake_st.button_calls == [
        (
            "🌙 Dark",
            {
                "key": "ui_theme_toggle",
                "help": "Switch to dark mode",
                "on_click": main._toggle_ui_theme,
                "use_container_width": True,
            },
        )
    ]
    assert fake_st.session_state[main.UI_THEME_SESSION_KEY] == "dark"


def test_ui_theme_control_renders_before_main_profile_controls(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.private_ui_allowed = True
    seed_authenticated_session(fake_st, account_id="account-a")
    monkeypatch.setattr(main, "st", fake_st)

    def fake_refresh(select_profile_id=None):
        fake_st.session_state["profiles"] = []
        fake_st.session_state["selected_profile_id"] = None
        fake_st.session_state["selected_profile"] = None
        return True

    monkeypatch.setattr(main, "_refresh_profiles", fake_refresh)

    main.main()

    theme_button_index = fake_st.events.index(("button", "🌙 Dark"))
    gender_radio_index = fake_st.events.index(("radio", "Gender"))
    assert theme_button_index < gender_radio_index


def test_ui_theme_css_uses_tokens_without_js_or_private_api(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.session_state[main.UI_THEME_SESSION_KEY] = "dark"
    monkeypatch.setattr(main, "st", fake_st)

    main._apply_ui_theme()

    css = fake_st.markdown_calls[0][0][0]
    assert fake_st.markdown_calls[0][1] == {"unsafe_allow_html": True}
    assert "--fit-background: #111827;" in css
    assert "--fit-focus-ring:" in css
    assert "--fit-shadow:" in css
    assert "[data-testid=\"stAppViewContainer\"]" in css
    assert "[data-testid=\"stRadio\"]" in css
    assert "[data-testid=\"stSelectbox\"]" in css
    assert "<script" not in css.lower()
    assert "st._config" not in css
    assert "st-emotion-cache" not in css
    assert ".css-" not in css


def test_main_source_avoids_private_theme_api_and_javascript():
    source = main.__loader__.get_source(main.__name__)

    assert "st._config" not in source
    assert "streamlit.config" not in source
    assert "config.toml" not in source
    assert "<script" not in source.lower()
    assert "javascript:" not in source.lower()
    assert "components.html" not in source
    assert ".html(" not in source
    assert "st-emotion-cache" not in source
    assert ".css-" not in source


def test_trusted_account_id_comes_from_authenticated_session(monkeypatch):
    fake_st = FakeStreamlit()
    seed_authenticated_session(fake_st, account_id="account-a")
    monkeypatch.setattr(main, "st", fake_st)

    assert main._trusted_account_id() == "account-a"


def test_authenticated_session_requires_all_trusted_values(monkeypatch):
    fake_st = FakeStreamlit()
    monkeypatch.setattr(main, "st", fake_st)

    fake_st.session_state.update(
        {
            "authenticated": True,
            "account_id": "account-1",
            "username": "casey",
            "auth_session_id": "session-1",
        }
    )
    assert main._is_authenticated_session() is True

    invalid_states = [
        {"account_id": None},
        {"account_id": ""},
        {"username": ""},
        {"auth_session_id": None},
        {"authenticated": False},
    ]
    for overrides in invalid_states:
        fake_st.session_state.update(
            {
                "authenticated": True,
                "account_id": "account-1",
                "username": "casey",
                "auth_session_id": "session-1",
            }
        )
        fake_st.session_state.update(overrides)
        assert main._is_authenticated_session() is False


def test_reset_session_for_logout_clears_sensitive_state(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.session_state.update(
        {
            "authenticated": True,
            "account_id": "account-1",
            "username": "casey",
            "auth_session_id": "session-1",
            "selected_profile_id": "profile-1",
            "selected_profile": {"_id": "profile-1", "name": "Casey"},
            "profiles": [{"_id": "profile-1"}],
            "nutrition": {"calories": 2000},
            "notes": [{"_id": "note-1", "text": "private note"}],
            "last_ai_answer": "private answer",
            "create_profile_form_name": "Casey",
            "confirm_delete_note_id": "note-1",
        }
    )
    monkeypatch.setattr(main, "st", fake_st)

    main._reset_session_for_logout()

    assert fake_st.session_state == {
        "authenticated": False,
        "account_id": None,
        "username": None,
        "auth_session_id": None,
    }


def test_unauthenticated_main_stops_before_private_work(monkeypatch):
    fake_st = FakeStreamlit()
    monkeypatch.setattr(main, "st", fake_st)
    monkeypatch.setattr(
        main,
        "_refresh_profiles",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("profile refresh must not run before authentication")
        ),
    )

    try:
        main.main()
    except StopCalled:
        pass
    else:
        raise AssertionError("unauthenticated main should stop")

    assert fake_st.page_config == {
        "page_title": "Personal Fitness AI Assistant",
        "layout": "wide",
    }
    assert fake_st.info_messages == [
        "Authentication required."
    ]
    assert fake_st.tab_labels == [("Login", "Create Account")]
    assert fake_st.session_state == {
        "ui_theme": "light",
        "authenticated": False,
        "account_id": None,
        "username": None,
        "auth_session_id": None,
    }


def test_create_account_password_mismatch_does_not_call_backend(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    fake_st.input_values = {
        "Username": "TestUser",
        "Password": "long-password-1",
        "Confirm Password": "different-password",
    }
    monkeypatch.setattr(main, "st", fake_st)

    def fail_create_account(username, password):
        raise AssertionError("create_account must not be called when passwords differ")

    monkeypatch.setattr(main.auth, "create_account", fail_create_account)

    main._initialize_auth_session_state()
    main._render_create_account_form()

    assert fake_st.error_messages == ["Passwords do not match."]
    assert fake_st.session_state["authenticated"] is False
    assert fake_st.session_state["account_id"] is None
    assert fake_st.session_state["username"] is None
    assert fake_st.session_state["auth_session_id"] is None


def test_create_account_calls_backend_without_confirm_password(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    fake_st.input_values = {
        "Username": "TestUser",
        "Password": "long-password-1",
        "Confirm Password": "long-password-1",
    }
    monkeypatch.setattr(main, "st", fake_st)
    calls = []

    def fake_create_account(username, password):
        calls.append((username, password))
        return {"account_id": "account-test-id", "username": "TestUser"}

    monkeypatch.setattr(main.auth, "create_account", fake_create_account)

    main._initialize_auth_session_state()
    try:
        main._render_create_account_form()
    except RerunCalled:
        pass
    else:
        raise AssertionError("successful account creation should trigger rerun")

    assert calls == [("TestUser", "long-password-1")]


def test_successful_create_account_establishes_trusted_session(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    fake_st.input_values = {
        "Username": "TestUser",
        "Password": "long-password-1",
        "Confirm Password": "long-password-1",
    }
    monkeypatch.setattr(main, "st", fake_st)
    monkeypatch.setattr(
        main.auth,
        "create_account",
        lambda username, password: {"account_id": "account-test-id", "username": "TestUser"},
    )

    main._initialize_auth_session_state()
    try:
        main._render_create_account_form()
    except RerunCalled:
        pass
    else:
        raise AssertionError("successful account creation should trigger rerun")

    assert fake_st.session_state["authenticated"] is True
    assert fake_st.session_state["account_id"] == "account-test-id"
    assert fake_st.session_state["username"] == "TestUser"
    assert isinstance(fake_st.session_state["auth_session_id"], str)
    assert fake_st.session_state["auth_session_id"]


def test_successful_login_establishes_trusted_session(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    fake_st.input_values = {
        "Username": "LoginUser",
        "Password": "login-password-1",
    }
    monkeypatch.setattr(main, "st", fake_st)
    calls = []

    def fake_authenticate(username, password):
        calls.append((username, password))
        return {"account_id": "account-login-test", "username": "LoginUser"}

    monkeypatch.setattr(main.auth, "authenticate", fake_authenticate)

    main._initialize_auth_session_state()
    try:
        main._render_login_form()
    except RerunCalled:
        pass
    else:
        raise AssertionError("successful login should trigger rerun")

    assert calls == [("LoginUser", "login-password-1")]
    assert fake_st.session_state["authenticated"] is True
    assert fake_st.session_state["account_id"] == "account-login-test"
    assert fake_st.session_state["username"] == "LoginUser"
    assert isinstance(fake_st.session_state["auth_session_id"], str)
    assert fake_st.session_state["auth_session_id"]


def test_login_account_id_comes_only_from_backend_return(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    fake_st.input_values = {
        "Username": "LoginUser",
        "Password": "login-password-1",
        "account_id": "forged-account-id",
    }
    monkeypatch.setattr(main, "st", fake_st)
    monkeypatch.setattr(
        main.auth,
        "authenticate",
        lambda username, password: {"account_id": "backend-account-id", "username": "LoginUser"},
    )

    main._initialize_auth_session_state()
    try:
        main._render_login_form()
    except RerunCalled:
        pass
    else:
        raise AssertionError("successful login should trigger rerun")

    assert all(label != "account_id" for label, _kwargs in fake_st.text_input_calls)
    assert fake_st.session_state["account_id"] == "backend-account-id"


def test_wrong_password_login_is_generic_and_unauthenticated(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    fake_st.input_values = {
        "Username": "LoginUser",
        "Password": "wrong-password-1",
    }
    monkeypatch.setattr(main, "st", fake_st)

    def fake_authenticate(username, password):
        raise main.auth.AuthenticationError("Invalid username or password.")

    monkeypatch.setattr(main.auth, "authenticate", fake_authenticate)

    main._initialize_auth_session_state()
    main._render_login_form()

    assert fake_st.error_messages == ["Invalid username or password."]
    assert fake_st.session_state["authenticated"] is False
    assert fake_st.session_state["account_id"] is None
    assert fake_st.session_state["username"] is None
    assert fake_st.session_state["auth_session_id"] is None


def test_nonexistent_username_login_matches_wrong_password_response(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    fake_st.input_values = {
        "Username": "MissingUser",
        "Password": "login-password-1",
    }
    monkeypatch.setattr(main, "st", fake_st)

    def fake_authenticate(username, password):
        raise main.auth.AuthenticationError("Invalid username or password.")

    monkeypatch.setattr(main.auth, "authenticate", fake_authenticate)

    main._initialize_auth_session_state()
    main._render_login_form()

    assert fake_st.error_messages == ["Invalid username or password."]
    assert fake_st.session_state["authenticated"] is False
    assert fake_st.session_state["account_id"] is None


def test_login_unexpected_error_is_generic(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    fake_st.input_values = {
        "Username": "LoginUser",
        "Password": "login-password-1",
    }
    monkeypatch.setattr(main, "st", fake_st)

    def fake_authenticate(username, password):
        raise RuntimeError("AstraCS:super-secret-token password_hash private detail")

    monkeypatch.setattr(main.auth, "authenticate", fake_authenticate)

    main._initialize_auth_session_state()
    main._render_login_form()

    assert fake_st.error_messages == ["Unable to log in right now."]
    assert "AstraCS" not in fake_st.error_messages[0]
    assert "password_hash" not in fake_st.error_messages[0]
    assert fake_st.session_state["authenticated"] is False
    assert fake_st.session_state["account_id"] is None


def test_logout_clears_sensitive_state_and_reruns(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.private_ui_allowed = True
    fake_st.button_values = {"Logout": True}
    fake_st.session_state.update(
        {
            "authenticated": True,
            "account_id": "account-a",
            "username": "UserA",
            "auth_session_id": "session-a",
            "selected_profile_id": "profile-a",
            "selected_profile": {"_id": "profile-a"},
            "profiles": [{"_id": "profile-a"}],
            "nutrition": {"calories": 2000},
            "notes": [{"_id": "note-a", "text": "private"}],
            "last_ai_answer": "private answer",
            "confirm_delete_note_id": "note-a",
        }
    )
    monkeypatch.setattr(main, "st", fake_st)

    try:
        main._render_authenticated_header()
    except RerunCalled:
        pass
    else:
        raise AssertionError("logout should trigger rerun")

    assert fake_st.session_state == {
        "authenticated": False,
        "account_id": None,
        "username": None,
        "auth_session_id": None,
    }


def test_auth_session_id_rotates_between_logins(monkeypatch):
    fake_st = FakeStreamlit()
    monkeypatch.setattr(main, "st", fake_st)

    main._initialize_auth_session_state()
    main._establish_authenticated_session(
        {"account_id": "account-login-test", "username": "LoginUser"}
    )
    first_session_id = fake_st.session_state["auth_session_id"]

    main._reset_session_for_logout()
    main._establish_authenticated_session(
        {"account_id": "account-login-test", "username": "LoginUser"}
    )
    second_session_id = fake_st.session_state["auth_session_id"]

    assert first_session_id
    assert second_session_id
    assert first_session_id != second_session_id


def test_refresh_profiles_uses_authenticated_account_for_list_and_read(monkeypatch):
    fake_st = FakeStreamlit()
    seed_authenticated_session(fake_st, account_id="account-a")
    monkeypatch.setattr(main, "st", fake_st)
    calls = []

    def fake_get_all_profiles(account_id):
        calls.append(("list", account_id))
        return [{"_id": "profile-a", "name": "A", "goals": []}]

    def fake_get_profile_by_id(account_id, profile_id):
        calls.append(("read", account_id, profile_id))
        return {"_id": profile_id, "name": "A", "goals": []}

    monkeypatch.setattr(main.profiles, "get_all_profiles", fake_get_all_profiles)
    monkeypatch.setattr(main.profiles, "get_profile_by_id", fake_get_profile_by_id)

    assert main._refresh_profiles() is True

    assert calls == [
        ("list", "account-a"),
        ("read", "account-a", "profile-a"),
    ]
    assert fake_st.session_state["selected_profile_id"] == "profile-a"


def test_refresh_profiles_uses_account_b_and_clears_stale_account_a_selection(monkeypatch):
    fake_st = FakeStreamlit()
    seed_authenticated_session(fake_st, account_id="account-b", username="UserB")
    fake_st.session_state["selected_profile_id"] = "profile-a"
    monkeypatch.setattr(main, "st", fake_st)
    calls = []

    def fake_get_all_profiles(account_id):
        calls.append(("list", account_id))
        return [{"_id": "profile-b", "name": "B", "goals": []}]

    def fake_get_profile_by_id(account_id, profile_id):
        calls.append(("read", account_id, profile_id))
        return {"_id": profile_id, "name": "B", "goals": []}

    monkeypatch.setattr(main.profiles, "get_all_profiles", fake_get_all_profiles)
    monkeypatch.setattr(main.profiles, "get_profile_by_id", fake_get_profile_by_id)

    assert main._refresh_profiles() is True

    assert calls == [
        ("list", "account-b"),
        ("read", "account-b", "profile-b"),
    ]
    assert fake_st.session_state["selected_profile_id"] == "profile-b"
    assert fake_st.session_state["selected_profile"]["_id"] == "profile-b"


def test_profile_creation_passes_trusted_account_id_without_owner_field(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    seed_authenticated_session(fake_st, account_id="account-a")
    fake_st.input_values = {
        "Name": "Profile A",
        "Age": 31,
        "Weight": 72.5,
        "Height": 180.0,
        "Gender": "Male",
        "Activity Level": "Moderately Active",
        "owner_account_id": "account-b",
    }
    monkeypatch.setattr(main, "st", fake_st)
    calls = []
    refreshes = []

    def fake_create_new_profile(**kwargs):
        calls.append(kwargs)
        return "profile-new"

    monkeypatch.setattr(main.profiles, "create_new_profile", fake_create_new_profile)
    monkeypatch.setattr(main, "_refresh_profiles", lambda select_profile_id=None: refreshes.append(select_profile_id) or True)

    try:
        main._render_profile_form(mode="create")
    except RerunCalled:
        pass
    else:
        raise AssertionError("profile creation should rerun")

    assert calls == [
        {
            "account_id": "account-a",
            "name": "Profile A",
            "age": 31,
            "weight": 72.5,
            "height": 180.0,
            "gender": "Male",
            "activity_level": "Moderately Active",
            "goals": ["Muscle Gain"],
        }
    ]
    assert "owner_account_id" not in calls[0]
    assert refreshes == ["profile-new"]


def test_profile_edit_passes_trusted_account_id_and_profile_id(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    seed_authenticated_session(fake_st, account_id="account-a")
    fake_st.session_state["selected_profile_id"] = "profile-a"
    fake_st.input_values = {
        "Name": "Profile A",
        "Age": 32,
        "Weight": 74.0,
        "Height": 181.0,
        "owner_account_id": "account-b",
    }
    monkeypatch.setattr(main, "st", fake_st)
    calls = []

    def fake_save_profile_changes(account_id, profile_id, **updates):
        calls.append((account_id, profile_id, updates))
        return {"_id": profile_id, **updates}

    monkeypatch.setattr(main.profiles, "save_profile_changes", fake_save_profile_changes)
    monkeypatch.setattr(main, "_refresh_profiles", lambda select_profile_id=None: True)

    try:
        main._render_profile_form(
            mode="edit",
            profile={
                "_id": "profile-a",
                "gender": "unspecified",
                "activity_level": "active",
                "goals": ["Improve endurance"],
            },
        )
    except RerunCalled:
        pass
    else:
        raise AssertionError("profile edit should rerun")

    assert calls == [
        (
            "account-a",
            "profile-a",
            {
                "name": "Profile A",
                "age": 32,
                "weight": 74.0,
                "height": 181.0,
                "gender": "unspecified",
                "activity_level": "active",
                "goals": ["Improve endurance"],
            },
        )
    ]
    assert "owner_account_id" not in calls[0][2]


def test_profile_create_uses_native_choice_widgets_and_goal_editor(monkeypatch):
    fake_st = FakeStreamlit()
    monkeypatch.setattr(main, "st", fake_st)

    main._render_profile_form(mode="create")

    assert fake_st.radio_calls == [
        (
            "Gender",
            {
                "options": main.GENDER_OPTIONS,
                "index": None,
                "key": "create_profile_form_gender_choice",
            },
        )
    ]
    assert fake_st.selectbox_calls == [
        (
            "Activity Level",
            {
                "options": main.ACTIVITY_LEVEL_OPTIONS,
                "index": None,
                "key": "create_profile_form_activity_level_choice",
                "placeholder": "Choose activity level",
            },
        )
    ]
    assert fake_st.multiselect_calls == []
    assert fake_st.session_state["create_profile_form_goals_editor"] == ["Muscle Gain"]
    assert fake_st.columns_calls == [
        (3, {}),
        ((4, 1), {"vertical_alignment": "center"}),
        ((4, 1), {}),
    ]
    assert fake_st.subheader_calls == [(("Goals",), {})]
    assert any(label == "−" for label, _kwargs in fake_st.form_submit_calls)
    assert any(label == "+" for label, _kwargs in fake_st.form_submit_calls)


def test_new_profile_goal_editor_initializes_default_once_and_allows_removal(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.form_submit_values["create_profile_form_goals_editor_remove_0"] = True
    monkeypatch.setattr(main, "st", fake_st)

    main._render_profile_form(mode="create")
    assert fake_st.session_state["create_profile_form_goals_editor"] == []

    fake_st.form_submit_values = {}
    main._render_profile_form(mode="create")
    assert fake_st.session_state["create_profile_form_goals_editor"] == []


def test_existing_profile_goal_editor_initializes_exactly_without_default(monkeypatch):
    fake_st = FakeStreamlit()
    monkeypatch.setattr(main, "st", fake_st)

    main._render_profile_form(
        mode="edit",
        profile={
            "_id": "profile-a",
            "gender": "Female",
            "activity_level": "Very Active",
            "goals": ["Build strength", "Improve endurance"],
        },
    )

    assert fake_st.radio_calls[0][1]["options"] == main.GENDER_OPTIONS
    assert fake_st.radio_calls[0][1]["index"] == 1
    assert fake_st.selectbox_calls[0][1]["options"] == main.ACTIVITY_LEVEL_OPTIONS
    assert fake_st.selectbox_calls[0][1]["index"] == 3
    assert fake_st.multiselect_calls == []
    assert fake_st.session_state["edit_profile_form_goals_editor_profile-a"] == [
        "Build strength",
        "Improve endurance",
    ]
    assert "Muscle Gain" not in fake_st.session_state["edit_profile_form_goals_editor_profile-a"]


def test_existing_empty_profile_goal_editor_remains_empty(monkeypatch):
    fake_st = FakeStreamlit()
    monkeypatch.setattr(main, "st", fake_st)

    main._render_profile_form(
        mode="edit",
        profile={"_id": "profile-a", "activity_level": "active", "goals": []},
    )

    assert fake_st.session_state["edit_profile_form_goals_editor_profile-a"] == []
    assert fake_st.selectbox_calls[0][1]["options"][0] == "active"
    assert fake_st.selectbox_calls[0][1]["index"] == 0


def test_goal_editor_adds_custom_goal_and_trims_whitespace(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.session_state["create_profile_form_goals_editor"] = []
    fake_st.session_state["create_profile_form_goal_add_open"] = True
    fake_st.session_state["create_profile_form_goal_input"] = "  Run a marathon  "
    fake_st.form_submit_values["create_profile_form_goals_editor_add_goal"] = True
    monkeypatch.setattr(main, "st", fake_st)

    main._render_profile_form(mode="create")

    assert fake_st.session_state["create_profile_form_goals_editor"] == ["Run a marathon"]
    assert fake_st.session_state["create_profile_form_goal_input"] == ""
    assert fake_st.session_state["create_profile_form_goal_add_open"] is False
    assert fake_st.session_state["create_profile_form_goal_error"] is None


def test_goal_editor_rejects_blank_and_duplicate_goals(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.session_state["create_profile_form_goals_editor"] = ["Muscle Gain"]
    fake_st.session_state["create_profile_form_goal_add_open"] = True
    fake_st.session_state["create_profile_form_goal_input"] = "   "
    fake_st.form_submit_values["create_profile_form_goals_editor_add_goal"] = True
    monkeypatch.setattr(main, "st", fake_st)

    main._render_profile_form(mode="create")

    assert fake_st.session_state["create_profile_form_goals_editor"] == ["Muscle Gain"]
    assert fake_st.session_state["create_profile_form_goal_error"] == "Enter a goal before adding."

    fake_st.session_state["create_profile_form_goal_input"] = "Muscle Gain"
    main._render_profile_form(mode="create")

    assert fake_st.session_state["create_profile_form_goals_editor"] == ["Muscle Gain"]
    assert fake_st.session_state["create_profile_form_goal_error"] == "That goal is already in the list."


def test_goal_editor_adds_multiple_custom_goals(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.session_state["create_profile_form_goals_editor"] = []
    monkeypatch.setattr(main, "st", fake_st)

    main._add_goal_to_editor(
        "create_profile_form_goals_editor",
        "goal_input",
        "goal_error",
        "goal_add_open",
    )
    fake_st.session_state["goal_input"] = "Improve flexibility"
    main._add_goal_to_editor(
        "create_profile_form_goals_editor",
        "goal_input",
        "goal_error",
        "goal_add_open",
    )
    fake_st.session_state["goal_input"] = "Bench press 100 kg"
    main._add_goal_to_editor(
        "create_profile_form_goals_editor",
        "goal_input",
        "goal_error",
        "goal_add_open",
    )

    assert fake_st.session_state["create_profile_form_goals_editor"] == [
        "Improve flexibility",
        "Bench press 100 kg",
    ]


def test_final_new_profile_goal_acceptance_flow_and_theme_preservation(monkeypatch):
    fake_st = FakeStreamlit()
    monkeypatch.setattr(main, "st", fake_st)

    def fail_persistence(*args, **kwargs):
        raise AssertionError("non-submit goal/theme actions must not persist")

    monkeypatch.setattr(main.profiles, "create_new_profile", fail_persistence)
    monkeypatch.setattr(main.profiles, "save_profile_changes", fail_persistence)
    monkeypatch.setattr(main.db, "create_profile", fail_persistence)
    monkeypatch.setattr(main.db, "update_personal_information", fail_persistence)

    state_key = main._initialize_goal_editor_state(
        form_key="create_profile_form",
        is_edit=False,
    )
    assert fake_st.session_state[state_key] == ["Muscle Gain"]

    main._remove_goal_from_editor(state_key, 0, "goal_error")
    assert fake_st.session_state[state_key] == []

    rerun_state_key = main._initialize_goal_editor_state(
        form_key="create_profile_form",
        is_edit=False,
    )
    assert rerun_state_key == state_key
    assert fake_st.session_state[state_key] == []

    for goal in ("Fat Loss", "Run a half marathon", "Improve flexibility"):
        fake_st.session_state["goal_input"] = goal
        main._add_goal_to_editor(state_key, "goal_input", "goal_error", "goal_add_open")

    fake_st.session_state["goal_input"] = "   "
    main._add_goal_to_editor(state_key, "goal_input", "goal_error", "goal_add_open")
    assert fake_st.session_state["goal_error"] == "Enter a goal before adding."

    fake_st.session_state["goal_input"] = "Fat Loss"
    main._add_goal_to_editor(state_key, "goal_input", "goal_error", "goal_add_open")
    assert fake_st.session_state["goal_error"] == "That goal is already in the list."

    main._remove_goal_from_editor(state_key, 2, "goal_error")
    assert fake_st.session_state[state_key] == ["Fat Loss", "Run a half marathon"]

    fake_st.session_state[main.UI_THEME_SESSION_KEY] = "light"
    main._toggle_ui_theme()
    assert fake_st.session_state[main.UI_THEME_SESSION_KEY] == "dark"
    assert fake_st.session_state[state_key] == ["Fat Loss", "Run a half marathon"]


def test_goal_editor_removes_one_goal_and_can_remove_final_goal(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.session_state["create_profile_form_goals_editor"] = [
        "Muscle Gain",
        "Run a marathon",
        "Improve flexibility",
    ]
    monkeypatch.setattr(main, "st", fake_st)

    main._remove_goal_from_editor("create_profile_form_goals_editor", 1, "goal_error")
    assert fake_st.session_state["create_profile_form_goals_editor"] == [
        "Muscle Gain",
        "Improve flexibility",
    ]

    main._remove_goal_from_editor("create_profile_form_goals_editor", 1, "goal_error")
    main._remove_goal_from_editor("create_profile_form_goals_editor", 0, "goal_error")
    assert fake_st.session_state["create_profile_form_goals_editor"] == []


def test_long_special_and_twenty_goal_state_remains_ordered_list(monkeypatch):
    fake_st = FakeStreamlit()
    state_key = "create_profile_form_goals_editor"
    error_key = "goal_error"
    input_key = "goal_input"
    open_key = "goal_add_open"
    fake_st.session_state[state_key] = []
    monkeypatch.setattr(main, "st", fake_st)

    unusual_goals = [
        "Complete a half marathon without stopping",
        "Improve ankle & hip mobility",
        "Strength — upper body",
        "Exercise 4 times / week",
    ]
    for goal in unusual_goals:
        fake_st.session_state[input_key] = goal
        main._add_goal_to_editor(state_key, input_key, error_key, open_key)

    for number in range(1, 21):
        fake_st.session_state[input_key] = f"Goal {number:02d}"
        main._add_goal_to_editor(state_key, input_key, error_key, open_key)

    expected_goals = unusual_goals + [f"Goal {number:02d}" for number in range(1, 21)]
    assert fake_st.session_state[state_key] == expected_goals
    assert all(isinstance(goal, str) for goal in fake_st.session_state[state_key])

    fake_st.session_state[input_key] = "Goal 07"
    main._add_goal_to_editor(state_key, input_key, error_key, open_key)
    assert fake_st.session_state[state_key] == expected_goals
    assert fake_st.session_state[error_key] == "That goal is already in the list."

    main._remove_goal_from_editor(state_key, 2, error_key)
    assert fake_st.session_state[state_key] == [
        *unusual_goals[:2],
        unusual_goals[3],
        *[f"Goal {number:02d}" for number in range(1, 21)],
    ]


def test_goal_editor_actions_do_not_call_profile_persistence(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.form_submit_values["create_profile_form_goals_editor_remove_0"] = True
    monkeypatch.setattr(main, "st", fake_st)

    def fail_create(**kwargs):
        raise AssertionError("create should not be called for goal editor actions")

    monkeypatch.setattr(main.profiles, "create_new_profile", fail_create)

    main._render_profile_form(mode="create")

    assert fake_st.session_state["create_profile_form_goals_editor"] == []


def test_goal_editor_plus_opens_add_input_without_persistence(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.form_submit_values["create_profile_form_goals_editor_show_add_goal"] = True
    monkeypatch.setattr(main, "st", fake_st)

    def fail_create(**kwargs):
        raise AssertionError("create should not be called by +")

    monkeypatch.setattr(main.profiles, "create_new_profile", fail_create)

    main._render_profile_form(mode="create")

    assert fake_st.session_state["create_profile_form_goal_add_open"] is True
    assert fake_st.session_state["create_profile_form_goal_error"] is None


def test_profile_choice_and_goal_typing_do_not_persist_without_submit(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.session_state["create_profile_form_goal_add_open"] = True
    fake_st.input_values = {
        "Gender": "Female",
        "Activity Level": "Very Active",
    }
    monkeypatch.setattr(main, "st", fake_st)

    def fail_persistence(*args, **kwargs):
        raise AssertionError("form field interaction must not persist without submit")

    monkeypatch.setattr(main.profiles, "create_new_profile", fail_persistence)
    monkeypatch.setattr(main.profiles, "save_profile_changes", fail_persistence)
    monkeypatch.setattr(main.db, "create_profile", fail_persistence)
    monkeypatch.setattr(main.db, "update_personal_information", fail_persistence)

    main._render_profile_form(mode="create")

    assert fake_st.radio_calls[0][0] == "Gender"
    assert fake_st.selectbox_calls[0][0] == "Activity Level"
    assert fake_st.text_input_calls[-1][0] == "New Goal"


def test_profile_submit_receives_current_goal_editor_list(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    seed_authenticated_session(fake_st, account_id="account-a")
    fake_st.session_state["create_profile_form_goals_editor"] = [
        "Run a marathon",
        "Improve flexibility",
    ]
    fake_st.input_values = {
        "Name": "Profile A",
        "Age": 31,
        "Weight": 72.5,
        "Height": 180.0,
        "Gender": "Male",
        "Activity Level": "Sedentary",
    }
    monkeypatch.setattr(main, "st", fake_st)
    calls = []

    def fake_create_new_profile(**kwargs):
        calls.append(kwargs)
        return "profile-new"

    monkeypatch.setattr(main.profiles, "create_new_profile", fake_create_new_profile)
    monkeypatch.setattr(main, "_refresh_profiles", lambda select_profile_id=None: True)

    try:
        main._render_profile_form(mode="create")
    except RerunCalled:
        pass
    else:
        raise AssertionError("profile creation should rerun")

    assert calls[0]["goals"] == ["Run a marathon", "Improve flexibility"]
    assert "create_profile_form_goals_editor" not in fake_st.session_state


def test_profile_switching_refreshes_goal_editor_state_both_directions(monkeypatch):
    fake_st = FakeStreamlit()
    monkeypatch.setattr(main, "st", fake_st)

    main._set_selected_profile({"_id": "profile-a", "goals": ["Fat Loss"]})
    main._render_profile_form(mode="edit", profile=fake_st.session_state["selected_profile"])
    assert fake_st.session_state["edit_profile_form_goals_editor_profile-a"] == ["Fat Loss"]

    main._set_selected_profile({"_id": "profile-b", "goals": ["Stay Active", "Run 5 km"]})
    main._render_profile_form(mode="edit", profile=fake_st.session_state["selected_profile"])
    assert "edit_profile_form_goals_editor_profile-a" not in fake_st.session_state
    assert fake_st.session_state["edit_profile_form_goals_editor_profile-b"] == [
        "Stay Active",
        "Run 5 km",
    ]

    main._set_selected_profile({"_id": "profile-a", "goals": ["Fat Loss"]})
    main._render_profile_form(mode="edit", profile=fake_st.session_state["selected_profile"])
    assert "edit_profile_form_goals_editor_profile-b" not in fake_st.session_state
    assert fake_st.session_state["edit_profile_form_goals_editor_profile-a"] == ["Fat Loss"]


def test_profile_switching_refreshes_gender_activity_and_goal_state(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.session_state.update(
        {
            "profiles": [{"_id": "profile-a"}, {"_id": "profile-b"}],
            "last_ai_answer": "existing answer",
        }
    )
    monkeypatch.setattr(main, "st", fake_st)

    profile_a = {
        "_id": "profile-a",
        "gender": "Male",
        "activity_level": "Sedentary",
        "goals": ["Fat Loss"],
    }
    profile_b = {
        "_id": "profile-b",
        "gender": "Female",
        "activity_level": "Very Active",
        "goals": ["Stay Active", "Run 5 km"],
    }

    for profile, gender_index, activity_index in (
        (profile_a, 0, 0),
        (profile_b, 1, 3),
        (profile_a, 0, 0),
        (profile_b, 1, 3),
    ):
        profile_id = profile["_id"]
        fake_st.radio_calls = []
        fake_st.selectbox_calls = []
        fake_st.session_state[f"edit_profile_form_goal_input_{profile_id}"] = "stale input"
        fake_st.session_state[f"edit_profile_form_goal_error_{profile_id}"] = "stale error"

        main._set_selected_profile(profile)
        main._render_profile_form(mode="edit", profile=profile)

        assert fake_st.radio_calls[0][1]["index"] == gender_index
        assert fake_st.selectbox_calls[0][1]["index"] == activity_index
        assert fake_st.session_state[f"edit_profile_form_goals_editor_{profile_id}"] == profile[
            "goals"
        ]
        assert f"edit_profile_form_goal_input_{profile_id}" not in fake_st.session_state
        assert f"edit_profile_form_goal_error_{profile_id}" not in fake_st.session_state

    assert fake_st.session_state["last_ai_answer"] == "existing answer"


def test_unsaved_edit_goals_survive_repeated_theme_toggles_without_persistence(monkeypatch):
    fake_st = FakeStreamlit()
    state_key = "edit_profile_form_goals_editor_profile-a"
    fake_st.session_state.update(
        {
            main.UI_THEME_SESSION_KEY: "light",
            state_key: ["Fat Loss", "Stay Active"],
            "goal_input": "Mobility work",
        }
    )
    monkeypatch.setattr(main, "st", fake_st)

    def fail_persistence(*args, **kwargs):
        raise AssertionError("theme and temporary goal edits must not persist")

    monkeypatch.setattr(main.profiles, "save_profile_changes", fail_persistence)
    monkeypatch.setattr(main.db, "update_personal_information", fail_persistence)

    main._add_goal_to_editor(state_key, "goal_input", "goal_error", "goal_add_open")
    assert fake_st.session_state[state_key] == ["Fat Loss", "Stay Active", "Mobility work"]

    main._toggle_ui_theme()
    assert fake_st.session_state[main.UI_THEME_SESSION_KEY] == "dark"
    assert fake_st.session_state[state_key] == ["Fat Loss", "Stay Active", "Mobility work"]

    main._toggle_ui_theme()
    assert fake_st.session_state[main.UI_THEME_SESSION_KEY] == "light"
    assert fake_st.session_state[state_key] == ["Fat Loss", "Stay Active", "Mobility work"]

    main._remove_goal_from_editor(state_key, 0, "goal_error")
    main._toggle_ui_theme()

    assert fake_st.session_state[main.UI_THEME_SESSION_KEY] == "dark"
    assert fake_st.session_state[state_key] == ["Stay Active", "Mobility work"]


def test_existing_legacy_profile_save_preserves_values_exactly(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    seed_authenticated_session(fake_st, account_id="account-a")
    fake_st.session_state["selected_profile_id"] = "profile-legacy"
    fake_st.input_values = {
        "Name": "Legacy Profile",
        "Age": 40,
        "Weight": 80.0,
        "Height": 175.0,
    }
    monkeypatch.setattr(main, "st", fake_st)
    calls = []

    def fake_save_profile_changes(account_id, profile_id, **updates):
        calls.append((account_id, profile_id, updates))
        return {"_id": profile_id, **updates}

    monkeypatch.setattr(main.profiles, "save_profile_changes", fake_save_profile_changes)
    monkeypatch.setattr(main, "_refresh_profiles", lambda select_profile_id=None: True)

    try:
        main._render_profile_form(
            mode="edit",
            profile={
                "_id": "profile-legacy",
                "name": "Legacy Profile",
                "age": 40,
                "weight": 80.0,
                "height": 175.0,
                "gender": "unspecified",
                "activity_level": "moderate",
                "goals": ["Build strength", "Improve endurance"],
            },
        )
    except RerunCalled:
        pass
    else:
        raise AssertionError("profile edit should rerun")

    assert calls == [
        (
            "account-a",
            "profile-legacy",
            {
                "name": "Legacy Profile",
                "age": 40,
                "weight": 80.0,
                "height": 175.0,
                "gender": "unspecified",
                "activity_level": "moderate",
                "goals": ["Build strength", "Improve endurance"],
            },
        )
    ]


def test_existing_empty_goals_save_remains_empty(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    seed_authenticated_session(fake_st, account_id="account-a")
    fake_st.session_state["selected_profile_id"] = "profile-empty"
    fake_st.input_values = {
        "Name": "Empty Goals",
        "Age": 35,
        "Weight": 75.0,
        "Height": 170.0,
    }
    monkeypatch.setattr(main, "st", fake_st)
    calls = []

    def fake_save_profile_changes(account_id, profile_id, **updates):
        calls.append(updates)
        return {"_id": profile_id, **updates}

    monkeypatch.setattr(main.profiles, "save_profile_changes", fake_save_profile_changes)
    monkeypatch.setattr(main, "_refresh_profiles", lambda select_profile_id=None: True)

    try:
        main._render_profile_form(
            mode="edit",
            profile={
                "_id": "profile-empty",
                "name": "Empty Goals",
                "age": 35,
                "weight": 75.0,
                "height": 170.0,
                "gender": "Male",
                "activity_level": "Sedentary",
                "goals": [],
            },
        )
    except RerunCalled:
        pass
    else:
        raise AssertionError("profile edit should rerun")

    assert calls[0]["goals"] == []


def test_successful_edit_save_synchronizes_goal_editor_state(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    seed_authenticated_session(fake_st, account_id="account-a")
    fake_st.session_state["selected_profile_id"] = "profile-a"
    fake_st.session_state["edit_profile_form_goals_editor_profile-a"] = ["Run a marathon"]
    fake_st.input_values = {
        "Name": "Profile A",
        "Age": 32,
        "Weight": 74.0,
        "Height": 181.0,
        "Gender": "Male",
        "Activity Level": "Sedentary",
    }
    monkeypatch.setattr(main, "st", fake_st)

    def fake_save_profile_changes(account_id, profile_id, **updates):
        return {"_id": profile_id, **updates}

    monkeypatch.setattr(main.profiles, "save_profile_changes", fake_save_profile_changes)
    monkeypatch.setattr(main, "_refresh_profiles", lambda select_profile_id=None: True)

    try:
        main._render_profile_form(
            mode="edit",
            profile={"_id": "profile-a", "gender": "Male", "activity_level": "Sedentary"},
        )
    except RerunCalled:
        pass
    else:
        raise AssertionError("profile edit should rerun")

    assert fake_st.session_state["edit_profile_form_goals_editor_profile-a"] == [
        "Run a marathon"
    ]


def test_profile_edit_saves_intentional_canonical_replacements(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    seed_authenticated_session(fake_st, account_id="account-a")
    fake_st.session_state["selected_profile_id"] = "profile-a"
    fake_st.session_state["edit_profile_form_goals_editor_profile-a"] = ["Muscle Gain"]
    fake_st.input_values = {
        "Name": "Profile A",
        "Age": 32,
        "Weight": 74.0,
        "Height": 181.0,
        "Gender": "Other",
        "Activity Level": "Very Active",
    }
    monkeypatch.setattr(main, "st", fake_st)
    calls = []

    def fake_save_profile_changes(account_id, profile_id, **updates):
        calls.append((account_id, profile_id, updates))
        return {"_id": profile_id, **updates}

    monkeypatch.setattr(main.profiles, "save_profile_changes", fake_save_profile_changes)
    monkeypatch.setattr(main, "_refresh_profiles", lambda select_profile_id=None: True)

    try:
        main._render_profile_form(
            mode="edit",
            profile={
                "_id": "profile-a",
                "gender": "unspecified",
                "activity_level": "moderate",
                "goals": ["Build strength"],
            },
        )
    except RerunCalled:
        pass
    else:
        raise AssertionError("profile edit should rerun")

    assert calls[0][2]["gender"] == "Other"
    assert calls[0][2]["activity_level"] == "Very Active"
    assert calls[0][2]["goals"] == ["Muscle Gain"]


def test_selected_profile_change_clears_only_edit_choice_widget_state(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.session_state.update(
        {
            "selected_profile_id": "profile-a",
            "selected_profile": {"_id": "profile-a"},
            "profiles": [{"_id": "profile-a"}],
            "nutrition": {"calories": 2000},
            "last_ai_answer": "existing answer",
            "edit_profile_form_gender_choice": "Male",
            "edit_profile_form_activity_level_choice": "Sedentary",
            "edit_profile_form_goals_multiselect": ["Fat Loss"],
            "edit_profile_form_goals_editor_profile-a": ["Fat Loss"],
            "edit_profile_form_goal_input_profile-a": "Run",
            "edit_profile_form_goal_add_open_profile-a": True,
            "edit_profile_form_goal_error_profile-a": "Duplicate",
        }
    )
    monkeypatch.setattr(main, "st", fake_st)

    main._set_selected_profile(
        {
            "_id": "profile-b",
            "gender": "Female",
            "activity_level": "Very Active",
            "goals": ["Stay Active"],
        }
    )

    assert "edit_profile_form_gender_choice" not in fake_st.session_state
    assert "edit_profile_form_activity_level_choice" not in fake_st.session_state
    assert "edit_profile_form_goals_multiselect" not in fake_st.session_state
    assert "edit_profile_form_goals_editor_profile-a" not in fake_st.session_state
    assert "edit_profile_form_goal_input_profile-a" not in fake_st.session_state
    assert "edit_profile_form_goal_add_open_profile-a" not in fake_st.session_state
    assert "edit_profile_form_goal_error_profile-a" not in fake_st.session_state
    assert fake_st.session_state["profiles"] == [{"_id": "profile-a"}]
    assert fake_st.session_state["last_ai_answer"] == "existing answer"


def test_nutrition_save_passes_trusted_account_id(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    fake_st.private_ui_allowed = True
    seed_authenticated_session(fake_st, account_id="account-a")
    fake_st.session_state.update(
        {
            "selected_profile": {
                "_id": "profile-a",
                "name": "Profile A",
                "goals": [],
                "nutrition": {"calories": 2000, "protein": 120, "fat": 70, "carbs": 250},
            },
            "nutrition": {"calories": 2000, "protein": 120, "fat": 70, "carbs": 250},
            "nutrition_draft_version": 0,
        }
    )
    fake_st.input_values = {
        "Calories (kcal/day)": 2100.0,
        "Protein (g/day)": 130.0,
        "Fat (g/day)": 75.0,
        "Carbs (g/day)": 260.0,
    }
    monkeypatch.setattr(main, "st", fake_st)
    calls = []

    def fake_save_profile_changes(account_id, profile_id, **updates):
        calls.append((account_id, profile_id, updates))
        return {"_id": profile_id, "nutrition": updates["nutrition"], "goals": []}

    monkeypatch.setattr(main.profiles, "save_profile_changes", fake_save_profile_changes)
    monkeypatch.setattr(main, "_refresh_profiles", lambda select_profile_id=None: True)

    try:
        main.render_nutrition_section()
    except RerunCalled:
        pass
    else:
        raise AssertionError("nutrition save should rerun")

    assert calls == [
        (
            "account-a",
            "profile-a",
            {
                "nutrition": {
                    "calories": 2100.0,
                    "protein": 130.0,
                    "fat": 75.0,
                    "carbs": 260.0,
                }
            },
        )
    ]


def test_note_list_uses_authenticated_account_and_selected_profile(monkeypatch):
    fake_st = FakeStreamlit()
    seed_authenticated_session(fake_st, account_id="account-a")
    monkeypatch.setattr(main, "st", fake_st)
    calls = []

    def fake_list_notes(account_id, profile_id, limit=50):
        calls.append((account_id, profile_id, limit))
        return [{"_id": "note-a", "text": "private"}]

    monkeypatch.setattr(main.db, "list_notes", fake_list_notes)

    assert main._refresh_notes("profile-a") is True

    assert calls == [("account-a", "profile-a", 50)]
    assert fake_st.session_state["notes_profile_id"] == "profile-a"


def test_note_create_uses_authenticated_account_and_selected_profile(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.private_ui_allowed = True
    fake_st.submit_value = True
    seed_authenticated_session(fake_st, account_id="account-a")
    fake_st.session_state["selected_profile"] = {"_id": "profile-a", "goals": []}
    fake_st.session_state["notes_profile_id"] = "profile-a"
    fake_st.input_values = {
        "Workout / fitness note": "synthetic note text",
        "owner_account_id": "account-b",
    }
    monkeypatch.setattr(main, "st", fake_st)
    calls = []
    refreshes = []

    def fake_add_note(account_id, profile_id, text):
        calls.append((account_id, profile_id, text))
        return "note-a"

    monkeypatch.setattr(main.db, "add_note", fake_add_note)
    monkeypatch.setattr(main, "_refresh_notes", lambda profile_id: refreshes.append(profile_id) or True)

    try:
        main.render_notes_section()
    except RerunCalled:
        pass
    else:
        raise AssertionError("adding a note should trigger rerun")

    assert calls == [("account-a", "profile-a", "synthetic note text")]
    assert refreshes == ["profile-a"]


def test_note_delete_uses_authenticated_account_profile_and_note_id(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.private_ui_allowed = True
    seed_authenticated_session(fake_st, account_id="account-a")
    fake_st.session_state.update(
        {
            "selected_profile": {"_id": "profile-a", "goals": []},
            "notes": [{"_id": "note-a", "text": "private"}],
            "notes_profile_id": "profile-a",
            "confirm_delete_note_id": "note-a",
        }
    )
    fake_st.button_values = {"Confirm delete": True}
    monkeypatch.setattr(main, "st", fake_st)
    calls = []
    refreshes = []

    def fake_delete_note(account_id, profile_id, note_id):
        calls.append((account_id, profile_id, note_id))
        return True

    monkeypatch.setattr(main.db, "delete_note", fake_delete_note)
    monkeypatch.setattr(main, "_refresh_notes", lambda profile_id: refreshes.append(profile_id) or True)

    try:
        main.render_notes_section()
    except RerunCalled:
        pass
    else:
        raise AssertionError("deleting a note should trigger rerun")

    assert calls == [("account-a", "profile-a", "note-a")]
    assert refreshes == ["profile-a"]


def test_account_b_notes_use_account_b_and_profile_b(monkeypatch):
    fake_st = FakeStreamlit()
    seed_authenticated_session(fake_st, account_id="account-b", username="UserB")
    monkeypatch.setattr(main, "st", fake_st)
    list_calls = []

    def fake_list_notes(account_id, profile_id, limit=50):
        list_calls.append((account_id, profile_id, limit))
        return []

    monkeypatch.setattr(main.db, "list_notes", fake_list_notes)

    assert main._refresh_notes("profile-b") is True

    assert list_calls == [("account-b", "profile-b", 50)]


def test_selected_profile_change_clears_stale_note_state(monkeypatch):
    fake_st = FakeStreamlit()
    monkeypatch.setattr(main, "st", fake_st)
    fake_st.session_state.update(
        {
            "notes": [{"_id": "note-a", "text": "old"}],
            "notes_profile_id": "profile-a",
            "confirm_delete_note_id": "note-a",
        }
    )

    main._set_selected_profile({"_id": "profile-b", "goals": []})

    assert fake_st.session_state["selected_profile"]["_id"] == "profile-b"
    assert fake_st.session_state["notes"] == []
    assert fake_st.session_state["notes_profile_id"] is None
    assert fake_st.session_state["confirm_delete_note_id"] is None


def test_ask_ai_uses_authenticated_account_profile_and_auth_session(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.private_ui_allowed = True
    fake_st.submit_value = True
    seed_authenticated_session(fake_st, account_id="account-a")
    fake_st.session_state["auth_session_id"] = "session-a"
    fake_st.session_state["selected_profile"] = {"_id": "profile-a", "name": "A", "goals": []}
    fake_st.input_values = {
        "Question": "What should I do next week?",
        "account_id": "forged-account-id",
        "auth_session_id": "forged-session-id",
    }
    monkeypatch.setattr(main, "st", fake_st)
    calls = []

    monkeypatch.setattr(
        main.profiles,
        "build_profile_context",
        lambda profile: "profile context without account identifiers",
    )

    def fake_ask_ai(question, profile_context, account_id, profile_id, session_id=None):
        calls.append((question, profile_context, account_id, profile_id, session_id))
        return "answer"

    monkeypatch.setattr(main.ai, "ask_ai", fake_ask_ai)

    try:
        main.render_ask_ai_section()
    except RerunCalled:
        pass
    else:
        raise AssertionError("Ask AI success should trigger rerun")

    assert calls == [
        (
            "What should I do next week?",
            "profile context without account identifiers",
            "account-a",
            "profile-a",
            "session-a",
        )
    ]
    assert fake_st.session_state["last_ai_answer"] == "answer"


def test_notes_no_profile_guard_prevents_backend_calls(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    seed_authenticated_session(fake_st, account_id="account-a")
    monkeypatch.setattr(main, "st", fake_st)
    monkeypatch.setattr(
        main.db,
        "add_note",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("notes backend must not run without selected profile")
        ),
    )
    monkeypatch.setattr(
        main.db,
        "list_notes",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("notes list must not run without selected profile")
        ),
    )

    main.render_notes_section()


def test_ask_ai_no_profile_guard_prevents_backend_call(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    seed_authenticated_session(fake_st, account_id="account-a")
    monkeypatch.setattr(main, "st", fake_st)
    monkeypatch.setattr(
        main.ai,
        "ask_ai",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Ask AI must not run without selected profile")
        ),
    )

    main.render_ask_ai_section()


def test_two_account_logout_login_prevents_streamlit_state_leakage(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.private_ui_allowed = True
    monkeypatch.setattr(main, "st", fake_st)

    account_a_profile = {
        "_id": "profile-a",
        "name": "Account A Profile",
        "goals": ["private-a-goal"],
        "nutrition": {"calories": 2000, "protein": 120, "fat": 70, "carbs": 250},
    }
    account_b_profile = {
        "_id": "profile-b",
        "name": "Account B Profile",
        "goals": ["private-b-goal"],
        "nutrition": {"calories": 2100, "protein": 130, "fat": 75, "carbs": 260},
    }

    fake_st.session_state.update(
        {
            "authenticated": True,
            "account_id": "account-a",
            "username": "UserA",
            "auth_session_id": "session-a",
            "selected_profile_id": "profile-a",
            "selected_profile": account_a_profile,
            "profiles": [account_a_profile],
            "nutrition": account_a_profile["nutrition"],
            "nutrition_draft": {"calories": 1999},
            "nutrition_draft_profile_id": "profile-a",
            "notes": [{"_id": "note-a", "text": "ACCOUNT_A_PRIVATE_NOTE"}],
            "notes_profile_id": "profile-a",
            "last_ai_answer": "PRIVATE_A_AI_RESPONSE",
            "confirm_delete_note_id": "note-a",
            "create_profile_form_name": "Account A Profile",
            "ask_ai_error": "Account A private error",
        }
    )

    fake_st.button_values = {"Logout": True}
    try:
        main._render_authenticated_header()
    except RerunCalled:
        pass
    else:
        raise AssertionError("logout should trigger rerun")

    assert fake_st.session_state == {
        "authenticated": False,
        "account_id": None,
        "username": None,
        "auth_session_id": None,
    }
    for account_a_key in (
        "selected_profile_id",
        "selected_profile",
        "profiles",
        "nutrition",
        "nutrition_draft",
        "nutrition_draft_profile_id",
        "notes",
        "notes_profile_id",
        "last_ai_answer",
        "confirm_delete_note_id",
        "create_profile_form_name",
        "ask_ai_error",
    ):
        assert account_a_key not in fake_st.session_state

    profile_calls = []
    note_calls = []
    ai_calls = []
    update_calls = []

    def fail_profile_call(*args, **kwargs):
        profile_calls.append((args, kwargs))
        raise AssertionError("profile calls must not run while unauthenticated")

    def fail_note_call(*args, **kwargs):
        note_calls.append((args, kwargs))
        raise AssertionError("note calls must not run while unauthenticated")

    def fail_ai_call(*args, **kwargs):
        ai_calls.append((args, kwargs))
        raise AssertionError("Ask AI must not run while unauthenticated")

    monkeypatch.setattr(main.profiles, "get_all_profiles", fail_profile_call)
    monkeypatch.setattr(main.db, "list_notes", fail_note_call)
    monkeypatch.setattr(main.ai, "ask_ai", fail_ai_call)
    fake_st.private_ui_allowed = False
    fake_st.submit_value = False
    fake_st.button_values = {}
    try:
        main.main()
    except StopCalled:
        pass
    else:
        raise AssertionError("unauthenticated transition should stop before private work")

    assert profile_calls == []
    assert note_calls == []
    assert ai_calls == []

    fake_st.private_ui_allowed = True
    fake_st.submit_value = True
    fake_st.input_values = {"Username": "UserB", "Password": "login-password-b"}

    def fake_authenticate(username, password):
        assert (username, password) == ("UserB", "login-password-b")
        return {"account_id": "account-b", "username": "UserB"}

    monkeypatch.setattr(main.auth, "authenticate", fake_authenticate)

    try:
        main._render_login_form()
    except RerunCalled:
        pass
    else:
        raise AssertionError("Account B login should trigger rerun")

    account_b_session_id = fake_st.session_state["auth_session_id"]
    assert fake_st.session_state["authenticated"] is True
    assert fake_st.session_state["account_id"] == "account-b"
    assert fake_st.session_state["username"] == "UserB"
    assert account_b_session_id
    assert account_b_session_id != "session-a"
    assert "PRIVATE_A_AI_RESPONSE" not in str(fake_st.session_state)

    profile_calls.clear()

    def fake_get_all_profiles(account_id):
        profile_calls.append(("list", account_id))
        return [account_b_profile]

    def fake_get_profile_by_id(account_id, profile_id):
        profile_calls.append(("read", account_id, profile_id))
        return account_b_profile

    monkeypatch.setattr(main.profiles, "get_all_profiles", fake_get_all_profiles)
    monkeypatch.setattr(main.profiles, "get_profile_by_id", fake_get_profile_by_id)
    fake_st.session_state["selected_profile_id"] = "profile-a"

    assert main._refresh_profiles() is True

    assert profile_calls == [
        ("list", "account-b"),
        ("read", "account-b", "profile-b"),
    ]
    assert fake_st.session_state["profiles"] == [account_b_profile]
    assert fake_st.session_state["selected_profile_id"] == "profile-b"
    assert fake_st.session_state["selected_profile"] == account_b_profile
    assert "profile-a" not in str(fake_st.session_state)

    note_calls.clear()

    def fake_list_notes(account_id, profile_id, limit=50):
        note_calls.append(("list", account_id, profile_id, limit))
        return [{"_id": "note-b", "text": "ACCOUNT_B_PRIVATE_NOTE"}]

    monkeypatch.setattr(main.db, "list_notes", fake_list_notes)

    assert main._refresh_notes("profile-b") is True

    assert note_calls == [("list", "account-b", "profile-b", 50)]
    assert fake_st.session_state["notes"] == [{"_id": "note-b", "text": "ACCOUNT_B_PRIVATE_NOTE"}]
    assert fake_st.session_state["notes_profile_id"] == "profile-b"
    assert "note-a" not in str(fake_st.session_state)
    assert "ACCOUNT_A_PRIVATE_NOTE" not in str(fake_st.session_state)

    monkeypatch.setattr(
        main.profiles,
        "build_profile_context",
        lambda profile: "Account B profile context",
    )

    def fake_ask_ai(question, profile_context, account_id, profile_id, session_id=None):
        ai_calls.append((question, profile_context, account_id, profile_id, session_id))
        return "ACCOUNT_B_AI_RESPONSE"

    monkeypatch.setattr(main.ai, "ask_ai", fake_ask_ai)
    fake_st.input_values = {"Question": "What should I do next week?"}

    try:
        main.render_ask_ai_section()
    except RerunCalled:
        pass
    else:
        raise AssertionError("Account B Ask AI should trigger rerun")

    assert ai_calls == [
        (
            "What should I do next week?",
            "Account B profile context",
            "account-b",
            "profile-b",
            account_b_session_id,
        )
    ]
    assert fake_st.session_state["last_ai_answer"] == "ACCOUNT_B_AI_RESPONSE"
    assert "PRIVATE_A_AI_RESPONSE" not in str(fake_st.session_state)

    fake_st.input_values = {
        "Calories (kcal/day)": 2200.0,
        "Protein (g/day)": 140.0,
        "Fat (g/day)": 80.0,
        "Carbs (g/day)": 270.0,
    }

    def fake_save_profile_changes(account_id, profile_id, **updates):
        update_calls.append((account_id, profile_id, updates))
        return {"_id": profile_id, "goals": [], "nutrition": updates["nutrition"]}

    monkeypatch.setattr(main.profiles, "save_profile_changes", fake_save_profile_changes)
    monkeypatch.setattr(main, "_refresh_profiles", lambda select_profile_id=None: True)

    try:
        main.render_nutrition_section()
    except RerunCalled:
        pass
    else:
        raise AssertionError("Account B nutrition save should trigger rerun")

    assert update_calls == [
        (
            "account-b",
            "profile-b",
            {
                "nutrition": {
                    "calories": 2200.0,
                    "protein": 140.0,
                    "fat": 80.0,
                    "carbs": 270.0,
                }
            },
        )
    ]


def test_duplicate_create_account_error_is_safe(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    fake_st.input_values = {
        "Username": "TestUser",
        "Password": "long-password-1",
        "Confirm Password": "long-password-1",
    }
    monkeypatch.setattr(main, "st", fake_st)

    def fake_create_account(username, password):
        raise main.auth.AccountAlreadyExistsError("raw duplicate database detail")

    monkeypatch.setattr(main.auth, "create_account", fake_create_account)

    main._initialize_auth_session_state()
    main._render_create_account_form()

    assert fake_st.error_messages == ["That username is already in use."]
    assert fake_st.session_state["authenticated"] is False
    assert fake_st.session_state["account_id"] is None


def test_create_account_validation_error_uses_auth_message(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    fake_st.input_values = {
        "Username": "no",
        "Password": "long-password-1",
        "Confirm Password": "long-password-1",
    }
    monkeypatch.setattr(main, "st", fake_st)

    def fake_create_account(username, password):
        raise main.auth.InvalidUsernameError("Username must be 3 to 32 characters.")

    monkeypatch.setattr(main.auth, "create_account", fake_create_account)

    main._initialize_auth_session_state()
    main._render_create_account_form()

    assert fake_st.error_messages == ["Username must be 3 to 32 characters."]
    assert fake_st.session_state["authenticated"] is False


def test_create_account_unexpected_error_is_generic(monkeypatch):
    fake_st = FakeStreamlit()
    fake_st.submit_value = True
    fake_st.input_values = {
        "Username": "TestUser",
        "Password": "long-password-1",
        "Confirm Password": "long-password-1",
    }
    monkeypatch.setattr(main, "st", fake_st)

    def fake_create_account(username, password):
        raise RuntimeError("AstraCS:super-secret-token password_hash private detail")

    monkeypatch.setattr(main.auth, "create_account", fake_create_account)

    main._initialize_auth_session_state()
    main._render_create_account_form()

    assert fake_st.error_messages == ["Unable to create account right now."]
    assert "AstraCS" not in fake_st.error_messages[0]
    assert "password_hash" not in fake_st.error_messages[0]
    assert fake_st.session_state["authenticated"] is False
    assert fake_st.session_state["account_id"] is None


def test_ui_diagnostic_sanitizer_redacts_known_secret_values(monkeypatch):
    values = {
        "LANGFLOW_API_KEY": "secret-langflow-key",
        "ASTRA_DB_APPLICATION_TOKEN": "AstraCS:super-secret-token",
    }
    monkeypatch.setattr(main.config, "get_env_value", lambda name: values.get(name, ""))

    sanitized = main._sanitize_diagnostic(
        "failed with secret-langflow-key, AstraCS:super-secret-token, "
        "and http://user:password@example.test"
    )

    assert "secret-langflow-key" not in sanitized
    assert "AstraCS:super-secret-token" not in sanitized
    assert "password" not in sanitized
    assert "<redacted:LANGFLOW_API_KEY>" in sanitized
    assert "<redacted:ASTRA_DB_APPLICATION_TOKEN>" in sanitized


def test_safe_ui_errors_are_user_friendly_without_low_level_details():
    error = RuntimeError("AstraCS:super-secret-token")

    assert "AstraCS" not in main._safe_profile_error("Loading profiles", error)
    assert "AstraCS" not in main._safe_notes_error("Loading notes", error)
    assert "AstraCS" not in main._safe_macro_error("Generating macros", error)
    assert "AstraCS" not in main._safe_ask_ai_error("Ask AI", error)


def test_ai_provider_quota_errors_show_actionable_macro_and_ask_messages():
    error = main.ai.ProviderQuotaError(
        "Langflow HTTP request failed with status 500. Upstream provider HTTP 402.",
        status_code=500,
        diagnostic_summary="detail: OpenRouter 402 requires more credits or fewer max_tokens",
        provider_status=402,
    )

    macro_message = main._safe_macro_error("Generating macros", error)
    ask_message = main._safe_ask_ai_error("Ask AI", error)

    for message in (macro_message, ask_message):
        assert "OpenRouter credit/token budget is insufficient" in message
        assert "Add OpenRouter credit" in message
        assert "max-token setting in Langflow" in message
        assert "ProviderQuotaError" not in message
        assert "LangflowHTTPError" not in message
        assert "402" not in message


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            main.ai.LangflowConfigError("Missing required environment variable: LANGFLOW_API_KEY"),
            "AI configuration is incomplete",
        ),
        (
            main.ai.LangflowConnectionError("connection refused"),
            "Langflow could not be reached",
        ),
        (
            main.ai.LangflowTimeoutError("timeout"),
            "AI request timed out",
        ),
        (
            main.ai.LangflowHTTPError("Langflow HTTP request failed with status 500."),
            "Langflow could not complete the AI workflow",
        ),
        (
            main.ai.LangflowResponseError("unexpected shape"),
            "Langflow returned an unexpected response format",
        ),
        (
            main.NutritionParseError("Nutrition output is not valid JSON."),
            "nutrition output was not valid",
        ),
    ],
)
def test_macro_error_messages_distinguish_ai_failure_categories(error, expected):
    message = main._safe_macro_error("Generating macros", error)

    assert expected in message
    assert type(error).__name__ not in message


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            main.ai.LangflowConfigError("Missing required environment variable: LANGFLOW_API_KEY"),
            "AI configuration is incomplete",
        ),
        (
            main.ai.LangflowConnectionError("connection refused"),
            "Langflow could not be reached",
        ),
        (
            main.ai.LangflowTimeoutError("timeout"),
            "AI request timed out",
        ),
        (
            main.ai.LangflowHTTPError("Langflow HTTP request failed with status 500."),
            "Langflow could not complete the AI workflow",
        ),
        (
            main.ai.LangflowResponseError("unexpected shape"),
            "Langflow returned an unexpected response format",
        ),
    ],
)
def test_ask_ai_error_messages_distinguish_ai_failure_categories(error, expected):
    message = main._safe_ask_ai_error("Ask AI", error)

    assert expected in message
    assert type(error).__name__ not in message


def test_ai_safe_messages_do_not_expose_secret_markers_or_headers():
    error = main.ai.LangflowHTTPError(
        "Langflow HTTP request failed with status 500. "
        "x-api-key: FAKE_LANGFLOW_SECRET_DO_NOT_LEAK "
        "Authorization: FAKE_OPENROUTER_SECRET_DO_NOT_LEAK",
        status_code=500,
        diagnostic_summary=(
            "detail: FAKE_LANGFLOW_SECRET_DO_NOT_LEAK "
            "FAKE_OPENROUTER_SECRET_DO_NOT_LEAK"
        ),
    )

    macro_message = main._safe_macro_error("Generating macros", error)
    ask_message = main._safe_ask_ai_error("Ask AI", error)

    for message in (macro_message, ask_message):
        assert "FAKE_LANGFLOW_SECRET_DO_NOT_LEAK" not in message
        assert "FAKE_OPENROUTER_SECRET_DO_NOT_LEAK" not in message
        assert "x-api-key" not in message.lower()
        assert "authorization" not in message.lower()


def test_profile_validation_errors_show_actionable_field_message():
    error = main.db.InvalidProfileError("activity_level must be a non-empty string")

    message = main._safe_profile_error("Saving profile", error)

    assert message == "Saving profile failed: activity_level must be a non-empty string."
