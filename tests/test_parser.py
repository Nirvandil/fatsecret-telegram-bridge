import json

from fsai.parser import Parser
from tests.conftest import FakeProvider


def test_parses_items_with_grams():
    payload = json.dumps({"items": [
        {"name": "гречка", "query_en": "buckwheat", "grams": 200,
         "meal_hint": None, "confidence": 0.95},
        {"name": "куриное филе", "query_en": "chicken breast", "grams": 150,
         "meal_hint": "lunch", "confidence": 0.9},
    ]})
    parser = Parser(FakeProvider(payload))
    items = parser.parse("греча 200г, куриное филе 150г", ["гречка"])
    assert len(items) == 2
    assert items[0].name == "гречка" and items[0].grams == 200.0
    assert items[0].query_en == "buckwheat"
    assert items[1].meal_hint == "lunch"


def test_known_aliases_passed_into_prompt():
    provider = FakeProvider(json.dumps({"items": []}))
    Parser(provider).parse("что-то", ["рис", "гречка"])
    assert "рис" in provider.last_user and "гречка" in provider.last_user


def test_handles_code_fenced_json():
    payload = "```json\n" + json.dumps({"items": [{"name": "рис", "grams": 100}]}) + "\n```"
    items = Parser(FakeProvider(payload)).parse("рис 100", [])
    assert items[0].name == "рис" and items[0].grams == 100.0


def test_missing_grams_becomes_none():
    payload = json.dumps({"items": [{"name": "банан"}]})
    items = Parser(FakeProvider(payload)).parse("банан", [])
    assert items[0].grams is None
    assert items[0].confidence == 1.0
    assert items[0].query_en is None      # query_en необязателен


def test_empty_or_garbage_returns_empty_list():
    assert Parser(FakeProvider("не json вовсе")).parse("шум", []) == []
