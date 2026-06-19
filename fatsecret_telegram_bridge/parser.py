import json
import logging
import re
from typing import Optional

from fatsecret_telegram_bridge.llm.base import LLMProvider
from fatsecret_telegram_bridge.models import ParsedItem

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You extract food items from a dictated meal phrase. The phrase may be in "
    "any language. "
    "Return STRICTLY a JSON object of the form "
    '{"items": [{"name": str, "query_en": str, "quantity": number|null, '
    '"unit": str|null, "meal_hint": "breakfast"|"lunch"|"dinner"|"other"|null, '
    '"confidence": number}]}. '
    "No text outside the JSON. "
    "name — the food as the user said it, in the original language. "
    "query_en — the common ENGLISH product name for that food, translated from "
    "whatever language the user used, short and searchable for the FatSecret "
    "(US/English) database, e.g. 'oatmeal', 'cottage cheese', 'chicken breast'. "
    "quantity — the numeric amount (e.g. 200 for '200 g', 6 for '6 oz', "
    "2 for '2 eggs'); null if not stated. "
    "unit — the measurement normalized to a short token, one of: g, kg, oz, lb, "
    "ml, l, cup, tbsp, tsp, slice, piece; null if no unit was stated. "
    "If a list of known names is provided, map name to the closest one "
    "(synonyms, inflections, typos); otherwise keep it as said. "
    "confidence is 0 to 1."
)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


class Parser:
    """LLM-backed parser: free-form phrase -> structured items, with translation."""

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def parse(self, text: str, known_aliases: list[str]) -> list[ParsedItem]:
        logger.info("Parsing text via LLM (%s chars, %s known aliases)",
                    len(text), len(known_aliases))
        user = self._build_user_prompt(text, known_aliases)
        raw = self.provider.complete(SYSTEM_PROMPT, user)
        logger.debug("LLM raw response: %s", raw)
        data = _extract_json(raw)
        if not data or not isinstance(data.get("items"), list):
            logger.warning("LLM did not return valid JSON with items")
            return []
        items = [it for it in (_item_from_dict(d) for d in data["items"]) if it]
        logger.info("Parsed items: %s",
                    [(i.name, i.quantity, i.unit) for i in items])
        return items

    @staticmethod
    def _build_user_prompt(text: str, known_aliases: list[str]) -> str:
        known = ", ".join(known_aliases) if known_aliases else "(none)"
        return f"Known names: {known}\n\nPhrase: {text}"


class RegexParser:
    """No-LLM parser: splits on commas/newlines, reads "<name> <quantity> <unit>".

    No translation (query_en stays None, so search uses name directly). Best for
    users who type structured English input, e.g. "oatmeal 50g, chicken 150 g".
    """

    _SEG = re.compile(r"^(.+?)\s+(\d+(?:[.,]\d+)?)\s*([^\d\s][^\d]*)?$")

    def parse(self, text: str, known_aliases: list[str]) -> list[ParsedItem]:
        items: list[ParsedItem] = []
        # Split on newline/semicolon and on commas — but not a comma inside a
        # decimal like "1,5" (comma followed by a digit).
        for seg in re.split(r",(?!\d)|[\n;]+", text):
            seg = seg.strip()
            if not seg:
                continue
            m = self._SEG.match(seg)
            if m:
                items.append(ParsedItem(
                    name=m.group(1).strip(),
                    quantity=float(m.group(2).replace(",", ".")),
                    unit=(m.group(3) or "").strip() or None,
                ))
            else:
                items.append(ParsedItem(name=seg))
        logger.info("Parsed items via regex: %s",
                    [(i.name, i.quantity, i.unit) for i in items])
        return items


def _item_from_dict(d) -> Optional[ParsedItem]:
    if not isinstance(d, dict) or not d.get("name"):
        return None
    return ParsedItem(
        name=str(d["name"]).strip(),
        query_en=str(d["query_en"]).strip() if d.get("query_en") else None,
        quantity=_to_float(d.get("quantity")),
        unit=str(d["unit"]).strip() if d.get("unit") else None,
        meal_hint=d.get("meal_hint") or None,
        confidence=float(d.get("confidence", 1.0)),
    )


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
