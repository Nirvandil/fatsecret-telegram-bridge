from typing import Any

from fsai.models import FoodCandidate, Serving


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


class FatSecretClient:
    """Тонкая обёртка над pyfatsecret: нормализует ответы в наши модели."""

    def __init__(self, consumer_key: str, consumer_secret: str,
                 access_token: str, access_secret: str):
        from fatsecret import Fatsecret
        self._fs = Fatsecret(
            consumer_key, consumer_secret,
            session_token=(access_token, access_secret),
        )

    def search_foods(self, query: str, max_results: int = 5) -> list[FoodCandidate]:
        raw = self._fs.foods_search(query, max_results=max_results)
        return [
            FoodCandidate(
                food_id=str(f["food_id"]),
                food_name=f["food_name"],
                description=f.get("food_description", ""),
            )
            for f in _as_list(raw)
        ]

    def get_servings(self, food_id: str) -> list[Serving]:
        food = self._fs.food_get(food_id)
        servings = _as_list(food.get("servings", {}).get("serving"))
        out: list[Serving] = []
        for s in servings:
            unit = s.get("metric_serving_unit")
            amount = s.get("metric_serving_amount")
            grams = float(amount) if unit == "g" and amount is not None else None
            out.append(Serving(
                serving_id=str(s["serving_id"]),
                description=s.get("serving_description", ""),
                grams=grams,
                metric_unit=unit,
            ))
        return out

    def create_entry(self, food_id: str, food_name: str, serving_id: str,
                     number_of_units: float, meal: str,
                     date=None) -> str:
        entry_id = self._fs.food_entry_create(
            food_id, food_name, serving_id, number_of_units, meal, date)
        return str(entry_id)

    def delete_entry(self, entry_id: str) -> None:
        self._fs.food_entry_delete(entry_id)
