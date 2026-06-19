from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedItem:
    """One parsed food item from a phrase.

    `name` — the food as the user said it (the personal-table key; any language).
    `query_en` — an English search query for the FatSecret DB (US/English);
        None when no LLM is used (search falls back to `name`).
    `quantity` — amount in `unit` (e.g. 200 for "200 g", 6 for "6 oz"); None if
        not stated.
    `unit` — the measurement the user used ("g", "oz", "cup", ...); None if none.
    """
    name: str
    query_en: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
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

    `measurement` — normalized unit of this serving's base measurement
        ("g", "oz", "cup", ...). FatSecret's number_of_units in a diary entry is
        counted in this unit, so logging is `number_of_units = quantity` with no
        conversion when the user's unit matches `measurement`.
    `description` — human-readable serving label, e.g. "100 g", "1 cup".
    """
    serving_id: str
    description: str
    measurement: str


@dataclass
class AliasRecord:
    """A row of the personal lookup table: a user name -> a FatSecret food.

    The serving is chosen per message from the unit, so only the food is stored.
    """
    alias: str
    food_id: str
    food_name: str


@dataclass
class ResolvedItem:
    """A fully resolved item, ready to write to the diary."""
    alias: str
    food_id: str
    food_name: str
    serving_id: str
    number_of_units: float      # counted in the serving's measurement unit
    unit: str                   # for display, e.g. "g", "oz", "cup"
    meal: str
