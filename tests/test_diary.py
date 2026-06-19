from datetime import datetime

from fatsecret_telegram_bridge.diary import infer_meal, Diary
from fatsecret_telegram_bridge.models import ResolvedItem


def test_infer_meal_boundaries():
    def at(h):
        return infer_meal(datetime(2026, 6, 17, h, 0))
    assert at(7) == "breakfast"
    assert at(13) == "lunch"
    assert at(19) == "dinner"
    assert at(23) == "other"
    assert at(3) == "other"
    # left-inclusive boundaries
    assert at(5) == "breakfast"
    assert at(11) == "lunch"
    assert at(16) == "dinner"


def test_infer_meal_custom_bounds():
    assert infer_meal(datetime(2026, 6, 17, 10, 0), breakfast=6, lunch=12) == "breakfast"


class FakeClient:
    def __init__(self):
        self.calls = []

    def create_entry(self, food_id, food_name, serving_id, number_of_units,
                     meal, date=None):
        self.calls.append((food_id, food_name, serving_id, number_of_units,
                           meal, date))
        return f"e{len(self.calls)}"


def test_diary_write_passes_number_of_units_and_returns_ids():
    c = FakeClient()
    items = [
        ResolvedItem("гречка", "11", "Buckwheat", "22", 200.0, "g", "lunch"),
        ResolvedItem("chicken", "33", "Chicken", "44", 6.0, "oz", "lunch"),
    ]
    ids = Diary(c).write(items)
    assert ids == ["e1", "e2"]
    assert c.calls[0] == ("11", "Buckwheat", "22", 200.0, "lunch", None)
    assert c.calls[1] == ("33", "Chicken", "44", 6.0, "lunch", None)
