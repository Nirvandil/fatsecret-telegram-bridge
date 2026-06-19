import logging
from dataclasses import dataclass
from typing import Optional, Union

from fatsecret_telegram_bridge.models import (
    AliasRecord, FoodCandidate, ParsedItem, ResolvedItem, Serving,
)
from fatsecret_telegram_bridge.units import normalize_unit

logger = logging.getLogger(__name__)


@dataclass
class Resolved:
    item: ResolvedItem


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


@dataclass
class NeedsQuantity:
    parsed: ParsedItem
    food_id: str
    food_name: str
    serving_id: str
    unit: str
    meal: str


Resolution = Union[Resolved, NeedsFood, NeedsServing, NeedsQuantity]


class Resolver:
    def __init__(self, client, store):
        self.client = client
        self.store = store

    def resolve(self, item: ParsedItem, meal: str) -> Resolution:
        rec = self.store.get_alias(item.name)
        if rec is None:
            term = item.query_en or item.name
            logger.info("'%s': not in table -> searching FatSecret for %r",
                        item.name, term)
            return NeedsFood(item, self.client.search_foods(term), meal)
        logger.info("'%s': found in table (food=%s)", item.name, rec.food_id)
        return self._with_food(item, rec.food_id, rec.food_name, meal)

    def confirm_food(self, parsed: ParsedItem, food_id: str, food_name: str,
                     meal: str) -> Resolution:
        # User picked a food from search results -> remember it, then resolve serving.
        self.store.save_alias(AliasRecord(parsed.name, food_id, food_name))
        logger.info("'%s' -> alias saved: food=%s", parsed.name, food_id)
        return self._with_food(parsed, food_id, food_name, meal)

    def choose_serving(self, parsed: ParsedItem, food_id: str, food_name: str,
                       serving: Serving, meal: str) -> Resolution:
        unit = serving.measurement or normalize_unit(parsed.unit)
        if parsed.quantity is None:
            return NeedsQuantity(parsed, food_id, food_name, serving.serving_id,
                                 unit, meal)
        return Resolved(self._resolved(parsed, food_id, food_name,
                                       serving.serving_id, unit, meal))

    def set_quantity(self, parsed: ParsedItem, food_id: str, food_name: str,
                     serving_id: str, unit: str, quantity: float,
                     meal: str) -> Resolved:
        parsed.quantity = quantity
        return Resolved(self._resolved(parsed, food_id, food_name, serving_id,
                                       unit, meal))

    def _with_food(self, item: ParsedItem, food_id: str, food_name: str,
                   meal: str) -> Resolution:
        servings = self.client.get_servings(food_id)
        chosen = self._match_serving(servings, item.unit)
        if chosen is None:
            logger.info("'%s': unit=%r not matched -> ask serving",
                        item.name, item.unit)
            return NeedsServing(item, food_id, food_name, servings, meal)
        if item.quantity is None:
            return NeedsQuantity(item, food_id, food_name, chosen.serving_id,
                                 chosen.measurement, meal)
        return Resolved(self._resolved(item, food_id, food_name,
                                       chosen.serving_id, chosen.measurement, meal))

    @staticmethod
    def _match_serving(servings: list[Serving], unit) -> Optional[Serving]:
        if not unit:
            return None
        target = normalize_unit(unit)
        return next((s for s in servings if s.measurement == target), None)

    @staticmethod
    def _resolved(item: ParsedItem, food_id: str, food_name: str,
                  serving_id: str, unit: str, meal: str) -> ResolvedItem:
        return ResolvedItem(
            alias=item.name, food_id=food_id, food_name=food_name,
            serving_id=serving_id, number_of_units=item.quantity,
            unit=unit, meal=meal,
        )
