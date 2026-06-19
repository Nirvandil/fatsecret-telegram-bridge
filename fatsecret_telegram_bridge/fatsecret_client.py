import logging
from typing import Optional

from fatsecret_telegram_bridge.models import FoodCandidate, Serving
from fatsecret_telegram_bridge.units import normalize_unit

logger = logging.getLogger(__name__)


class FatSecretClient:
    """Thin wrapper over the `fatsecret` 4.0.4 library (namespaced resource API).

    Normalizes the library's typed pydantic models (`Food`, `Serving`,
    `FoodEntry`) into our domain models. The library handles OAuth 1.0a
    (HMAC-SHA1) signing, retries, and FatSecret error parsing.

    `region`/`language` are passed to search/get for localized food databases
    (a FatSecret Premier feature; ignored by the free US/English tier).
    """

    def __init__(self, consumer_key: str, consumer_secret: str,
                 access_token: str, access_secret: str,
                 region: Optional[str] = None, language: Optional[str] = None):
        from fatsecret import Fatsecret
        self._fs = Fatsecret(
            consumer_key, consumer_secret,
            session_token=(access_token, access_secret),
        )
        self._region = region or None
        self._language = language or None

    def _loc(self) -> dict:
        loc = {}
        if self._region:
            loc["region"] = self._region
        if self._language:
            loc["language"] = self._language
        return loc

    def search_foods(self, query: str, max_results: int = 5) -> list[FoodCandidate]:
        logger.info("FatSecret foods.search %r (max=%s, loc=%s)",
                    query, max_results, self._loc() or "US")
        foods = self._fs.foods.search_v1(
            search_expression=query, max_results=max_results, **self._loc())
        out = []
        for f in (foods or []):
            # When there are no matches FatSecret returns a single "empty"
            # candidate with food_id=None — that's not a result, skip it.
            if f.food_id is None:
                continue
            out.append(FoodCandidate(
                food_id=str(f.food_id),
                food_name=f.food_name or "",
                description=f.food_description or "",
            ))
        logger.info("  -> %s candidates", len(out))
        return out

    def get_servings(self, food_id: str) -> list[Serving]:
        logger.info("FatSecret food.get %s", food_id)
        food = self._fs.foods.get_v2(food_id, **self._loc())
        if food is None or food.servings is None:
            logger.info("  -> no servings")
            return []
        out: list[Serving] = []
        for s in (food.servings.serving or []):
            out.append(Serving(
                serving_id=str(s.serving_id),
                description=s.serving_description or "",
                measurement=normalize_unit(s.measurement_description),
            ))
        logger.info("  -> %s servings (units: %s)",
                    len(out), sorted({s.measurement for s in out if s.measurement}))
        return out

    def create_entry(self, food_id: str, food_name: str, serving_id: str,
                     number_of_units: float, meal: str,
                     date=None) -> str:
        # The high-level fs.diary.entry_create_v1 in fatsecret 4.0.4 unwraps the
        # response by the `food_entries.food_entry` key, whereas food_entry.create
        # responds with `{"food_entry_id": {"value": "<id>"}}` — so the id is lost.
        # Call _call directly and parse the id ourselves (needed for undo).
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
        logger.info("  -> entry_id=%s", entry_id or "(empty!)")
        return entry_id

    def delete_entry(self, entry_id: str) -> None:
        logger.info("FatSecret food_entry.delete %s", entry_id)
        self._fs.diary.entry_delete_v1(food_entry_id=entry_id)
