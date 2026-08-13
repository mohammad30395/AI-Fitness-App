from utils import dict_to_string


def test_dict_to_string_serializes_profile_like_data_deterministically():
    result = dict_to_string(
        {
            "goals": ["build strength", "improve endurance"],
            "nutrition": {"carbs": 250, "calories": 2400, "fat": 70, "protein": 160},
            "name": "Example User",
            "activity_level": "moderate",
        },
        key_order=("name", "activity_level", "goals", "nutrition"),
        nested_key_orders={"nutrition": ("calories", "protein", "fat", "carbs")},
    )

    assert result == "\n".join(
        [
            "Name: Example User",
            "Activity level: moderate",
            "Goals: build strength, improve endurance",
            "Nutrition:",
            "  Calories: 2400",
            "  Protein: 160",
            "  Fat: 70",
            "  Carbs: 250",
        ]
    )


def test_dict_to_string_marks_missing_and_empty_values_readably():
    result = dict_to_string(
        {"name": "", "goals": [], "nutrition": None},
        key_order=("name", "goals", "nutrition"),
    )

    assert result == "\n".join(
        [
            "Name: not set",
            "Goals: none",
            "Nutrition: not set",
        ]
    )
