from typing import Optional

from fsai.models import FoodCandidate, Serving


class FatSecretClient:
    """Тонкая обёртка над библиотекой `fatsecret` 4.0.4 (namespaced resource API).

    Нормализует типизированные pydantic-модели библиотеки (`Food`, `Serving`,
    `FoodEntry`) в наши доменные модели. Сама библиотека отвечает за подпись
    OAuth 1.0a (HMAC-SHA1), ретраи и разбор ошибок FatSecret.
    """

    def __init__(self, consumer_key: str, consumer_secret: str,
                 access_token: str, access_secret: str):
        from fatsecret import Fatsecret
        self._fs = Fatsecret(
            consumer_key, consumer_secret,
            session_token=(access_token, access_secret),
        )

    def search_foods(self, query: str, max_results: int = 5) -> list[FoodCandidate]:
        foods = self._fs.foods.search_v1(
            search_expression=query, max_results=max_results)
        return [
            FoodCandidate(
                food_id=str(f.food_id),
                food_name=f.food_name,
                description=f.food_description or "",
            )
            for f in (foods or [])
        ]

    def get_servings(self, food_id: str) -> list[Serving]:
        food = self._fs.foods.get_v2(food_id)
        if food is None or food.servings is None:
            return []
        out: list[Serving] = []
        for s in (food.servings.serving or []):
            unit = s.metric_serving_unit
            amount = s.metric_serving_amount
            grams = float(amount) if unit == "g" and amount is not None else None
            out.append(Serving(
                serving_id=str(s.serving_id),
                description=s.serving_description or "",
                grams=grams,
                metric_unit=unit,
            ))
        return out

    def create_entry(self, food_id: str, food_name: str, serving_id: str,
                     number_of_units: float, meal: str,
                     date=None) -> str:
        entries = self._fs.diary.entry_create_v1(
            food_id=food_id, food_entry_name=food_name, serving_id=serving_id,
            number_of_units=number_of_units, meal=meal, date=date)
        if not entries:
            return ""
        return str(entries[0].food_entry_id)

    def delete_entry(self, entry_id: str) -> None:
        self._fs.diary.entry_delete_v1(food_entry_id=entry_id)
