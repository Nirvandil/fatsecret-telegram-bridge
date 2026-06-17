from dataclasses import dataclass
from typing import Union

from fsai.models import (
    AliasRecord, FoodCandidate, ParsedItem, ResolvedItem, Serving,
)


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
            return NeedsGrams(item)
        rec = self.store.get_alias(item.name)
        if rec is not None:
            return Resolved(self._to_resolved(item, rec, meal))
        candidates = self.client.search_foods(item.name)
        return NeedsFood(item, candidates, meal)

    def confirm_food(self, parsed: ParsedItem, food_id: str,
                     food_name: str, meal: str) -> Resolution:
        servings = self.client.get_servings(food_id)
        gram_servings = [s for s in servings if s.grams]
        if not gram_servings:
            return NeedsServing(parsed, food_id, food_name, servings, meal)
        chosen = gram_servings[0]
        rec = AliasRecord(
            alias=parsed.name, food_id=food_id, serving_id=chosen.serving_id,
            grams_per_serving=chosen.grams, food_name=food_name,
        )
        self.store.save_alias(rec)
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
