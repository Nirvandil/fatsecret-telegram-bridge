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
        self.created = []
        self.deleted = []
        self.create_return = []

    def entry_create_v1(self, food_id=None, food_entry_name=None, serving_id=None,
                        number_of_units=None, meal=None, date=None):
        self.created.append((food_id, food_entry_name, serving_id,
                             number_of_units, meal, date))
        return self.create_return

    def entry_delete_v1(self, food_entry_id=None):
        self.deleted.append(food_entry_id)


class FakeFs:
    def __init__(self):
        self.foods = FakeFoods()
        self.diary = FakeDiary()


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


def test_create_entry_returns_str_id_and_passes_args():
    fake = FakeFs()
    fake.diary.create_return = [NS(food_entry_id=9001)]
    eid = make_client(fake).create_entry("1", "Buckwheat", "10", 2.0, "lunch", None)
    assert eid == "9001"
    assert fake.diary.created == [("1", "Buckwheat", "10", 2.0, "lunch", None)]


def test_create_entry_empty_response_returns_empty_string():
    fake = FakeFs()
    fake.diary.create_return = []
    assert make_client(fake).create_entry("1", "X", "2", 1.0, "lunch") == ""


def test_delete_entry():
    fake = FakeFs()
    make_client(fake).delete_entry("9001")
    assert fake.diary.deleted == ["9001"]
