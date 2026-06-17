from datetime import datetime

from fsai.diary import infer_meal, units_for, Diary
from fsai.models import ResolvedItem


def test_units_for():
    assert units_for(200.0, 100.0) == 2.0
    assert units_for(50.0, 100.0) == 0.5


def test_infer_meal_boundaries():
    def at(h):
        return infer_meal(datetime(2026, 6, 17, h, 0))
    assert at(7) == "breakfast"
    assert at(13) == "lunch"
    assert at(19) == "dinner"
    assert at(23) == "other"
    assert at(3) == "other"
    # границы включительно слева
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


def test_diary_write_computes_units_and_returns_ids():
    c = FakeClient()
    items = [
        ResolvedItem("гречка", "11", "22", "Buckwheat", 200.0, 100.0, "lunch"),
        ResolvedItem("филе", "33", "44", "Chicken", 150.0, 100.0, "lunch"),
    ]
    ids = Diary(c).write(items)
    assert ids == ["e1", "e2"]
    assert c.calls[0] == ("11", "Buckwheat", "22", 2.0, "lunch", None)
    assert c.calls[1] == ("33", "Chicken", "44", 1.5, "lunch", None)
