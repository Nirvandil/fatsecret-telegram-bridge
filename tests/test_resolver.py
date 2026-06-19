from fatsecret_telegram_bridge.models import (
    AliasRecord, FoodCandidate, ParsedItem, Serving,
)
from fatsecret_telegram_bridge.resolver import (
    Resolver, Resolved, NeedsFood, NeedsServing, NeedsQuantity,
)
from fatsecret_telegram_bridge.store import Store


class FakeClient:
    def __init__(self):
        self.search_return = []
        self.servings_return = []

    def search_foods(self, query, max_results=5):
        self.last_query = query
        return self.search_return

    def get_servings(self, food_id):
        self.last_food_id = food_id
        return self.servings_return


def store(tmp_path):
    return Store(str(tmp_path / "r.sqlite3"))


def test_unknown_triggers_search_by_english_query(tmp_path):
    c = FakeClient()
    c.search_return = [FoodCandidate("1", "Buckwheat", "")]
    res = Resolver(c, store(tmp_path)).resolve(
        ParsedItem(name="греча", query_en="buckwheat", quantity=200.0, unit="g"),
        meal="lunch")
    assert isinstance(res, NeedsFood)
    assert res.candidates[0].food_id == "1"
    assert c.last_query == "buckwheat"     # search by the English query


def test_unknown_search_falls_back_to_name(tmp_path):
    c = FakeClient()
    Resolver(c, store(tmp_path)).resolve(
        ParsedItem(name="греча", quantity=200.0, unit="g"), meal="lunch")
    assert c.last_query == "греча"         # no query_en -> search by name


def test_known_alias_unit_match_with_quantity_resolves(tmp_path):
    s = store(tmp_path)
    s.save_alias(AliasRecord("rice", "11", "Rice"))
    c = FakeClient()
    c.servings_return = [Serving("100", "100 g", "g"), Serving("200", "1 cup", "cup")]
    res = Resolver(c, s).resolve(
        ParsedItem(name="rice", quantity=200.0, unit="g"), meal="lunch")
    assert isinstance(res, Resolved)
    assert res.item.serving_id == "100"
    assert res.item.number_of_units == 200.0 and res.item.unit == "g"


def test_known_alias_unit_match_without_quantity_needs_quantity(tmp_path):
    s = store(tmp_path)
    s.save_alias(AliasRecord("rice", "11", "Rice"))
    c = FakeClient()
    c.servings_return = [Serving("200", "1 cup", "cup")]
    res = Resolver(c, s).resolve(ParsedItem(name="rice", unit="cup"), meal="lunch")
    assert isinstance(res, NeedsQuantity)
    assert res.serving_id == "200" and res.unit == "cup"


def test_known_alias_no_unit_needs_serving(tmp_path):
    s = store(tmp_path)
    s.save_alias(AliasRecord("rice", "11", "Rice"))
    c = FakeClient()
    c.servings_return = [Serving("100", "100 g", "g")]
    res = Resolver(c, s).resolve(ParsedItem(name="rice", quantity=200.0), meal="lunch")
    assert isinstance(res, NeedsServing)
    assert res.servings[0].serving_id == "100"


def test_known_alias_unit_no_match_needs_serving(tmp_path):
    s = store(tmp_path)
    s.save_alias(AliasRecord("rice", "11", "Rice"))
    c = FakeClient()
    c.servings_return = [Serving("100", "100 g", "g")]
    res = Resolver(c, s).resolve(
        ParsedItem(name="rice", quantity=2.0, unit="cup"), meal="lunch")
    assert isinstance(res, NeedsServing)


def test_confirm_food_saves_alias_and_resolves(tmp_path):
    s = store(tmp_path)
    c = FakeClient()
    c.servings_return = [Serving("100", "100 g", "g")]
    res = Resolver(c, s).confirm_food(
        ParsedItem(name="греча", quantity=200.0, unit="g"), "1", "Buckwheat",
        meal="dinner")
    assert isinstance(res, Resolved)
    assert res.item.serving_id == "100" and res.item.number_of_units == 200.0
    assert s.get_alias("греча").food_id == "1"


def test_choose_serving_with_quantity_resolves(tmp_path):
    res = Resolver(FakeClient(), store(tmp_path)).choose_serving(
        ParsedItem(name="rice", quantity=2.0), "1", "Rice",
        Serving("200", "1 cup", "cup"), meal="lunch")
    assert isinstance(res, Resolved)
    assert res.item.serving_id == "200"
    assert res.item.number_of_units == 2.0 and res.item.unit == "cup"


def test_choose_serving_without_quantity_needs_quantity(tmp_path):
    res = Resolver(FakeClient(), store(tmp_path)).choose_serving(
        ParsedItem(name="rice"), "1", "Rice",
        Serving("200", "1 cup", "cup"), meal="lunch")
    assert isinstance(res, NeedsQuantity)
    assert res.serving_id == "200" and res.unit == "cup"


def test_set_quantity_resolves(tmp_path):
    res = Resolver(FakeClient(), store(tmp_path)).set_quantity(
        ParsedItem(name="rice"), "1", "Rice", "200", "cup", 3.0, meal="lunch")
    assert isinstance(res, Resolved)
    assert res.item.number_of_units == 3.0 and res.item.unit == "cup"
