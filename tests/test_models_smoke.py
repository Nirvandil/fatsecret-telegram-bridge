from fatsecret_telegram_bridge.models import (
    ParsedItem, FoodCandidate, Serving, AliasRecord, ResolvedItem,
)


def test_parsed_item_defaults():
    item = ParsedItem(name="гречка")
    assert item.grams is None
    assert item.meal_hint is None
    assert item.confidence == 1.0


def test_resolved_item_fields():
    r = ResolvedItem(
        alias="гречка", food_id="11", serving_id="22",
        food_name="Buckwheat, cooked", grams=200.0,
        grams_per_serving=100.0, meal="lunch",
    )
    assert r.grams == 200.0 and r.meal == "lunch"


def test_serving_optional_grams():
    s = Serving(serving_id="1", description="1 cup", grams=None, metric_unit=None)
    assert s.grams is None
