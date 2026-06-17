import json
import logging
import re
from typing import Optional

from fsai.llm.base import LLMProvider
from fsai.models import ParsedItem

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ты извлекаешь позиции питания из надиктованной фразы на русском. "
    "Верни СТРОГО JSON-объект вида "
    '{"items": [{"name": str, "query_en": str, "grams": number|null, '
    '"meal_hint": "breakfast"|"lunch"|"dinner"|"other"|null, '
    '"confidence": number}]}. '
    "Никакого текста вне JSON. "
    "name — название как сказал пользователь, по-русски. "
    "query_en — короткий АНГЛИЙСКИЙ поисковый запрос для базы продуктов FatSecret "
    "(US/English): обычное название продукта по-английски, например "
    "'яблоки'→'apple', 'овсянка сухая'→'oatmeal dry', 'творог 5%'→'cottage cheese'. "
    "Граммы — число в граммах, если можно их вычислить; иначе null. "
    "Если в подсказке дан список известных названий, приводи name к наиболее "
    "близкому из них (синонимы, падежи, опечатки); иначе оставляй как сказано. "
    "confidence от 0 до 1."
)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


class Parser:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def parse(self, text: str, known_aliases: list[str]) -> list[ParsedItem]:
        logger.info("Парсинг текста (%s симв., %s известных алиасов)",
                    len(text), len(known_aliases))
        user = self._build_user_prompt(text, known_aliases)
        raw = self.provider.complete(SYSTEM_PROMPT, user)
        logger.debug("LLM сырой ответ: %s", raw)
        data = self._extract_json(raw)
        if not data or not isinstance(data.get("items"), list):
            logger.warning("LLM не вернул валидный JSON с items")
            return []
        items: list[ParsedItem] = []
        for it in data["items"]:
            if not isinstance(it, dict) or not it.get("name"):
                continue
            query_en = it.get("query_en")
            items.append(ParsedItem(
                name=str(it["name"]).strip(),
                query_en=str(query_en).strip() if query_en else None,
                grams=_to_float(it.get("grams")),
                meal_hint=it.get("meal_hint") or None,
                confidence=float(it.get("confidence", 1.0)),
            ))
        logger.info("Распознано позиций: %s — %s",
                    len(items), [(i.name, i.grams) for i in items])
        return items

    @staticmethod
    def _build_user_prompt(text: str, known_aliases: list[str]) -> str:
        known = ", ".join(known_aliases) if known_aliases else "(пусто)"
        return f"Известные названия: {known}\n\nФраза: {text}"

    @staticmethod
    def _extract_json(raw: str) -> Optional[dict]:
        if not raw:
            return None
        candidate = raw.strip()
        fence = _FENCE_RE.search(candidate)
        if fence:
            candidate = fence.group(1)
        else:
            obj = _OBJ_RE.search(candidate)
            if obj:
                candidate = obj.group(0)
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
