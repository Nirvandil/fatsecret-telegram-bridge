import logging
from datetime import datetime
from typing import Optional

from fatsecret_telegram_bridge.models import ResolvedItem

logger = logging.getLogger(__name__)


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


class Diary:
    def __init__(self, client):
        self.client = client

    def write(self, items: list[ResolvedItem],
              date: Optional[datetime] = None) -> list[str]:
        ids: list[str] = []
        for it in items:
            logger.info("Diary write: %s — %g %s (%s)",
                        it.food_name, it.number_of_units, it.unit, it.meal)
            ids.append(self.client.create_entry(
                it.food_id, it.food_name, it.serving_id, it.number_of_units,
                it.meal, date))
        return ids
