from fsai.models import AliasRecord, FoodCandidate, ParsedItem, Serving
from fsai.resolver import (
    Resolver, Resolved, NeedsGrams, NeedsFood, NeedsServing,
)
from fsai.store import Store


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


def test_missing_grams_returns_needs_grams(tmp_path):
    r = Resolver(FakeClient(), store(tmp_path))
    res = r.resolve(ParsedItem(name="банан", grams=None), meal="lunch")
    assert isinstance(res, NeedsGrams)


def test_known_alias_resolves_directly(tmp_path):
    s = store(tmp_path)
    s.save_alias(AliasRecord("гречка", "11", "22", 100.0, "Buckwheat"))
    r = Resolver(FakeClient(), s)
    res = r.resolve(ParsedItem(name="гречка", grams=200.0), meal="lunch")
    assert isinstance(res, Resolved)
    assert res.item.food_id == "11" and res.item.grams == 200.0
    assert res.item.grams_per_serving == 100.0 and res.item.meal == "lunch"


def test_unknown_triggers_search_by_english_query(tmp_path):
    c = FakeClient()
    c.search_return = [FoodCandidate("1", "Buckwheat", "")]
    r = Resolver(c, store(tmp_path))
    res = r.resolve(ParsedItem(name="греча", query_en="buckwheat", grams=200.0),
                    meal="lunch")
    assert isinstance(res, NeedsFood)
    assert res.candidates[0].food_id == "1"
    assert res.parsed.name == "греча"
    assert c.last_query == "buckwheat"     # ищем по англоязычному запросу


def test_unknown_search_falls_back_to_name(tmp_path):
    c = FakeClient()
    c.search_return = []
    r = Resolver(c, store(tmp_path))
    r.resolve(ParsedItem(name="греча", grams=200.0), meal="lunch")
    assert c.last_query == "греча"         # query_en нет → ищем по name


def test_confirm_food_prefers_gram_serving_and_saves_alias(tmp_path):
    s = store(tmp_path)
    c = FakeClient()
    # Граммовая порция стоит ВТОРОЙ, но должна быть выбрана (is_gram=True).
    c.servings_return = [
        Serving("99", "1 cup", 152.0, "g", is_gram=False),
        Serving("100", "100 g", 1.0, "g", is_gram=True),
    ]
    r = Resolver(c, s)
    parsed = ParsedItem(name="греча", grams=200.0)
    res = r.confirm_food(parsed, "1", "Buckwheat", meal="dinner")
    assert isinstance(res, Resolved)
    assert res.item.serving_id == "100" and res.item.grams_per_serving == 1.0
    assert res.item.meal == "dinner"
    saved = s.get_alias("греча")
    assert saved.food_id == "1" and saved.serving_id == "100"


def test_confirm_food_falls_back_to_first_gram_serving(tmp_path):
    # Нет «g»-порции → берём первую порцию в граммах.
    c = FakeClient()
    c.servings_return = [Serving("99", "1 cup", 152.0, "g", is_gram=False)]
    r = Resolver(c, store(tmp_path))
    res = r.confirm_food(ParsedItem(name="x", grams=200.0), "1", "X", meal="lunch")
    assert isinstance(res, Resolved)
    assert res.item.serving_id == "99" and res.item.grams_per_serving == 152.0


def test_confirm_food_without_gram_serving_asks_serving(tmp_path):
    c = FakeClient()
    c.servings_return = [Serving("99", "1 cup", None, "cup")]
    r = Resolver(c, store(tmp_path))
    res = r.confirm_food(ParsedItem(name="x", grams=50.0), "1", "X", meal="lunch")
    assert isinstance(res, NeedsServing)
    assert res.servings[0].serving_id == "99"
