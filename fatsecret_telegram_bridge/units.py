"""Normalize measurement units so a parsed unit can be matched to a FatSecret
serving's measurement_description (e.g. 'grams'/'г' -> 'g', 'ounce' -> 'oz')."""

_SYNONYMS = {
    "g": "g", "gram": "g", "grams": "g", "gr": "g", "gramm": "g",
    "г": "g", "гр": "g", "грамм": "g", "грамма": "g", "граммов": "g",
    "kg": "kg", "kilogram": "kg", "kilograms": "kg", "кг": "kg",
    "mg": "mg", "milligram": "mg",
    "oz": "oz", "ounce": "oz", "ounces": "oz", "унция": "oz", "унции": "oz",
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
    "ml": "ml", "milliliter": "ml", "millilitre": "ml", "мл": "ml",
    "l": "l", "liter": "l", "litre": "l", "л": "l",
    "cup": "cup", "cups": "cup", "стакан": "cup",
    "tbsp": "tbsp", "tablespoon": "tbsp", "tablespoons": "tbsp",
    "tsp": "tsp", "teaspoon": "tsp", "teaspoons": "tsp",
    "slice": "slice", "slices": "slice",
    "piece": "piece", "pieces": "piece", "pcs": "piece", "pc": "piece",
    "шт": "piece", "штука": "piece", "штуки": "piece",
    "serving": "serving", "servings": "serving",
    "small": "small", "medium": "medium", "large": "large",
}


def normalize_unit(unit) -> str:
    """Map a free-form unit string to a canonical token; '' if empty/None.

    Unknown units fall back to their first lowercased word, so a serving like
    'medium (1-1/4" dia)' normalizes to 'medium'.
    """
    if not unit:
        return ""
    token = str(unit).strip().lower()
    if token in _SYNONYMS:
        return _SYNONYMS[token]
    first = token.split()[0] if token.split() else token
    return _SYNONYMS.get(first, first)
