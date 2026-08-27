import pytest

import profiles
from utils import dict_to_string


ACCOUNT_ID = "account-a"


def raw_profile(**overrides):
    profile = {
        "_id": "profile-1",
        "name": "Ada Lovelace",
        "age": 31,
        "weight": 64.5,
        "height": 170,
        "gender": "female",
        "activity_level": "moderate",
        "goals": ["strength", "mobility"],
        "nutrition": {
            "carbs": 220,
            "fat": 70,
            "protein": 140,
            "calories": 2100,
            "extra": "ignored",
        },
        "unexpected": "ignored",
    }
    profile.update(overrides)
    return profile


def test_normalize_profile_returns_predictable_shape_and_field_order():
    normalized = profiles.normalize_profile(raw_profile())

    assert list(normalized) == [
        "_id",
        "name",
        "age",
        "weight",
        "height",
        "gender",
        "activity_level",
        "goals",
        "nutrition",
    ]
    assert normalized["goals"] == ["strength", "mobility"]
    assert normalized["nutrition"] == {
        "calories": 2100,
        "protein": 140,
        "fat": 70,
        "carbs": 220,
    }
    assert "unexpected" not in normalized


def test_normalize_profile_keeps_nutrition_optional():
    normalized = profiles.normalize_profile(raw_profile(nutrition=None))

    assert "nutrition" not in normalized
    assert normalized["goals"] == ["strength", "mobility"]


@pytest.mark.parametrize("profile", [None, [], "not a profile"])
def test_normalize_profile_rejects_non_dictionary_values(profile):
    with pytest.raises(profiles.ProfileDataError):
        profiles.normalize_profile(profile)


def test_build_profile_context_is_deterministic_and_human_readable():
    context = profiles.build_profile_context(raw_profile())

    assert context == "\n".join(
        [
            "Profile id: profile-1",
            "Name: Ada Lovelace",
            "Age: 31",
            "Weight: 64.5",
            "Height: 170",
            "Gender: female",
            "Activity level: moderate",
            "Goals: strength, mobility",
            "Nutrition:",
            "  Calories: 2100",
            "  Protein: 140",
            "  Fat: 70",
            "  Carbs: 220",
        ]
    )


def test_build_profile_context_marks_missing_nutrition_as_not_generated():
    context = profiles.build_profile_context(raw_profile(nutrition={}))

    assert "Nutrition: not generated yet" in context


def test_get_all_profiles_normalizes_db_results(monkeypatch):
    calls = []

    def fake_list_profiles(account_id):
        calls.append(account_id)
        return [
            raw_profile(_id="profile-1"),
            raw_profile(_id="profile-2", nutrition=None),
        ]

    monkeypatch.setattr(
        profiles.db,
        "list_profiles",
        fake_list_profiles,
    )

    result = profiles.get_all_profiles(ACCOUNT_ID)

    assert calls == [ACCOUNT_ID]
    assert [profile["_id"] for profile in result] == ["profile-1", "profile-2"]
    assert "nutrition" not in result[1]


def test_get_profile_by_id_normalizes_db_result(monkeypatch):
    calls = []

    def fake_get_profile(account_id, profile_id):
        calls.append((account_id, profile_id))
        return raw_profile(_id=profile_id)

    monkeypatch.setattr(profiles.db, "get_profile", fake_get_profile)

    assert profiles.get_profile_by_id(ACCOUNT_ID, "profile-1")["_id"] == "profile-1"
    assert calls == [(ACCOUNT_ID, "profile-1")]


def test_create_new_profile_preserves_goals_list_and_optional_nutrition(monkeypatch):
    calls = []
    monkeypatch.setattr(
        profiles.db,
        "create_profile",
        lambda profile_data: calls.append(profile_data) or "profile-1",
    )

    inserted_id = profiles.create_new_profile(
        name="Ada Lovelace",
        age=31,
        weight=64.5,
        height=170,
        gender="female",
        activity_level="moderate",
        goals=["strength", "mobility"],
    )

    assert inserted_id == "profile-1"
    assert calls == [
        {
            "name": "Ada Lovelace",
            "age": 31,
            "weight": 64.5,
            "height": 170,
            "gender": "female",
            "activity_level": "moderate",
            "goals": ["strength", "mobility"],
        }
    ]


def test_save_profile_changes_normalizes_updated_profile(monkeypatch):
    calls = []

    def fake_update(profile_id, updates):
        calls.append((profile_id, updates))
        return raw_profile(_id=profile_id, goals=updates["goals"], nutrition=None)

    monkeypatch.setattr(profiles.db, "update_personal_information", fake_update)

    result = profiles.save_profile_changes("profile-1", goals=["endurance"], nutrition=None)

    assert calls == [("profile-1", {"goals": ["endurance"]})]
    assert result["goals"] == ["endurance"]
    assert "nutrition" not in result


def test_dict_to_string_is_project_deterministic_serializer():
    result = dict_to_string(
        {"b": 2, "a": ["x", "y"], "nested": {"d": 4, "c": 3}},
        key_order=("a",),
    )

    assert result == "\n".join(
        [
            "A: x, y",
            "B: 2",
            "Nested:",
            "  C: 3",
            "  D: 4",
        ]
    )
