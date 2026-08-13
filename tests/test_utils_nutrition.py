import pytest

from utils import NutritionParseError, parse_nutrition_json


def test_parse_nutrition_json_accepts_valid_plain_json():
    result = parse_nutrition_json('{"calories": 2200, "protein": 150, "fat": 70, "carbs": 250}')

    assert result == {
        "calories": 2200,
        "protein": 150,
        "fat": 70,
        "carbs": 250,
    }


def test_parse_nutrition_json_accepts_fenced_json_object():
    result = parse_nutrition_json(
        """```json
{"calories": 2200, "protein": 150.5, "fat": 70, "carbs": 250}
```"""
    )

    assert result["protein"] == 150.5


def test_parse_nutrition_json_rejects_missing_fields():
    with pytest.raises(NutritionParseError, match="missing fields"):
        parse_nutrition_json('{"calories": 2200, "protein": 150, "fat": 70}')


def test_parse_nutrition_json_rejects_non_numeric_values():
    with pytest.raises(NutritionParseError, match="must be a number"):
        parse_nutrition_json('{"calories": "2200", "protein": 150, "fat": 70, "carbs": 250}')


def test_parse_nutrition_json_rejects_negative_values():
    with pytest.raises(NutritionParseError, match="positive"):
        parse_nutrition_json('{"calories": 2200, "protein": -150, "fat": 70, "carbs": 250}')


def test_parse_nutrition_json_rejects_extra_prose():
    with pytest.raises(NutritionParseError, match="valid JSON"):
        parse_nutrition_json('Here are macros: {"calories": 2200, "protein": 150, "fat": 70, "carbs": 250}')


def test_parse_nutrition_json_rejects_malformed_json():
    with pytest.raises(NutritionParseError, match="valid JSON"):
        parse_nutrition_json('{"calories": 2200, "protein": 150, "fat": 70, "carbs": }')


def test_parse_nutrition_json_rejects_extra_fields():
    with pytest.raises(NutritionParseError, match="unexpected fields"):
        parse_nutrition_json(
            '{"calories": 2200, "protein": 150, "fat": 70, "carbs": 250, "fiber": 30}'
        )
