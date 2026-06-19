import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional, Union

from fatsecret_telegram_bridge.diary import Diary, infer_meal
from fatsecret_telegram_bridge.models import (
    FoodCandidate, ParsedItem, ResolvedItem, Serving,
)
from fatsecret_telegram_bridge.parser import Parser, RegexParser
from fatsecret_telegram_bridge.resolver import (
    Resolver, Resolved, NeedsFood, NeedsServing, NeedsQuantity,
)

logger = logging.getLogger(__name__)


@dataclass
class PendingPrompt:
    index: int
    kind: str                      # "food" | "serving" | "quantity"
    parsed: ParsedItem
    candidates: list[FoodCandidate] = field(default_factory=list)
    servings: list[Serving] = field(default_factory=list)
    food_id: Optional[str] = None
    food_name: Optional[str] = None
    serving_id: Optional[str] = None
    unit: Optional[str] = None


@dataclass
class _Session:
    session_id: str
    raw_text: str
    meal: str
    resolved: dict[int, ResolvedItem]      # index -> ResolvedItem
    pending: dict[int, PendingPrompt]      # index -> prompt


@dataclass
class AutoLogged:
    lines: list[str]
    log_id: Optional[int]


@dataclass
class NeedsInput:
    session_id: str
    pending: list[PendingPrompt]


ProcessResult = Union[AutoLogged, NeedsInput]


class LoggerService:
    def __init__(self, provider, client, store,
                 clock: Callable[[], datetime] = datetime.now,
                 meal_bounds: tuple[int, int, int, int] = (5, 11, 16, 22)):
        # provider is None -> no LLM, use the regex parser (no translation).
        self.parser = RegexParser() if provider is None else Parser(provider)
        self.client = client
        self.store = store
        self.resolver = Resolver(client, store)
        self.diary = Diary(client)
        self.clock = clock
        self.meal_bounds = meal_bounds
        self._sessions: dict[str, _Session] = {}

    # --- main entry ---
    def process_text(self, text: str) -> ProcessResult:
        meal = infer_meal(self.clock(), *self.meal_bounds)
        logger.info("process_text: %r (meal by time: %s)", text, meal)
        items = self.parser.parse(text, self.store.all_alias_names())
        resolved: dict[int, ResolvedItem] = {}
        pending: dict[int, PendingPrompt] = {}
        for idx, item in enumerate(items):
            self._record(idx, self.resolver.resolve(item, meal), resolved, pending)
        session = _Session(str(uuid.uuid4()), text, meal, resolved, pending)
        if pending:
            self._sessions[session.session_id] = session
            logger.info("Input needed for %s items, auto-resolved %s (session=%s)",
                        len(pending), len(resolved), session.session_id)
            return NeedsInput(session.session_id, list(pending.values()))
        return self._finalize_session(session)

    # --- clarification callbacks ---
    def choose_food(self, session_id: str, index: int, food_id: str,
                    food_name: Optional[str] = None) -> None:
        session = self._sessions[session_id]
        prompt = session.pending[index]
        if food_name is None:
            food_name = next(
                (c.food_name for c in prompt.candidates if c.food_id == food_id),
                food_id,
            )
        res = self.resolver.confirm_food(prompt.parsed, food_id, food_name,
                                         session.meal)
        self._record(index, res, session.resolved, session.pending)

    def choose_serving(self, session_id: str, index: int, serving_id: str) -> None:
        session = self._sessions[session_id]
        prompt = session.pending[index]
        serving = next((s for s in prompt.servings if s.serving_id == serving_id),
                       None)
        if serving is None:
            return
        res = self.resolver.choose_serving(prompt.parsed, prompt.food_id,
                                           prompt.food_name, serving, session.meal)
        self._record(index, res, session.resolved, session.pending)

    def set_quantity(self, session_id: str, index: int, quantity: float) -> None:
        session = self._sessions[session_id]
        prompt = session.pending[index]
        res = self.resolver.set_quantity(
            prompt.parsed, prompt.food_id, prompt.food_name, prompt.serving_id,
            prompt.unit, quantity, session.meal)
        self._record(index, res, session.resolved, session.pending)

    def finalize(self, session_id: str) -> ProcessResult:
        session = self._sessions[session_id]
        if session.pending:
            return NeedsInput(session_id, list(session.pending.values()))
        self._sessions.pop(session_id, None)
        return self._finalize_session(session)

    def undo(self, log_id: Optional[int]) -> int:
        if log_id is None:
            return 0
        rec = self.store.get_log(log_id)
        if not rec:
            logger.warning("undo: log_id=%s not found", log_id)
            return 0
        logger.info("undo log_id=%s: deleting %s entries",
                    log_id, len(rec["entry_ids"]))
        for eid in rec["entry_ids"]:
            self.client.delete_entry(eid)
        return len(rec["entry_ids"])

    # --- internal ---
    def _record(self, index, res, resolved, pending) -> None:
        if isinstance(res, Resolved):
            resolved[index] = res.item
            pending.pop(index, None)
        elif isinstance(res, NeedsFood):
            pending[index] = PendingPrompt(index, "food", res.parsed,
                                           candidates=res.candidates)
        elif isinstance(res, NeedsServing):
            pending[index] = PendingPrompt(index, "serving", res.parsed,
                                           servings=res.servings,
                                           food_id=res.food_id,
                                           food_name=res.food_name)
        elif isinstance(res, NeedsQuantity):
            pending[index] = PendingPrompt(index, "quantity", res.parsed,
                                           food_id=res.food_id,
                                           food_name=res.food_name,
                                           serving_id=res.serving_id,
                                           unit=res.unit)

    def _finalize_session(self, session: _Session) -> AutoLogged:
        items = [session.resolved[i] for i in sorted(session.resolved)]
        if not items:
            logger.info("Nothing to log (0 resolved items)")
            return AutoLogged(lines=[], log_id=None)
        entry_ids = self.diary.write(items)
        log_id = self.store.add_log(session.raw_text, entry_ids)
        logger.info("Logged %s items, log_id=%s, entry_ids=%s",
                    len(items), log_id, entry_ids)
        lines = [f"{it.food_name} — {it.number_of_units:g} {it.unit} ({it.meal})"
                 for it in items]
        return AutoLogged(lines=lines, log_id=log_id)
