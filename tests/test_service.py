import json
from datetime import datetime

from fsai.models import AliasRecord, FoodCandidate, Serving
from fsai.service import LoggerService, AutoLogged, NeedsInput
from fsai.store import Store
from tests.conftest import FakeProvider


class FakeClient:
    def __init__(self):
        self.search_return = []
        self.servings_return = []
        self.created = []
        self.deleted = []

    def search_foods(self, query, max_results=5):
        return self.search_return

    def get_servings(self, food_id):
        return self.servings_return

    def create_entry(self, food_id, food_name, serving_id, number_of_units,
                     meal, date=None):
        self.created.append((food_id, serving_id, number_of_units, meal))
        return f"e{len(self.created)}"

    def delete_entry(self, entry_id):
        self.deleted.append(entry_id)


def build(tmp_path, provider, client, now_hour=13):
    store = Store(str(tmp_path / "svc.sqlite3"))
    return LoggerService(
        provider=provider, client=client, store=store,
        clock=lambda: datetime(2026, 6, 17, now_hour, 0),
    ), store


def test_all_known_items_autolog(tmp_path):
    payload = json.dumps({"items": [
        {"name": "гречка", "grams": 200, "confidence": 0.95},
        {"name": "филе", "grams": 150, "confidence": 0.95},
    ]})
    client = FakeClient()
    svc, store = build(tmp_path, FakeProvider(payload), client)
    store.save_alias(AliasRecord("гречка", "11", "22", 100.0, "Buckwheat"))
    store.save_alias(AliasRecord("филе", "33", "44", 100.0, "Chicken"))

    res = svc.process_text("греча 200г, филе 150г")

    assert isinstance(res, AutoLogged)
    assert len(client.created) == 2
    assert client.created[0] == ("11", "22", 2.0, "lunch")
    assert store.get_log(res.log_id)["entry_ids"] == ["e1", "e2"]


def test_unknown_item_needs_input_then_finalize(tmp_path):
    payload = json.dumps({"items": [{"name": "греча", "grams": 200, "confidence": 0.9}]})
    client = FakeClient()
    client.search_return = [FoodCandidate("1", "Buckwheat", "Per 100g")]
    client.servings_return = [Serving("100", "100 g", 100.0, "g")]
    svc, store = build(tmp_path, FakeProvider(payload), client)

    res = svc.process_text("греча 200г")
    assert isinstance(res, NeedsInput)
    prompt = res.pending[0]
    assert prompt.kind == "food"
    assert prompt.candidates[0].food_id == "1"

    svc.choose_food(res.session_id, prompt.index, "1", "Buckwheat")
    final = svc.finalize(res.session_id)
    assert isinstance(final, AutoLogged)
    assert client.created == [("1", "100", 2.0, "lunch")]
    assert store.get_alias("греча").food_id == "1"


def test_missing_grams_needs_input(tmp_path):
    payload = json.dumps({"items": [{"name": "гречка"}]})
    client = FakeClient()
    svc, store = build(tmp_path, FakeProvider(payload), client)
    store.save_alias(AliasRecord("гречка", "11", "22", 100.0, "Buckwheat"))

    res = svc.process_text("гречка")
    assert isinstance(res, NeedsInput)
    assert res.pending[0].kind == "grams"

    svc.set_grams(res.session_id, res.pending[0].index, 250.0)
    final = svc.finalize(res.session_id)
    assert isinstance(final, AutoLogged)
    assert client.created[0] == ("11", "22", 2.5, "lunch")


def test_empty_parse_returns_autologged_with_no_entries(tmp_path):
    client = FakeClient()
    svc, _ = build(tmp_path, FakeProvider(json.dumps({"items": []})), client)
    res = svc.process_text("бессмыслица")
    assert isinstance(res, AutoLogged) and res.log_id is None
    assert client.created == []


def test_undo_deletes_entries(tmp_path):
    payload = json.dumps({"items": [{"name": "гречка", "grams": 200}]})
    client = FakeClient()
    svc, store = build(tmp_path, FakeProvider(payload), client)
    store.save_alias(AliasRecord("гречка", "11", "22", 100.0, "Buckwheat"))
    res = svc.process_text("гречка 200")
    count = svc.undo(res.log_id)
    assert count == 1
    assert client.deleted == ["e1"]
