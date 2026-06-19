import logging
from dataclasses import dataclass
from typing import Union

from fatsecret_telegram_bridge.models import (
    AliasRecord, FoodCandidate, ParsedItem, ResolvedItem, Serving,
)

logger = logging.getLogger(__name__)


@dataclass
class Resolved:
    item: ResolvedItem


@dataclass
class NeedsGrams:
    parsed: ParsedItem


@dataclass
class NeedsFood:
    parsed: ParsedItem
    candidates: list[FoodCandidate]
    meal: str


@dataclass
class NeedsServing:
    parsed: ParsedItem
    food_id: str
    food_name: str
    servings: list[Serving]
    meal: str


Resolution = Union[Resolved, NeedsGrams, NeedsFood, NeedsServing]


class Resolver:
    def __init__(self, client, store):
        self.client = client
        self.store = store

    def resolve(self, item: ParsedItem, meal: str) -> Resolution:
        if item.grams is None:
            logger.info("'%s': no grams given -> asking", item.name)
            return NeedsGrams(item)
        rec = self.store.get_alias(item.name)
        if rec is not None:
            logger.info("'%s': found in table (food=%s) -> %s g",
                        item.name, rec.food_id, item.grams)
            return Resolved(self._to_resolved(item, rec, meal))
        search_term = item.query_en or item.name
        logger.info("'%s': not in table -> searching FatSecret for %r",
                    item.name, search_term)
        candidates = self.client.search_foods(search_term)
        return NeedsFood(item, candidates, meal)

    def confirm_food(self, parsed: ParsedItem, food_id: str,
                     food_name: str, meal: str) -> Resolution:
        servings = self.client.get_servings(food_id)
        gram_servings = [s for s in servings if s.grams]
        if not gram_servings:
            logger.info("'%s' (food=%s): no gram serving -> asking for a serving",
                        parsed.name, food_id)
            return NeedsServing(parsed, food_id, food_name, servings, meal)
        # Prefer the "gram" serving (measurement='g'): then grams=1 g/unit,
        # number_of_units == grams, and the diary shows exactly the given grams.
        chosen = next((s for s in gram_servings if s.is_gram), gram_servings[0])
        rec = AliasRecord(
            alias=parsed.name, food_id=food_id, serving_id=chosen.serving_id,
            grams_per_serving=chosen.grams, food_name=food_name,
        )
        self.store.save_alias(rec)
        logger.info("'%s' -> alias saved: food=%s serving=%s (%s g/unit)",
                    parsed.name, food_id, chosen.serving_id, chosen.grams)
        return Resolved(self._to_resolved(parsed, rec, meal))

    def confirm_serving(self, parsed: ParsedItem, food_id: str, food_name: str,
                        serving: Serving, grams_per_serving: float,
                        meal: str) -> Resolved:
        rec = AliasRecord(
            alias=parsed.name, food_id=food_id, serving_id=serving.serving_id,
            grams_per_serving=grams_per_serving, food_name=food_name,
        )
        self.store.save_alias(rec)
        return Resolved(self._to_resolved(parsed, rec, meal))

    @staticmethod
    def _to_resolved(item: ParsedItem, rec: AliasRecord,
                     meal: str) -> ResolvedItem:
        return ResolvedItem(
            alias=rec.alias, food_id=rec.food_id, serving_id=rec.serving_id,
            food_name=rec.food_name, grams=item.grams,
            grams_per_serving=rec.grams_per_serving, meal=meal,
        )
