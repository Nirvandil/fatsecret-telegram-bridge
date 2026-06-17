from decimal import Decimal
from types import SimpleNamespace as NS

from fsai.fatsecret_client import FatSecretClient
from fsai.models import FoodCandidate, Serving


class FakeFoods:
    def __init__(self):
        self.search_return = []
        self.food_return = None
        self.last_search = None
        self.last_get = None

    def search_v1(self, search_expression=None, max_results=None, page_number=None):
        self.last_search = (search_expression, max_results)
        return self.search_return

    def get_v2(self, food_id):
        self.last_get = food_id
        return self.food_return


class FakeDiary:
    def __init__(self):
        self.deleted = []

    def entry_delete_v1(self, food_entry_id=None):
        self.deleted.append(food_entry_id)


class FakeFs:
    def __init__(self):
        self.foods = FakeFoods()
        self.diary = FakeDiary()
        self.call_return = {"food_entry_id": {"value": "9001"}}
        self.calls = []

    def _call(self, params, method="GET", url=None, json_body=None):
        self.calls.append((dict(params), method))
        return self.call_return


def make_client(fake):
    c = FatSecretClient.__new__(FatSecretClient)
    c._fs = fake
    return c


def test_search_foods_maps_models_to_candidates():
    fake = FakeFs()
    fake.foods.search_return = [
        NS(food_id=1, food_name="Buckwheat", food_description="Per 100g"),
        NS(food_id=2, food_name="Rice", food_description=None),
    ]
    out = make_client(fake).search_foods("buckwheat", max_results=5)
    assert out[0] == FoodCandidate("1", "Buckwheat", "Per 100g")
    assert out[1] == FoodCandidate("2", "Rice", "")
    assert fake.foods.last_search == ("buckwheat", 5)


def test_search_foods_empty():
    fake = FakeFs()
    fake.foods.search_return = []
    assert make_client(fake).search_foods("nothing") == []


def test_get_servings_extracts_gram_serving():
    fake = FakeFs()
    fake.foods.food_return = NS(servings=NS(serving=[
        NS(serving_id=10, serving_description="1 cup",
           metric_serving_amount=Decimal("195.0"), metric_serving_unit="g"),
        NS(serving_id=11, serving_description="1 oz",
           metric_serving_amount=Decimal("1.0"), metric_serving_unit="oz"),
    ]))
    out = make_client(fake).get_servings("1")
    assert out[0] == Serving("10", "1 cup", 195.0, "g")
    assert out[1] == Serving("11", "1 oz", None, "oz")


def test_get_servings_handles_none_food():
    fake = FakeFs()
    fake.foods.food_return = None
    assert make_client(fake).get_servings("1") == []


def test_get_servings_handles_none_servings():
    fake = FakeFs()
    fake.foods.food_return = NS(servings=None)
    assert make_client(fake).get_servings("1") == []


def test_create_entry_returns_id_from_call_and_passes_args():
    fake = FakeFs()
    fake.call_return = {"food_entry_id": {"value": "9001"}}
    eid = make_client(fake).create_entry("39690", "Buckwheat", "62421", 2.0,
                                         "lunch", None)
    assert eid == "9001"
    params, method = fake.calls[0]
    assert method == "POST"
    assert params["method"] == "food_entry.create"
    assert params["food_id"] == "39690"
    assert params["food_entry_name"] == "Buckwheat"
    assert params["serving_id"] == "62421"
    assert params["number_of_units"] == 2.0
    assert params["meal"] == "lunch"
    assert "date" not in params          # date=None опускается


def test_create_entry_missing_id_returns_empty_string():
    fake = FakeFs()
    fake.call_return = {}
    assert make_client(fake).create_entry("1", "X", "2", 1.0, "lunch") == ""


def test_delete_entry():
    fake = FakeFs()
    make_client(fake).delete_entry("9001")
    assert fake.diary.deleted == ["9001"]
