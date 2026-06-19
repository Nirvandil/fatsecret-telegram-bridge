from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedItem:
    """One parsed food item from a phrase.

    `name` — the food as the user said it (the personal-table key; any language).
    `query_en` — an English search query for the FatSecret DB (US/English).
    """
    name: str
    query_en: Optional[str] = None
    grams: Optional[float] = None
    meal_hint: Optional[str] = None
    confidence: float = 1.0


@dataclass
class FoodCandidate:
    """A candidate from foods.search."""
    food_id: str
    food_name: str
    description: str = ""


@dataclass
class Serving:
    """A food serving from food.get.

    grams — grams in ONE loggable unit of this serving
    (metric_serving_amount / number_of_units). For a "100 g" serving FatSecret
    returns metric=100, number_of_units=100 → grams=1.0, so the diary entry's
    number_of_units equals the number of grams.
    is_gram — this is the "gram" serving (measurement_description == "g").
    """
    serving_id: str
    description: str
    grams: Optional[float]      # grams per one loggable unit
    metric_unit: Optional[str]
    is_gram: bool = False


@dataclass
class AliasRecord:
    """A row of the personal lookup table."""
    alias: str
    food_id: str
    serving_id: str
    grams_per_serving: float
    food_name: str


@dataclass
class ResolvedItem:
    """A fully resolved item, ready to write to the diary."""
    alias: str
    food_id: str
    serving_id: str
    food_name: str
    grams: float
    grams_per_serving: float
    meal: str
