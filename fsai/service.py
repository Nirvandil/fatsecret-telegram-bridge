import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional, Union

from fsai.diary import Diary, infer_meal
from fsai.models import FoodCandidate, ParsedItem, ResolvedItem, Serving
from fsai.parser import Parser
from fsai.resolver import (
    Resolver, Resolved, NeedsGrams, NeedsFood, NeedsServing,
)

logger = logging.getLogger(__name__)


@dataclass
class PendingPrompt:
    index: int
    kind: str                      # "food" | "grams" | "serving"
    parsed: ParsedItem
    candidates: list[FoodCandidate] = field(default_factory=list)
    servings: list[Serving] = field(default_factory=list)
    food_id: Optional[str] = None
    food_name: Optional[str] = None


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
        self.parser = Parser(provider)
        self.client = client
        self.store = store
        self.resolver = Resolver(client, store)
        self.diary = Diary(client)
        self.clock = clock
        self.meal_bounds = meal_bounds
        self._sessions: dict[str, _Session] = {}

    # --- основной вход ---
    def process_text(self, text: str) -> ProcessResult:
        meal = infer_meal(self.clock(), *self.meal_bounds)
        logger.info("process_text: %r (приём пищи по времени: %s)", text, meal)
        items = self.parser.parse(text, self.store.all_alias_names())
        resolved: dict[int, ResolvedItem] = {}
        pending: dict[int, PendingPrompt] = {}
        for idx, item in enumerate(items):
            res = self.resolver.resolve(item, meal)
            self._record(idx, item, res, resolved, pending)
        session = _Session(str(uuid.uuid4()), text, meal, resolved, pending)
        if pending:
            self._sessions[session.session_id] = session
            logger.info("Нужен ввод по %s позициям, авто-разрешено %s "
                        "(session=%s)", len(pending), len(resolved),
                        session.session_id)
            return NeedsInput(session.session_id, list(pending.values()))
        return self._finalize_session(session)

    # --- колбэки уточнения ---
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
        self._record(index, prompt.parsed, res, session.resolved,
                     session.pending)

    def set_grams(self, session_id: str, index: int, grams: float) -> None:
        session = self._sessions[session_id]
        prompt = session.pending[index]
        prompt.parsed.grams = grams
        res = self.resolver.resolve(prompt.parsed, session.meal)
        self._record(index, prompt.parsed, res, session.resolved,
                     session.pending)

    def choose_serving(self, session_id: str, index: int, serving: Serving,
                       grams_per_serving: float) -> None:
        session = self._sessions[session_id]
        prompt = session.pending[index]
        res = self.resolver.confirm_serving(
            prompt.parsed, prompt.food_id, prompt.food_name, serving,
            grams_per_serving, session.meal)
        self._record(index, prompt.parsed, res, session.resolved,
                     session.pending)

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
            logger.warning("undo: log_id=%s не найден", log_id)
            return 0
        logger.info("undo log_id=%s: удаляю %s записей",
                    log_id, len(rec["entry_ids"]))
        for eid in rec["entry_ids"]:
            self.client.delete_entry(eid)
        return len(rec["entry_ids"])

    # --- внутреннее ---
    def _record(self, index, parsed, res, resolved, pending) -> None:
        if isinstance(res, Resolved):
            resolved[index] = res.item
            pending.pop(index, None)
        elif isinstance(res, NeedsGrams):
            pending[index] = PendingPrompt(index, "grams", parsed)
        elif isinstance(res, NeedsFood):
            pending[index] = PendingPrompt(index, "food", parsed,
                                           candidates=res.candidates)
        elif isinstance(res, NeedsServing):
            pending[index] = PendingPrompt(index, "serving", parsed,
                                           servings=res.servings,
                                           food_id=res.food_id,
                                           food_name=res.food_name)

    def _finalize_session(self, session: _Session) -> AutoLogged:
        items = [session.resolved[i] for i in sorted(session.resolved)]
        if not items:
            logger.info("Нечего записывать (0 разрешённых позиций)")
            return AutoLogged(lines=[], log_id=None)
        entry_ids = self.diary.write(items)
        log_id = self.store.add_log(session.raw_text, entry_ids)
        logger.info("Залогировано %s позиций, log_id=%s, entry_ids=%s",
                    len(items), log_id, entry_ids)
        lines = [
            f"{it.food_name} — {it.grams:g} г ({it.meal})" for it in items
        ]
        return AutoLogged(lines=lines, log_id=log_id)
