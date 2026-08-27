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
    def caption(self, *args, **kwargs):
        return None

    def metric(self, *args, **kwargs):
        return None

    def subheader(self, *args, **kwargs):
        return None


class FakeStreamlit:
    def __init__(self):
        self.session_state = FakeSessionState()
        self.info_messages = []
        self.error_messages = []
        self.caption_messages = []
        self.page_config = None
        self.input_values = {}
        self.text_input_calls = []
        self.submit_value = False
        self.button_values = {}
        self.tab_labels = []
        self.headers = []
        self.private_ui_allowed = False

    def set_page_config(self, **kwargs):
        self.page_config = kwargs

    def info(self, message):
        self.info_messages.append(message)

    def error(self, message):
        self.error_messages.append(message)

    def header(self, message):
        self.headers.append(message)

    def subheader(self, *args, **kwargs):
        return None

    def tabs(self, labels):
        self.tab_labels.append(tuple(labels))
        return [FakeTab() for _ in labels]

    def columns(self, spec, **kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        return [FakeColumn() for _ in range(count)]

    def container(self, **kwargs):
        return FakeTab()

    def form(self, key):
        return FakeForm(self)

    def text_input(self, label, **kwargs):
        self.text_input_calls.append((label, kwargs))
        return self.input_values.get(label, "")

    def text_area(self, label, **kwargs):
        return self.input_values.get(label, kwargs.get("value", ""))

    def number_input(self, label, **kwargs):
        return self.input_values.get(label, kwargs.get("value"))

    def form_submit_button(self, label, **kwargs):
        return self.submit_value

    def button(self, label, **kwargs):
        return self.button_values.get(label, False)

    def stop(self):
        raise StopCalled

    def rerun(self):
        raise RerunCalled

    def title(self, *args, **kwargs):
        if not self.private_ui_allowed:
            raise AssertionError("private UI must not render before authentication")

    def caption(self, *args, **kwargs):
        self.caption_messages.append(args[0] if args else "")
        if not self.private_ui_allowed:
            raise AssertionError("private UI must not render before authentication")

    def success(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def write(self, *args, **kwargs):
        return None

    def markdown(self, *args, **kwargs):
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
        "Gender": "unspecified",
        "Activity level": "moderate",
        "Goals": "Build strength",
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
            "gender": "unspecified",
            "activity_level": "moderate",
            "goals": ["Build strength"],
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
        "Gender": "unspecified",
        "Activity level": "active",
        "Goals": "Improve endurance",
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
        main._render_profile_form(mode="edit", profile={"_id": "profile-a", "goals": []})
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
