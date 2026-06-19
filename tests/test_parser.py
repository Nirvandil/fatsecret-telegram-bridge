import json

from fatsecret_telegram_bridge.parser import Parser, RegexParser
from tests.conftest import FakeProvider


def test_parses_items_with_quantity_and_unit():
    payload = json.dumps({"items": [
        {"name": "гречка", "query_en": "buckwheat", "quantity": 200, "unit": "g",
         "meal_hint": None, "confidence": 0.95},
        {"name": "chicken", "query_en": "chicken breast", "quantity": 6,
         "unit": "oz", "meal_hint": "lunch", "confidence": 0.9},
    ]})
    items = Parser(FakeProvider(payload)).parse("...", ["гречка"])
    assert len(items) == 2
    assert items[0].name == "гречка" and items[0].quantity == 200.0
    assert items[0].unit == "g" and items[0].query_en == "buckwheat"
    assert items[1].quantity == 6.0 and items[1].unit == "oz"
    assert items[1].meal_hint == "lunch"


def test_known_aliases_passed_into_prompt():
    provider = FakeProvider(json.dumps({"items": []}))
    Parser(provider).parse("anything", ["рис", "гречка"])
    assert "рис" in provider.last_user and "гречка" in provider.last_user


def test_handles_code_fenced_json():
    payload = "```json\n" + json.dumps(
        {"items": [{"name": "rice", "quantity": 100, "unit": "g"}]}) + "\n```"
    items = Parser(FakeProvider(payload)).parse("rice 100g", [])
    assert items[0].name == "rice" and items[0].quantity == 100.0


def test_missing_quantity_and_unit_become_none():
    payload = json.dumps({"items": [{"name": "banana"}]})
    items = Parser(FakeProvider(payload)).parse("banana", [])
    assert items[0].quantity is None and items[0].unit is None
    assert items[0].query_en is None
    assert items[0].confidence == 1.0


def test_empty_or_garbage_returns_empty_list():
    assert Parser(FakeProvider("not json at all")).parse("noise", []) == []


# ---------- RegexParser (no-LLM mode) ----------

def test_regex_parser_extracts_name_quantity_unit():
    items = RegexParser().parse("oatmeal 50g, chicken breast 150 g, rice 1 cup", [])
    assert [(i.name, i.quantity, i.unit) for i in items] == [
        ("oatmeal", 50.0, "g"),
        ("chicken breast", 150.0, "g"),
        ("rice", 1.0, "cup"),
    ]
    assert items[0].query_en is None      # no translation without LLM


def test_regex_parser_item_without_quantity():
    items = RegexParser().parse("banana", [])
    assert items[0].name == "banana"
    assert items[0].quantity is None and items[0].unit is None


def test_regex_parser_handles_decimal_comma_and_newlines():
    items = RegexParser().parse("milk 1,5 cup\negg 2 piece", [])
    assert (items[0].name, items[0].quantity, items[0].unit) == ("milk", 1.5, "cup")
    assert (items[1].name, items[1].quantity, items[1].unit) == ("egg", 2.0, "piece")
