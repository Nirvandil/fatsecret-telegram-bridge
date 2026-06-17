from datetime import datetime
from typing import Optional

from fsai.models import ResolvedItem


def infer_meal(now: datetime, breakfast: int = 5, lunch: int = 11,
               dinner: int = 16, dinner_end: int = 22) -> str:
    h = now.hour
    if breakfast <= h < lunch:
        return "breakfast"
    if lunch <= h < dinner:
        return "lunch"
    if dinner <= h < dinner_end:
        return "dinner"
    return "other"


def units_for(grams: float, grams_per_serving: float) -> float:
    return grams / grams_per_serving


class Diary:
    def __init__(self, client):
        self.client = client

    def write(self, items: list[ResolvedItem],
              date: Optional[datetime] = None) -> list[str]:
        ids: list[str] = []
        for it in items:
            n = units_for(it.grams, it.grams_per_serving)
            ids.append(self.client.create_entry(
                it.food_id, it.food_name, it.serving_id, n, it.meal, date))
        return ids
