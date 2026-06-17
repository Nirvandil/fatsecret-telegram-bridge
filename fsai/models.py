from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedItem:
    """Результат парсинга одной позиции фразы.

    `name` — название как сказал пользователь (ключ личной таблицы, по-русски).
    `query_en` — англоязычный поисковый запрос для базы FatSecret (US/English).
    """
    name: str
    query_en: Optional[str] = None
    grams: Optional[float] = None
    meal_hint: Optional[str] = None
    confidence: float = 1.0


@dataclass
class FoodCandidate:
    """Кандидат из foods.search."""
    food_id: str
    food_name: str
    description: str = ""


@dataclass
class Serving:
    """Порция продукта из food.get.

    grams — сколько граммов в ОДНОЙ логируемой единице этой порции
    (metric_serving_amount / number_of_units). Для порции «100 g» FatSecret
    отдаёт metric=100, number_of_units=100 → grams=1.0, и тогда
    number_of_units в записи дневника = число граммов.
    is_gram — это «граммовая» порция (measurement_description == "g").
    """
    serving_id: str
    description: str
    grams: Optional[float]      # граммов на одну логируемую единицу
    metric_unit: Optional[str]
    is_gram: bool = False


@dataclass
class AliasRecord:
    """Строка личной таблицы соответствий."""
    alias: str
    food_id: str
    serving_id: str
    grams_per_serving: float
    food_name: str


@dataclass
class ResolvedItem:
    """Полностью разрешённая позиция, готовая к записи в дневник."""
    alias: str
    food_id: str
    serving_id: str
    food_name: str
    grams: float
    grams_per_serving: float
    meal: str
