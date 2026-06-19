import json
from datetime import datetime

from fatsecret_telegram_bridge.models import AliasRecord, FoodCandidate, Serving
from fatsecret_telegram_bridge.service import LoggerService, AutoLogged, NeedsInput
from fatsecret_telegram_bridge.store import Store
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
        {"name": "rice", "quantity": 200, "unit": "g"},
        {"name": "chicken", "quantity": 6, "unit": "oz"},
    ]})
    client = FakeClient()
    client.servings_return = [Serving("22", "100 g", "g"), Serving("23", "1 oz", "oz")]
    svc, store = build(tmp_path, FakeProvider(payload), client)
    store.save_alias(AliasRecord("rice", "11", "Rice"))
    store.save_alias(AliasRecord("chicken", "33", "Chicken"))

    res = svc.process_text("rice 200g, chicken 6oz")

    assert isinstance(res, AutoLogged)
    assert client.created == [("11", "22", 200.0, "lunch"),
                              ("33", "23", 6.0, "lunch")]
    assert store.get_log(res.log_id)["entry_ids"] == ["e1", "e2"]


def test_unknown_item_pick_food_then_autolog(tmp_path):
    payload = json.dumps({"items": [
        {"name": "греча", "query_en": "buckwheat", "quantity": 200, "unit": "g"}]})
    client = FakeClient()
    client.search_return = [FoodCandidate("1", "Buckwheat", "Per 100g")]
    client.servings_return = [Serving("100", "100 g", "g")]
    svc, store = build(tmp_path, FakeProvider(payload), client)

    res = svc.process_text("греча 200g")
    assert isinstance(res, NeedsInput)
    assert res.pending[0].kind == "food"
    assert res.pending[0].candidates[0].food_id == "1"

    svc.choose_food(res.session_id, res.pending[0].index, "1")
    final = svc.finalize(res.session_id)
    assert isinstance(final, AutoLogged)
    assert client.created == [("1", "100", 200.0, "lunch")]
    assert store.get_alias("греча").food_id == "1"


def test_no_unit_asks_serving_then_autolog(tmp_path):
    payload = json.dumps({"items": [{"name": "rice", "quantity": 200}]})
    client = FakeClient()
    client.servings_return = [Serving("22", "100 g", "g"), Serving("23", "1 cup", "cup")]
    svc, store = build(tmp_path, FakeProvider(payload), client)
    store.save_alias(AliasRecord("rice", "11", "Rice"))

    res = svc.process_text("rice 200")
    assert isinstance(res, NeedsInput)
    assert res.pending[0].kind == "serving"

    svc.choose_serving(res.session_id, res.pending[0].index, "22")
    final = svc.finalize(res.session_id)
    assert isinstance(final, AutoLogged)
    assert client.created == [("11", "22", 200.0, "lunch")]


def test_unit_without_quantity_asks_quantity_then_autolog(tmp_path):
    payload = json.dumps({"items": [{"name": "rice", "unit": "cup"}]})
    client = FakeClient()
    client.servings_return = [Serving("23", "1 cup", "cup")]
    svc, store = build(tmp_path, FakeProvider(payload), client)
    store.save_alias(AliasRecord("rice", "11", "Rice"))

    res = svc.process_text("rice, a cup")
    assert isinstance(res, NeedsInput)
    assert res.pending[0].kind == "quantity"

    svc.set_quantity(res.session_id, res.pending[0].index, 2.0)
    final = svc.finalize(res.session_id)
    assert isinstance(final, AutoLogged)
    assert client.created == [("11", "23", 2.0, "lunch")]


def test_empty_parse_returns_autologged_with_no_entries(tmp_path):
    client = FakeClient()
    svc, _ = build(tmp_path, FakeProvider(json.dumps({"items": []})), client)
    res = svc.process_text("nonsense")
    assert isinstance(res, AutoLogged) and res.log_id is None
    assert client.created == []


def test_undo_deletes_entries(tmp_path):
    payload = json.dumps({"items": [{"name": "rice", "quantity": 200, "unit": "g"}]})
    client = FakeClient()
    client.servings_return = [Serving("22", "100 g", "g")]
    svc, store = build(tmp_path, FakeProvider(payload), client)
    store.save_alias(AliasRecord("rice", "11", "Rice"))
    res = svc.process_text("rice 200g")
    assert svc.undo(res.log_id) == 1
    assert client.deleted == ["e1"]
