from fsai.fatsecret_client import FatSecretClient
from fsai.models import FoodCandidate, Serving


class FakeFatsecret:
    def __init__(self):
        self.created = []
        self.deleted = []
        self.search_return = []
        self.food_return = {}

    def foods_search(self, search_expression, page_number=None, max_results=None):
        self.last_search = (search_expression, max_results)
        return self.search_return

    def food_get(self, food_id):
        self.last_food_id = food_id
        return self.food_return

    def food_entry_create(self, food_id, food_entry_name, serving_id,
                          number_of_units, meal, date=None):
        self.created.append((food_id, food_entry_name, serving_id,
                             number_of_units, meal, date))
        return 9001

    def food_entry_delete(self, food_entry_id):
        self.deleted.append(food_entry_id)


def make_client(fake):
    c = FatSecretClient.__new__(FatSecretClient)
    c._fs = fake
    return c


def test_search_foods_normalizes_list():
    fake = FakeFatsecret()
    fake.search_return = [
        {"food_id": "1", "food_name": "Buckwheat", "food_description": "Per 100g"},
        {"food_id": "2", "food_name": "Rice"},
    ]
    out = make_client(fake).search_foods("buckwheat", max_results=5)
    assert out[0] == FoodCandidate("1", "Buckwheat", "Per 100g")
    assert out[1] == FoodCandidate("2", "Rice", "")
    assert fake.last_search == ("buckwheat", 5)


def test_search_foods_wraps_single_dict():
    fake = FakeFatsecret()
    fake.search_return = {"food_id": "1", "food_name": "Solo"}
    out = make_client(fake).search_foods("solo")
    assert out == [FoodCandidate("1", "Solo", "")]


def test_get_servings_extracts_gram_serving():
    fake = FakeFatsecret()
    fake.food_return = {"servings": {"serving": [
        {"serving_id": "10", "serving_description": "1 cup",
         "metric_serving_amount": "195.0", "metric_serving_unit": "g"},
        {"serving_id": "11", "serving_description": "1 oz",
         "metric_serving_amount": "1.0", "metric_serving_unit": "oz"},
    ]}}
    out = make_client(fake).get_servings("1")
    assert out[0] == Serving("10", "1 cup", 195.0, "g")
    assert out[1] == Serving("11", "1 oz", None, "oz")


def test_get_servings_handles_single_serving_dict():
    fake = FakeFatsecret()
    fake.food_return = {"servings": {"serving": {
        "serving_id": "10", "serving_description": "100 g",
        "metric_serving_amount": "100.0", "metric_serving_unit": "g"}}}
    out = make_client(fake).get_servings("1")
    assert out == [Serving("10", "100 g", 100.0, "g")]


def test_create_entry_returns_str_id_and_passes_args():
    fake = FakeFatsecret()
    eid = make_client(fake).create_entry("1", "Buckwheat", "10", 2.0, "lunch", None)
    assert eid == "9001"
    assert fake.created == [("1", "Buckwheat", "10", 2.0, "lunch", None)]


def test_delete_entry():
    fake = FakeFatsecret()
    make_client(fake).delete_entry("9001")
    assert fake.deleted == ["9001"]
