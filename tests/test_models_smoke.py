from fatsecret_telegram_bridge.models import (
    ParsedItem, FoodCandidate, Serving, AliasRecord, ResolvedItem,
)


def test_parsed_item_defaults():
    item = ParsedItem(name="гречка")
    assert item.quantity is None and item.unit is None
    assert item.query_en is None
    assert item.confidence == 1.0


def test_resolved_item_fields():
    r = ResolvedItem(
        alias="гречка", food_id="11", food_name="Buckwheat, cooked",
        serving_id="22", number_of_units=200.0, unit="g", meal="lunch",
    )
    assert r.number_of_units == 200.0 and r.unit == "g" and r.meal == "lunch"


def test_serving_fields():
    s = Serving(serving_id="1", description="1 cup", measurement="cup")
    assert s.measurement == "cup"


def test_alias_record_fields():
    a = AliasRecord("гречка", "11", "Buckwheat")
    assert a.food_id == "11" and a.food_name == "Buckwheat"


def test_food_candidate_default_description():
    assert FoodCandidate("1", "Rice").description == ""
