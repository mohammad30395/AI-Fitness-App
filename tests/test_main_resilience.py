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


class FakeStreamlit:
    def __init__(self):
        self.session_state = FakeSessionState()
        self.info_messages = []
        self.error_messages = []
        self.page_config = None
        self.input_values = {}
        self.submit_value = False
        self.headers = []

    def set_page_config(self, **kwargs):
        self.page_config = kwargs

    def info(self, message):
        self.info_messages.append(message)

    def error(self, message):
        self.error_messages.append(message)

    def header(self, message):
        self.headers.append(message)

    def form(self, key):
        return FakeForm(self)

    def text_input(self, label, **kwargs):
        return self.input_values.get(label, "")

    def form_submit_button(self, label, **kwargs):
        return self.submit_value

    def stop(self):
        raise StopCalled

    def rerun(self):
        raise RerunCalled

    def title(self, *args, **kwargs):
        raise AssertionError("private UI must not render before authentication")

    def caption(self, *args, **kwargs):
        raise AssertionError("private UI must not render before authentication")

    def divider(self, *args, **kwargs):
        raise AssertionError("private UI must not render before authentication")


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
    assert fake_st.session_state == {
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


def test_profile_validation_errors_show_actionable_field_message():
    error = main.db.InvalidProfileError("activity_level must be a non-empty string")

    message = main._safe_profile_error("Saving profile", error)

    assert message == "Saving profile failed: activity_level must be a non-empty string."
