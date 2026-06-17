import logging

from fsai.models import FoodCandidate, Serving

logger = logging.getLogger(__name__)


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
        logger.info("FatSecret foods.search %r (max=%s)", query, max_results)
        foods = self._fs.foods.search_v1(
            search_expression=query, max_results=max_results)
        out = []
        for f in (foods or []):
            # Когда совпадений нет, FatSecret возвращает один «пустой» кандидат
            # с food_id=None — это не результат, пропускаем.
            if f.food_id is None:
                continue
            out.append(FoodCandidate(
                food_id=str(f.food_id),
                food_name=f.food_name or "",
                description=f.food_description or "",
            ))
        logger.info("  → %s кандидатов", len(out))
        return out

    def get_servings(self, food_id: str) -> list[Serving]:
        logger.info("FatSecret food.get %s", food_id)
        food = self._fs.foods.get_v2(food_id)
        if food is None or food.servings is None:
            logger.info("  → нет порций")
            return []
        out: list[Serving] = []
        for s in (food.servings.serving or []):
            unit = s.metric_serving_unit
            amount = s.metric_serving_amount
            # number_of_units — сколько базовых единиц в этой порции (для «100 g»
            # это 100). Граммов на ОДНУ логируемую единицу = amount / number_of_units.
            nunits = float(s.number_of_units) if s.number_of_units else 1.0
            grams = (float(amount) / nunits
                     if unit == "g" and amount is not None and nunits else None)
            out.append(Serving(
                serving_id=str(s.serving_id),
                description=s.serving_description or "",
                grams=grams,
                metric_unit=unit,
                is_gram=(s.measurement_description == "g"),
            ))
        logger.info("  → %s порций (%s в граммах, g-порция: %s)",
                    len(out), sum(1 for s in out if s.grams),
                    any(s.is_gram for s in out))
        return out

    def create_entry(self, food_id: str, food_name: str, serving_id: str,
                     number_of_units: float, meal: str,
                     date=None) -> str:
        # Высокоуровневый fs.diary.entry_create_v1 в fatsecret 4.0.4 распаковывает
        # ответ по ключу `food_entries.food_entry`, тогда как food_entry.create
        # отвечает `{"food_entry_id": {"value": "<id>"}}` — из-за чего id теряется.
        # Зовём _call напрямую и парсим id сами (нужен для отмены записи).
        params = {
            "method": "food_entry.create",
            "food_id": food_id,
            "food_entry_name": food_name,
            "serving_id": serving_id,
            "number_of_units": number_of_units,
            "meal": meal,
        }
        if date is not None:
            params["date"] = self._fs.unix_time_v2(date)
        logger.info("FatSecret food_entry.create food=%s serving=%s units=%s meal=%s",
                    food_id, serving_id, number_of_units, meal)
        payload = self._fs._call(params, method="POST")
        fe = payload.get("food_entry_id") if isinstance(payload, dict) else None
        entry_id = str(fe.get("value", "")) if isinstance(fe, dict) else (
            str(fe) if fe else "")
        logger.info("  → entry_id=%s", entry_id or "(пусто!)")
        return entry_id

    def delete_entry(self, entry_id: str) -> None:
        logger.info("FatSecret food_entry.delete %s", entry_id)
        self._fs.diary.entry_delete_v1(food_entry_id=entry_id)
