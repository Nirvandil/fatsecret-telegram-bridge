from types import SimpleNamespace as NS

from fatsecret_telegram_bridge.fatsecret_client import FatSecretClient
from fatsecret_telegram_bridge.models import FoodCandidate, Serving


class FakeFoods:
    def __init__(self):
        self.search_return = []
        self.food_return = None
        self.last_search = None
        self.last_get = None

    def search_v1(self, search_expression=None, max_results=None,
                  page_number=None, region=None, language=None):
        self.last_search = (search_expression, max_results, region, language)
        return self.search_return

    def get_v2(self, food_id, region=None, language=None):
        self.last_get = (food_id, region, language)
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


def make_client(fake, region=None, language=None):
    c = FatSecretClient.__new__(FatSecretClient)
    c._fs = fake
    c._region = region
    c._language = language
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
    assert fake.foods.last_search == ("buckwheat", 5, None, None)


def test_search_foods_empty():
    fake = FakeFs()
    fake.foods.search_return = []
    assert make_client(fake).search_foods("nothing") == []


def test_search_foods_filters_null_candidate():
    # For no matches FatSecret returns a single "empty" candidate.
    fake = FakeFs()
    fake.foods.search_return = [NS(food_id=None, food_name=None,
                                   food_description="")]
    assert make_client(fake).search_foods("яблоки") == []


def test_region_language_passed_through():
    fake = FakeFs()
    make_client(fake, region="DE", language="de").search_foods("milch")
    assert fake.foods.last_search[2:] == ("DE", "de")


def test_get_servings_maps_measurement():
    fake = FakeFs()
    fake.foods.food_return = NS(servings=NS(serving=[
        NS(serving_id=10, serving_description="100 g", measurement_description="g"),
        NS(serving_id=11, serving_description="1 oz", measurement_description="oz"),
        NS(serving_id=12, serving_description='1 medium (1-1/4" dia)',
           measurement_description='medium (1-1/4" dia)'),
    ]))
    out = make_client(fake).get_servings("1")
    assert out[0] == Serving("10", "100 g", "g")
    assert out[1] == Serving("11", "1 oz", "oz")
    assert out[2] == Serving("12", '1 medium (1-1/4" dia)', "medium")


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
    eid = make_client(fake).create_entry("39690", "Buckwheat", "62421", 6.0,
                                         "lunch", None)
    assert eid == "9001"
    params, method = fake.calls[0]
    assert method == "POST"
    assert params["method"] == "food_entry.create"
    assert params["food_id"] == "39690"
    assert params["food_entry_name"] == "Buckwheat"
    assert params["serving_id"] == "62421"
    assert params["number_of_units"] == 6.0
    assert params["meal"] == "lunch"
    assert "date" not in params          # date=None is omitted


def test_create_entry_missing_id_returns_empty_string():
    fake = FakeFs()
    fake.call_return = {}
    assert make_client(fake).create_entry("1", "X", "2", 1.0, "lunch") == ""


def test_delete_entry():
    fake = FakeFs()
    make_client(fake).delete_entry("9001")
    assert fake.diary.deleted == ["9001"]
