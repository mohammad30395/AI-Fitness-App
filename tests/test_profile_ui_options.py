import db
import main


def test_canonical_option_constants_match_approved_contract():
    assert main.GENDER_OPTIONS == ("Male", "Female", "Other")
    assert main.ACTIVITY_LEVEL_OPTIONS == (
        "Sedentary",
        "Lightly Active",
        "Moderately Active",
        "Very Active",
        "Super Active",
    )
    assert main.GOAL_OPTIONS == ("Muscle Gain", "Fat Loss", "Stay Active")


def test_single_choice_canonical_value_is_not_duplicated():
    options = main._single_choice_options_with_current(main.GENDER_OPTIONS, "Male")

    assert options == main.GENDER_OPTIONS
    assert options.count("Male") == 1


def test_single_choice_preserves_unknown_gender_exactly():
    options = main._single_choice_options_with_current(main.GENDER_OPTIONS, "unspecified")

    assert options == ("unspecified", "Male", "Female", "Other")
    assert "Other" in options


def test_single_choice_preserves_unknown_activity_values_without_mapping():
    moderate_options = main._single_choice_options_with_current(
        main.ACTIVITY_LEVEL_OPTIONS,
        "moderate",
    )
    active_options = main._single_choice_options_with_current(
        main.ACTIVITY_LEVEL_OPTIONS,
        "active",
    )

    assert moderate_options[0] == "moderate"
    assert "Moderately Active" in moderate_options
    assert moderate_options.count("moderate") == 1
    assert active_options[0] == "active"
    assert "Very Active" in active_options
    assert active_options.count("active") == 1


def test_single_choice_none_and_blank_values_do_not_create_options():
    assert main._single_choice_options_with_current(main.GENDER_OPTIONS, None) == main.GENDER_OPTIONS
    assert main._single_choice_options_with_current(main.GENDER_OPTIONS, "") == main.GENDER_OPTIONS
    assert main._single_choice_options_with_current(main.GENDER_OPTIONS, "   ") == main.GENDER_OPTIONS


def test_goal_options_keep_canonical_selection_available():
    options = main._goal_options_with_existing(main.GOAL_OPTIONS, ["Muscle Gain"])

    assert options == main.GOAL_OPTIONS
    assert options.count("Muscle Gain") == 1


def test_goal_options_preserve_legacy_goals_exactly():
    options = main._goal_options_with_existing(
        main.GOAL_OPTIONS,
        ["Build strength", "Improve endurance"],
    )

    assert options == (
        "Muscle Gain",
        "Fat Loss",
        "Stay Active",
        "Build strength",
        "Improve endurance",
    )


def test_goal_options_are_unique_and_keep_existing_order():
    options = main._goal_options_with_existing(
        main.GOAL_OPTIONS,
        ["Muscle Gain", "Build strength", "Muscle Gain", "Improve endurance"],
    )

    assert options == (
        "Muscle Gain",
        "Fat Loss",
        "Stay Active",
        "Build strength",
        "Improve endurance",
    )
    assert len(options) == len(set(options))


def test_goal_options_none_and_empty_values_return_canonical_only():
    assert main._goal_options_with_existing(main.GOAL_OPTIONS, None) == main.GOAL_OPTIONS
    assert main._goal_options_with_existing(main.GOAL_OPTIONS, []) == main.GOAL_OPTIONS


def test_option_helpers_do_not_mutate_caller_owned_collections():
    canonical = ["Male", "Female", "Other"]
    goals = ["Build strength", "Improve endurance"]
    original_canonical = list(canonical)
    original_goals = list(goals)

    main._single_choice_options_with_current(canonical, "unspecified")
    main._goal_options_with_existing(canonical, goals)

    assert canonical == original_canonical
    assert goals == original_goals


def test_profile_storage_contract_remains_strings_and_goal_list():
    validated = db._validate_profile_fields(
        {
            "name": "Ada Lovelace",
            "age": 31,
            "weight": 64.5,
            "height": 170,
            "gender": "unspecified",
            "activity_level": "moderate",
            "goals": ["Build strength", "Improve endurance"],
        },
        partial=False,
    )

    assert isinstance(validated["gender"], str)
    assert isinstance(validated["activity_level"], str)
    assert isinstance(validated["goals"], list)
    assert all(isinstance(goal, str) for goal in validated["goals"])
