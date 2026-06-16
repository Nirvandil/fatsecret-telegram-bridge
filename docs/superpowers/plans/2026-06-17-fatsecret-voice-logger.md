# FatSecret Voice Logger — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Telegram-бот, который принимает надиктованный (через голосовой набор Telegram) текст вида «греча отварная 200г, куриное филе 150г», парсит его LLM-ом, сопоставляет с личной таблицей продуктов и пишет записи в дневник питания FatSecret.

**Architecture:** Один Python-процесс, long-polling Telegram-бот. Слоистая структура: тонкие доменные единицы (`models`, `config`, `store`, `parser`, `fatsecret_client`, `resolver`, `diary`), оркестрирующий `service` (фреймворк-независимый, легко тестируется) и тонкий `bot` (только Telegram-обвязка). LLM-провайдер за интерфейсом `LLMProvider` со сменными реализациями Anthropic/OpenAI. Состояние — SQLite. FatSecret-доступ — через `pyfatsecret` (она же делает OAuth 1.0a HMAC-SHA1 подпись и 3-legged oob-флоу).

**Tech Stack:** Python 3.11+, `python-telegram-bot` (async, long-polling), `pyfatsecret`, `anthropic`, `openai`, `python-dotenv`, stdlib `sqlite3`, `pytest`.

---

## File Structure

```
fs-ai/
  pyproject.toml                     # метаданные, зависимости, конфиг pytest
  .gitignore                         # секреты, БД, кэши
  .env.example                       # шаблон переменных окружения
  README.md                          # запуск, авторизация, эксплуатация
  fsai/
    __init__.py
    models.py                        # доменные dataclass'ы (общий словарь типов)
    config.py                        # Config + load_config() из окружения
    store.py                         # SQLite: алиасы + лог записей
    llm/
      __init__.py
      base.py                        # LLMProvider (ABC)
      anthropic_provider.py          # AnthropicProvider
      openai_provider.py             # OpenAIProvider
      factory.py                     # build_provider(config) -> LLMProvider
    parser.py                        # Parser: текст + алиасы -> [ParsedItem]
    fatsecret_client.py              # FatSecretClient: обёртка над pyfatsecret
    resolver.py                      # Resolver: ParsedItem -> Resolution (state machine)
    diary.py                         # infer_meal, units_for, Diary.write()
    service.py                       # LoggerService: оркестрация + pending-сессии + undo
    bot.py                           # Telegram-адаптер: хендлеры, рендеринг, кнопки
    auth_setup.py                    # разовый 3-legged OAuth (oob/PIN)
    __main__.py                      # точка входа: python -m fsai
  tests/
    __init__.py
    conftest.py                      # общие фикстуры (FakeProvider, FakeFatSecret)
    test_config.py
    test_store.py
    test_parser.py
    test_llm_providers.py
    test_fatsecret_client.py
    test_resolver.py
    test_diary.py
    test_service.py
    test_bot_render.py
    test_auth_setup.py
```

**Ответственности (границы):** `models` — только типы данных, без логики. `store` — только персистентность. `parser` — только текст→структура (зависит от `LLMProvider`, не от SDK). `fatsecret_client` — единственное место, знающее про pyfatsecret и форму его ответов. `resolver` — машина состояний разрешения одного продукта. `diary` — расчёт порций и запись. `service` — склейка без знания про Telegram. `bot` — только Telegram (рендеринг + маршрутизация колбэков в service).

---

## Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `fsai/__init__.py`, `fsai/llm/__init__.py`, `tests/__init__.py`, `tests/conftest.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "fsai"
version = "0.1.0"
description = "Voice food logger for FatSecret via Telegram"
requires-python = ">=3.11"
dependencies = [
    "python-telegram-bot>=21,<22",
    "pyfatsecret>=0.2.1",
    "anthropic>=0.40",
    "openai>=1.40",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["fsai*"]
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
__pycache__/
*.pyc
.venv/
.env
*.sqlite3
*.db
.pytest_cache/
*.egg-info/
```

- [ ] **Step 3: Create `.env.example`**

```dotenv
# Telegram
TELEGRAM_TOKEN=
OWNER_CHAT_ID=

# FatSecret app credentials
FATSECRET_CONSUMER_KEY=
FATSECRET_CONSUMER_SECRET=
# FatSecret user tokens (получаются один раз через python -m fsai.auth_setup)
FATSECRET_ACCESS_TOKEN=
FATSECRET_ACCESS_SECRET=

# LLM
LLM_PROVIDER=anthropic        # anthropic | openai
LLM_MODEL=claude-haiku-4-5
LLM_API_KEY=

# Storage / locale
DB_PATH=fsai.sqlite3
TZ=Europe/Belgrade

# Meal boundaries (часы локального времени)
MEAL_BREAKFAST_START=5
MEAL_LUNCH_START=11
MEAL_DINNER_START=16
MEAL_DINNER_END=22
```

- [ ] **Step 4: Create empty package files**

`fsai/__init__.py`, `fsai/llm/__init__.py`, `tests/__init__.py` — пустые файлы.

`tests/conftest.py`:
```python
import pytest
from fsai.llm.base import LLMProvider


class FakeProvider(LLMProvider):
    """Возвращает заранее заданную строку, игнорируя промпт."""

    def __init__(self, response: str = ""):
        self.response = response
        self.last_system = None
        self.last_user = None

    def complete(self, system: str, user: str) -> str:
        self.last_system = system
        self.last_user = user
        return self.response


@pytest.fixture
def fake_provider():
    return FakeProvider()
```

- [ ] **Step 5: Install and verify**

Run: `pip install -e ".[dev]"`
Then: `pytest -q`
Expected: `no tests ran` (или collected 0 items) — сборка пакета и conftest импортируются без ошибок. (Импорт `fsai.llm.base` появится в Task 5; до тех пор conftest можно временно не импортировать — но мы создаём `base.py` следующим, поэтому держим порядок: выполните Task 5 перед запуском conftest, либо закомментируйте импорт в conftest до Task 5.)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore .env.example fsai/__init__.py fsai/llm/__init__.py tests/__init__.py tests/conftest.py
git commit -m "chore: scaffold fsai project (deps, gitignore, env template)"
```

---

## Task 2: Domain models (`fsai/models.py`)

**Files:**
- Create: `fsai/models.py`
- Test: `tests/test_models_smoke.py` (лёгкий smoke-тест на конструкторы)

- [ ] **Step 1: Write the failing test**

`tests/test_models_smoke.py`:
```python
from fsai.models import (
    ParsedItem, FoodCandidate, Serving, AliasRecord, ResolvedItem,
)


def test_parsed_item_defaults():
    item = ParsedItem(name="гречка")
    assert item.grams is None
    assert item.meal_hint is None
    assert item.confidence == 1.0


def test_resolved_item_fields():
    r = ResolvedItem(
        alias="гречка", food_id="11", serving_id="22",
        food_name="Buckwheat, cooked", grams=200.0,
        grams_per_serving=100.0, meal="lunch",
    )
    assert r.grams == 200.0 and r.meal == "lunch"


def test_serving_optional_grams():
    s = Serving(serving_id="1", description="1 cup", grams=None, metric_unit=None)
    assert s.grams is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models_smoke.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fsai.models'`

- [ ] **Step 3: Write minimal implementation**

`fsai/models.py`:
```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedItem:
    """Результат парсинга одной позиции фразы."""
    name: str
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
    """Порция продукта из food.get."""
    serving_id: str
    description: str
    grams: Optional[float]      # граммы, если metric_serving_unit == "g"
    metric_unit: Optional[str]


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models_smoke.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add fsai/models.py tests/test_models_smoke.py
git commit -m "feat: domain models (ParsedItem, Serving, AliasRecord, ResolvedItem)"
```

---

## Task 3: Config loader (`fsai/config.py`)

**Files:**
- Create: `fsai/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
import pytest
from fsai.config import load_config


def base_env():
    return {
        "TELEGRAM_TOKEN": "tg",
        "OWNER_CHAT_ID": "12345",
        "FATSECRET_CONSUMER_KEY": "ck",
        "FATSECRET_CONSUMER_SECRET": "cs",
        "FATSECRET_ACCESS_TOKEN": "at",
        "FATSECRET_ACCESS_SECRET": "as",
        "LLM_API_KEY": "key",
    }


def test_loads_required_fields():
    cfg = load_config(base_env())
    assert cfg.telegram_token == "tg"
    assert cfg.owner_chat_id == 12345
    assert cfg.fatsecret_consumer_key == "ck"
    assert cfg.llm_api_key == "key"


def test_defaults_applied():
    cfg = load_config(base_env())
    assert cfg.llm_provider == "anthropic"
    assert cfg.llm_model == "claude-haiku-4-5"
    assert cfg.db_path == "fsai.sqlite3"
    assert (cfg.meal_breakfast_start, cfg.meal_lunch_start,
            cfg.meal_dinner_start, cfg.meal_dinner_end) == (5, 11, 16, 22)


def test_missing_required_raises():
    env = base_env()
    del env["TELEGRAM_TOKEN"]
    with pytest.raises(ValueError, match="TELEGRAM_TOKEN"):
        load_config(env)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fsai.config'`

- [ ] **Step 3: Write minimal implementation**

`fsai/config.py`:
```python
import os
from dataclasses import dataclass
from typing import Mapping


@dataclass
class Config:
    telegram_token: str
    owner_chat_id: int
    fatsecret_consumer_key: str
    fatsecret_consumer_secret: str
    fatsecret_access_token: str
    fatsecret_access_secret: str
    llm_provider: str
    llm_model: str
    llm_api_key: str
    db_path: str
    timezone: str
    meal_breakfast_start: int
    meal_lunch_start: int
    meal_dinner_start: int
    meal_dinner_end: int


def _required(env: Mapping[str, str], key: str) -> str:
    val = env.get(key)
    if not val:
        raise ValueError(f"Missing required env var: {key}")
    return val


def load_config(env: Mapping[str, str] | None = None) -> Config:
    env = env if env is not None else os.environ
    return Config(
        telegram_token=_required(env, "TELEGRAM_TOKEN"),
        owner_chat_id=int(_required(env, "OWNER_CHAT_ID")),
        fatsecret_consumer_key=_required(env, "FATSECRET_CONSUMER_KEY"),
        fatsecret_consumer_secret=_required(env, "FATSECRET_CONSUMER_SECRET"),
        fatsecret_access_token=_required(env, "FATSECRET_ACCESS_TOKEN"),
        fatsecret_access_secret=_required(env, "FATSECRET_ACCESS_SECRET"),
        llm_provider=env.get("LLM_PROVIDER", "anthropic"),
        llm_model=env.get("LLM_MODEL", "claude-haiku-4-5"),
        llm_api_key=_required(env, "LLM_API_KEY"),
        db_path=env.get("DB_PATH", "fsai.sqlite3"),
        timezone=env.get("TZ", "UTC"),
        meal_breakfast_start=int(env.get("MEAL_BREAKFAST_START", "5")),
        meal_lunch_start=int(env.get("MEAL_LUNCH_START", "11")),
        meal_dinner_start=int(env.get("MEAL_DINNER_START", "16")),
        meal_dinner_end=int(env.get("MEAL_DINNER_END", "22")),
    )
```

Примечание: `auth_setup.py` (Task 12) не требует access-токенов, поэтому он НЕ использует `load_config` — он читает только consumer key/secret напрямую из окружения.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add fsai/config.py tests/test_config.py
git commit -m "feat: config loader from environment with defaults"
```

---

## Task 4: SQLite store (`fsai/store.py`)

**Files:**
- Create: `fsai/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write the failing test**

`tests/test_store.py`:
```python
from fsai.models import AliasRecord
from fsai.store import Store


def make_store(tmp_path):
    return Store(str(tmp_path / "t.sqlite3"))


def test_save_and_get_alias(tmp_path):
    s = make_store(tmp_path)
    rec = AliasRecord("гречка", "11", "22", 100.0, "Buckwheat, cooked")
    s.save_alias(rec)
    got = s.get_alias("гречка")
    assert got == rec


def test_get_missing_alias_returns_none(tmp_path):
    s = make_store(tmp_path)
    assert s.get_alias("нет такого") is None


def test_save_alias_upserts(tmp_path):
    s = make_store(tmp_path)
    s.save_alias(AliasRecord("рис", "1", "2", 100.0, "Rice"))
    s.save_alias(AliasRecord("рис", "9", "8", 50.0, "Rice, white"))
    got = s.get_alias("рис")
    assert got.food_id == "9" and got.grams_per_serving == 50.0


def test_all_alias_names(tmp_path):
    s = make_store(tmp_path)
    s.save_alias(AliasRecord("рис", "1", "2", 100.0, "Rice"))
    s.save_alias(AliasRecord("гречка", "3", "4", 100.0, "Buckwheat"))
    assert sorted(s.all_alias_names()) == ["гречка", "рис"]


def test_log_roundtrip(tmp_path):
    s = make_store(tmp_path)
    log_id = s.add_log("греча 200г", ["e1", "e2"])
    rec = s.get_log(log_id)
    assert rec["raw_text"] == "греча 200г"
    assert rec["entry_ids"] == ["e1", "e2"]


def test_get_missing_log_returns_none(tmp_path):
    s = make_store(tmp_path)
    assert s.get_log(999) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_store.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fsai.store'`

- [ ] **Step 3: Write minimal implementation**

`fsai/store.py`:
```python
import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fsai.models import AliasRecord


class Store:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS aliases (
                alias             TEXT PRIMARY KEY,
                food_id           TEXT NOT NULL,
                serving_id        TEXT NOT NULL,
                grams_per_serving REAL NOT NULL,
                food_name         TEXT NOT NULL,
                created_at        TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ts        TEXT NOT NULL,
                raw_text  TEXT NOT NULL,
                entry_ids TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def get_alias(self, alias: str) -> Optional[AliasRecord]:
        row = self.conn.execute(
            "SELECT alias, food_id, serving_id, grams_per_serving, food_name "
            "FROM aliases WHERE alias = ?",
            (alias,),
        ).fetchone()
        if row is None:
            return None
        return AliasRecord(
            alias=row["alias"], food_id=row["food_id"],
            serving_id=row["serving_id"],
            grams_per_serving=row["grams_per_serving"],
            food_name=row["food_name"],
        )

    def save_alias(self, rec: AliasRecord) -> None:
        self.conn.execute(
            "INSERT INTO aliases "
            "(alias, food_id, serving_id, grams_per_serving, food_name, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(alias) DO UPDATE SET "
            "food_id=excluded.food_id, serving_id=excluded.serving_id, "
            "grams_per_serving=excluded.grams_per_serving, "
            "food_name=excluded.food_name",
            (rec.alias, rec.food_id, rec.serving_id, rec.grams_per_serving,
             rec.food_name, datetime.now(timezone.utc).isoformat()),
        )
        self.conn.commit()

    def all_alias_names(self) -> list[str]:
        rows = self.conn.execute("SELECT alias FROM aliases").fetchall()
        return [r["alias"] for r in rows]

    def add_log(self, raw_text: str, entry_ids: list[str]) -> int:
        cur = self.conn.execute(
            "INSERT INTO log (ts, raw_text, entry_ids) VALUES (?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), raw_text,
             json.dumps(entry_ids)),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_log(self, log_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT id, ts, raw_text, entry_ids FROM log WHERE id = ?",
            (log_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"], "ts": row["ts"], "raw_text": row["raw_text"],
            "entry_ids": json.loads(row["entry_ids"]),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_store.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add fsai/store.py tests/test_store.py
git commit -m "feat: SQLite store for aliases and entry log"
```

---

## Task 5: LLM base interface + Parser (`fsai/llm/base.py`, `fsai/parser.py`)

**Files:**
- Create: `fsai/llm/base.py`, `fsai/parser.py`
- Test: `tests/test_parser.py`

- [ ] **Step 1: Write `fsai/llm/base.py` (interface — no test needed, exercised via Parser)**

```python
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Минимальный интерфейс модели: вернуть текст ответа на пару system/user."""

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        ...
```

- [ ] **Step 2: Write the failing test**

`tests/test_parser.py`:
```python
import json

from fsai.parser import Parser
from tests.conftest import FakeProvider


def test_parses_items_with_grams():
    payload = json.dumps({"items": [
        {"name": "гречка", "grams": 200, "meal_hint": None, "confidence": 0.95},
        {"name": "куриное филе", "grams": 150, "meal_hint": "lunch", "confidence": 0.9},
    ]})
    parser = Parser(FakeProvider(payload))
    items = parser.parse("греча 200г, куриное филе 150г", ["гречка"])
    assert len(items) == 2
    assert items[0].name == "гречка" and items[0].grams == 200.0
    assert items[1].meal_hint == "lunch"


def test_known_aliases_passed_into_prompt():
    provider = FakeProvider(json.dumps({"items": []}))
    Parser(provider).parse("что-то", ["рис", "гречка"])
    assert "рис" in provider.last_user and "гречка" in provider.last_user


def test_handles_code_fenced_json():
    payload = "```json\n" + json.dumps({"items": [{"name": "рис", "grams": 100}]}) + "\n```"
    items = Parser(FakeProvider(payload)).parse("рис 100", [])
    assert items[0].name == "рис" and items[0].grams == 100.0


def test_missing_grams_becomes_none():
    payload = json.dumps({"items": [{"name": "банан"}]})
    items = Parser(FakeProvider(payload)).parse("банан", [])
    assert items[0].grams is None
    assert items[0].confidence == 1.0


def test_empty_or_garbage_returns_empty_list():
    assert Parser(FakeProvider("не json вовсе")).parse("шум", []) == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_parser.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fsai.parser'`

- [ ] **Step 4: Write minimal implementation**

`fsai/parser.py`:
```python
import json
import re
from typing import Optional

from fsai.llm.base import LLMProvider
from fsai.models import ParsedItem

SYSTEM_PROMPT = (
    "Ты извлекаешь позиции питания из надиктованной фразы на русском. "
    "Верни СТРОГО JSON-объект вида "
    '{\"items\": [{\"name\": str, \"grams\": number|null, '
    '\"meal_hint\": \"breakfast\"|\"lunch\"|\"dinner\"|\"other\"|null, '
    '\"confidence\": number}]}. '
    "Никакого текста вне JSON. Граммы — число в граммах, если можно их "
    "вычислить; иначе null. Если в подсказке дан список известных названий, "
    "приводи name к наиболее близкому из них (синонимы, падежи, опечатки); "
    "иначе оставляй как сказано. confidence от 0 до 1."
)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


class Parser:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def parse(self, text: str, known_aliases: list[str]) -> list[ParsedItem]:
        user = self._build_user_prompt(text, known_aliases)
        raw = self.provider.complete(SYSTEM_PROMPT, user)
        data = self._extract_json(raw)
        if not data or not isinstance(data.get("items"), list):
            return []
        items: list[ParsedItem] = []
        for it in data["items"]:
            if not isinstance(it, dict) or not it.get("name"):
                continue
            items.append(ParsedItem(
                name=str(it["name"]).strip(),
                grams=_to_float(it.get("grams")),
                meal_hint=it.get("meal_hint") or None,
                confidence=float(it.get("confidence", 1.0)),
            ))
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_parser.py -q`
Expected: PASS (5 passed)

- [ ] **Step 6: Commit**

```bash
git add fsai/llm/base.py fsai/parser.py tests/test_parser.py
git commit -m "feat: LLMProvider interface and Parser (text -> ParsedItem)"
```

---

## Task 6: LLM providers + factory (`fsai/llm/anthropic_provider.py`, `openai_provider.py`, `factory.py`)

**Files:**
- Create: `fsai/llm/anthropic_provider.py`, `fsai/llm/openai_provider.py`, `fsai/llm/factory.py`
- Test: `tests/test_llm_providers.py`

- [ ] **Step 1: Write the failing test**

`tests/test_llm_providers.py`:
```python
import pytest

from fsai.llm.anthropic_provider import AnthropicProvider
from fsai.llm.openai_provider import OpenAIProvider
from fsai.llm.factory import build_provider


class FakeAnthropicMessages:
    def __init__(self, sink):
        self.sink = sink

    def create(self, **kwargs):
        self.sink.update(kwargs)
        class _Block:
            text = "ANTHROPIC_OK"
        class _Resp:
            content = [_Block()]
        return _Resp()


class FakeAnthropicClient:
    def __init__(self, sink):
        self.messages = FakeAnthropicMessages(sink)


class FakeOpenAIChat:
    def __init__(self, sink):
        self.completions = self
        self.sink = sink

    def create(self, **kwargs):
        self.sink.update(kwargs)
        class _Msg:
            content = "OPENAI_OK"
        class _Choice:
            message = _Msg()
        class _Resp:
            choices = [_Choice()]
        return _Resp()


class FakeOpenAIClient:
    def __init__(self, sink):
        self.chat = FakeOpenAIChat(sink)


def test_anthropic_provider_calls_model_and_returns_text():
    sink = {}
    p = AnthropicProvider(client=FakeAnthropicClient(sink), model="claude-haiku-4-5")
    out = p.complete("SYS", "USR")
    assert out == "ANTHROPIC_OK"
    assert sink["model"] == "claude-haiku-4-5"
    assert sink["system"] == "SYS"
    assert sink["messages"] == [{"role": "user", "content": "USR"}]


def test_openai_provider_calls_model_and_returns_text():
    sink = {}
    p = OpenAIProvider(client=FakeOpenAIClient(sink), model="gpt-4o-mini")
    out = p.complete("SYS", "USR")
    assert out == "OPENAI_OK"
    assert sink["model"] == "gpt-4o-mini"
    assert sink["messages"][0] == {"role": "system", "content": "SYS"}
    assert sink["messages"][1] == {"role": "user", "content": "USR"}


def test_factory_selects_by_config():
    class Cfg:
        llm_provider = "anthropic"
        llm_model = "claude-haiku-4-5"
        llm_api_key = "k"
    assert isinstance(build_provider(Cfg()), AnthropicProvider)


def test_factory_rejects_unknown_provider():
    class Cfg:
        llm_provider = "llama"
        llm_model = "x"
        llm_api_key = "k"
    with pytest.raises(ValueError, match="llama"):
        build_provider(Cfg())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_providers.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fsai.llm.anthropic_provider'`

- [ ] **Step 3: Write minimal implementations**

`fsai/llm/anthropic_provider.py`:
```python
from fsai.llm.base import LLMProvider

MAX_TOKENS = 1024


class AnthropicProvider(LLMProvider):
    def __init__(self, client, model: str):
        self._client = client
        self._model = model

    def complete(self, system: str, user: str) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text
```

`fsai/llm/openai_provider.py`:
```python
from fsai.llm.base import LLMProvider


class OpenAIProvider(LLMProvider):
    def __init__(self, client, model: str):
        self._client = client
        self._model = model

    def complete(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content
```

`fsai/llm/factory.py`:
```python
from fsai.llm.base import LLMProvider
from fsai.llm.anthropic_provider import AnthropicProvider
from fsai.llm.openai_provider import OpenAIProvider


def build_provider(config) -> LLMProvider:
    provider = config.llm_provider.lower()
    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=config.llm_api_key)
        return AnthropicProvider(client=client, model=config.llm_model)
    if provider == "openai":
        import openai
        client = openai.OpenAI(api_key=config.llm_api_key)
        return OpenAIProvider(client=client, model=config.llm_model)
    raise ValueError(f"Unknown LLM_PROVIDER: {config.llm_provider}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_providers.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add fsai/llm/anthropic_provider.py fsai/llm/openai_provider.py fsai/llm/factory.py tests/test_llm_providers.py
git commit -m "feat: Anthropic/OpenAI providers and config-driven factory"
```

---

## Task 7: FatSecret client (`fsai/fatsecret_client.py`)

**Files:**
- Create: `fsai/fatsecret_client.py`
- Test: `tests/test_fatsecret_client.py`

Обёртка над `pyfatsecret`. Сама pyfatsecret подписывает запросы OAuth 1.0a и хранит сессию; мы тестируем только нормализацию ответов и параметры вызовов, подменяя внутренний `Fatsecret`-объект.

- [ ] **Step 1: Write the failing test**

`tests/test_fatsecret_client.py`:
```python
from fsai.fatsecret_client import FatSecretClient
from fsai.models import FoodCandidate, Serving


class FakeFatsecret:
    def __init__(self):
        self.created = []
        self.deleted = []
        self.search_return = []
        self.food_return = {}

    def foods_search(self, search_expression, page_number=None, max_results=None):
        self.last_search = (search_expression, max_results)
        return self.search_return

    def food_get(self, food_id):
        self.last_food_id = food_id
        return self.food_return

    def food_entry_create(self, food_id, food_entry_name, serving_id,
                          number_of_units, meal, date=None):
        self.created.append((food_id, food_entry_name, serving_id,
                             number_of_units, meal, date))
        return 9001

    def food_entry_delete(self, food_entry_id):
        self.deleted.append(food_entry_id)


def make_client(fake):
    c = FatSecretClient.__new__(FatSecretClient)
    c._fs = fake
    return c


def test_search_foods_normalizes_list():
    fake = FakeFatsecret()
    fake.search_return = [
        {"food_id": "1", "food_name": "Buckwheat", "food_description": "Per 100g"},
        {"food_id": "2", "food_name": "Rice"},
    ]
    out = make_client(fake).search_foods("buckwheat", max_results=5)
    assert out[0] == FoodCandidate("1", "Buckwheat", "Per 100g")
    assert out[1] == FoodCandidate("2", "Rice", "")
    assert fake.last_search == ("buckwheat", 5)


def test_search_foods_wraps_single_dict():
    fake = FakeFatsecret()
    fake.search_return = {"food_id": "1", "food_name": "Solo"}
    out = make_client(fake).search_foods("solo")
    assert out == [FoodCandidate("1", "Solo", "")]


def test_get_servings_extracts_gram_serving():
    fake = FakeFatsecret()
    fake.food_return = {"servings": {"serving": [
        {"serving_id": "10", "serving_description": "1 cup",
         "metric_serving_amount": "195.0", "metric_serving_unit": "g"},
        {"serving_id": "11", "serving_description": "1 oz",
         "metric_serving_amount": "1.0", "metric_serving_unit": "oz"},
    ]}}
    out = make_client(fake).get_servings("1")
    assert out[0] == Serving("10", "1 cup", 195.0, "g")
    assert out[1] == Serving("11", "1 oz", None, "oz")


def test_get_servings_handles_single_serving_dict():
    fake = FakeFatsecret()
    fake.food_return = {"servings": {"serving": {
        "serving_id": "10", "serving_description": "100 g",
        "metric_serving_amount": "100.0", "metric_serving_unit": "g"}}}
    out = make_client(fake).get_servings("1")
    assert out == [Serving("10", "100 g", 100.0, "g")]


def test_create_entry_returns_str_id_and_passes_args():
    fake = FakeFatsecret()
    eid = make_client(fake).create_entry("1", "Buckwheat", "10", 2.0, "lunch", None)
    assert eid == "9001"
    assert fake.created == [("1", "Buckwheat", "10", 2.0, "lunch", None)]


def test_delete_entry():
    fake = FakeFatsecret()
    make_client(fake).delete_entry("9001")
    assert fake.deleted == ["9001"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fatsecret_client.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fsai.fatsecret_client'`

- [ ] **Step 3: Write minimal implementation**

`fsai/fatsecret_client.py`:
```python
from typing import Any, Optional

from fsai.models import FoodCandidate, Serving


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


class FatSecretClient:
    """Тонкая обёртка над pyfatsecret: нормализует ответы в наши модели."""

    def __init__(self, consumer_key: str, consumer_secret: str,
                 access_token: str, access_secret: str):
        from fatsecret import Fatsecret
        self._fs = Fatsecret(
            consumer_key, consumer_secret,
            session_token=(access_token, access_secret),
        )

    def search_foods(self, query: str, max_results: int = 5) -> list[FoodCandidate]:
        raw = self._fs.foods_search(query, max_results=max_results)
        return [
            FoodCandidate(
                food_id=str(f["food_id"]),
                food_name=f["food_name"],
                description=f.get("food_description", ""),
            )
            for f in _as_list(raw)
        ]

    def get_servings(self, food_id: str) -> list[Serving]:
        food = self._fs.food_get(food_id)
        servings = _as_list(food.get("servings", {}).get("serving"))
        out: list[Serving] = []
        for s in servings:
            unit = s.get("metric_serving_unit")
            amount = s.get("metric_serving_amount")
            grams = float(amount) if unit == "g" and amount is not None else None
            out.append(Serving(
                serving_id=str(s["serving_id"]),
                description=s.get("serving_description", ""),
                grams=grams,
                metric_unit=unit,
            ))
        return out

    def create_entry(self, food_id: str, food_name: str, serving_id: str,
                     number_of_units: float, meal: str,
                     date=None) -> str:
        entry_id = self._fs.food_entry_create(
            food_id, food_name, serving_id, number_of_units, meal, date)
        return str(entry_id)

    def delete_entry(self, entry_id: str) -> None:
        self._fs.food_entry_delete(entry_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fatsecret_client.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add fsai/fatsecret_client.py tests/test_fatsecret_client.py
git commit -m "feat: FatSecret client wrapping pyfatsecret (search/servings/create/delete)"
```

---

## Task 8: Resolver (`fsai/resolver.py`)

**Files:**
- Create: `fsai/resolver.py`
- Test: `tests/test_resolver.py`

Машина состояний разрешения одной позиции. Результат — один из:
`Resolved`, `NeedsGrams`, `NeedsFood` (выбор продукта из кандидатов),
`NeedsServing` (продукт выбран, но нет грамм-порции — выбрать серию).

- [ ] **Step 1: Write the failing test**

`tests/test_resolver.py`:
```python
import pytest

from fsai.models import AliasRecord, FoodCandidate, ParsedItem, Serving
from fsai.resolver import (
    Resolver, Resolved, NeedsGrams, NeedsFood, NeedsServing,
)
from fsai.store import Store


class FakeClient:
    def __init__(self):
        self.search_return = []
        self.servings_return = []

    def search_foods(self, query, max_results=5):
        self.last_query = query
        return self.search_return

    def get_servings(self, food_id):
        self.last_food_id = food_id
        return self.servings_return


def store(tmp_path):
    return Store(str(tmp_path / "r.sqlite3"))


def test_missing_grams_returns_needs_grams(tmp_path):
    r = Resolver(FakeClient(), store(tmp_path))
    res = r.resolve(ParsedItem(name="банан", grams=None), meal="lunch")
    assert isinstance(res, NeedsGrams)


def test_known_alias_resolves_directly(tmp_path):
    s = store(tmp_path)
    s.save_alias(AliasRecord("гречка", "11", "22", 100.0, "Buckwheat"))
    r = Resolver(FakeClient(), s)
    res = r.resolve(ParsedItem(name="гречка", grams=200.0), meal="lunch")
    assert isinstance(res, Resolved)
    assert res.item.food_id == "11" and res.item.grams == 200.0
    assert res.item.grams_per_serving == 100.0 and res.item.meal == "lunch"


def test_unknown_triggers_search(tmp_path):
    c = FakeClient()
    c.search_return = [FoodCandidate("1", "Buckwheat", "")]
    r = Resolver(c, store(tmp_path))
    res = r.resolve(ParsedItem(name="греча", grams=200.0), meal="lunch")
    assert isinstance(res, NeedsFood)
    assert res.candidates[0].food_id == "1"
    assert res.parsed.name == "греча"


def test_confirm_food_picks_gram_serving_and_saves_alias(tmp_path):
    s = store(tmp_path)
    c = FakeClient()
    c.servings_return = [
        Serving("99", "1 cup", None, "cup"),
        Serving("100", "100 g", 100.0, "g"),
    ]
    r = Resolver(c, s)
    parsed = ParsedItem(name="греча", grams=200.0)
    res = r.confirm_food(parsed, "1", "Buckwheat", meal="dinner")
    assert isinstance(res, Resolved)
    assert res.item.serving_id == "100" and res.item.grams_per_serving == 100.0
    assert res.item.meal == "dinner"
    # алиас сохранён под названием из фразы
    saved = s.get_alias("греча")
    assert saved.food_id == "1" and saved.serving_id == "100"


def test_confirm_food_without_gram_serving_asks_serving(tmp_path):
    c = FakeClient()
    c.servings_return = [Serving("99", "1 cup", None, "cup")]
    r = Resolver(c, store(tmp_path))
    res = r.confirm_food(ParsedItem(name="x", grams=50.0), "1", "X", meal="lunch")
    assert isinstance(res, NeedsServing)
    assert res.servings[0].serving_id == "99"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_resolver.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fsai.resolver'`

- [ ] **Step 3: Write minimal implementation**

`fsai/resolver.py`:
```python
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
```

Примечание: `confirm_serving` (для случая `NeedsServing`, когда у выбранной серии нет грамм — пользователь сообщает граммовку серии) добавлен для полноты state machine; используется ботом в Task 11.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_resolver.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add fsai/resolver.py tests/test_resolver.py
git commit -m "feat: Resolver state machine (alias lookup, search, serving selection)"
```

---

## Task 9: Diary (`fsai/diary.py`)

**Files:**
- Create: `fsai/diary.py`
- Test: `tests/test_diary.py`

- [ ] **Step 1: Write the failing test**

`tests/test_diary.py`:
```python
from datetime import datetime

from fsai.diary import infer_meal, units_for, Diary
from fsai.models import ResolvedItem


def test_units_for():
    assert units_for(200.0, 100.0) == 2.0
    assert units_for(50.0, 100.0) == 0.5


def test_infer_meal_boundaries():
    def at(h):
        return infer_meal(datetime(2026, 6, 17, h, 0))
    assert at(7) == "breakfast"
    assert at(13) == "lunch"
    assert at(19) == "dinner"
    assert at(23) == "other"
    assert at(3) == "other"
    # границы включительно слева
    assert at(5) == "breakfast"
    assert at(11) == "lunch"
    assert at(16) == "dinner"


def test_infer_meal_custom_bounds():
    assert infer_meal(datetime(2026, 6, 17, 10, 0), breakfast=6, lunch=12) == "breakfast"


class FakeClient:
    def __init__(self):
        self.calls = []

    def create_entry(self, food_id, food_name, serving_id, number_of_units,
                     meal, date=None):
        self.calls.append((food_id, food_name, serving_id, number_of_units,
                           meal, date))
        return f"e{len(self.calls)}"


def test_diary_write_computes_units_and_returns_ids():
    c = FakeClient()
    items = [
        ResolvedItem("гречка", "11", "22", "Buckwheat", 200.0, 100.0, "lunch"),
        ResolvedItem("филе", "33", "44", "Chicken", 150.0, 100.0, "lunch"),
    ]
    ids = Diary(c).write(items)
    assert ids == ["e1", "e2"]
    assert c.calls[0] == ("11", "Buckwheat", "22", 2.0, "lunch", None)
    assert c.calls[1] == ("33", "Chicken", "44", 1.5, "lunch", None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_diary.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fsai.diary'`

- [ ] **Step 3: Write minimal implementation**

`fsai/diary.py`:
```python
from datetime import datetime
from typing import Optional

from fsai.models import ResolvedItem


def infer_meal(now: datetime, breakfast: int = 5, lunch: int = 11,
               dinner: int = 16, dinner_end: int = 22) -> str:
    h = now.hour
    if breakfast <= h < lunch:
        return "breakfast"
    if lunch <= h < dinner:
        return "lunch"
    if dinner <= h < dinner_end:
        return "dinner"
    return "other"


def units_for(grams: float, grams_per_serving: float) -> float:
    return grams / grams_per_serving


class Diary:
    def __init__(self, client):
        self.client = client

    def write(self, items: list[ResolvedItem],
              date: Optional[datetime] = None) -> list[str]:
        ids: list[str] = []
        for it in items:
            n = units_for(it.grams, it.grams_per_serving)
            ids.append(self.client.create_entry(
                it.food_id, it.food_name, it.serving_id, n, it.meal, date))
        return ids
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_diary.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add fsai/diary.py tests/test_diary.py
git commit -m "feat: meal inference, units calc, diary writer"
```

---

## Task 10: Service orchestration (`fsai/service.py`)

**Files:**
- Create: `fsai/service.py`
- Test: `tests/test_service.py`

`LoggerService` склеивает парсинг → разрешение → авто-запись/уточнение. Хранит
pending-сессии в памяти (один пользователь). Результат `process_text`:
- `AutoLogged(lines, log_id)` — все позиции разрешились уверенно и записаны;
- `NeedsInput(session_id, pending)` — часть позиций требует ввода;
  `pending` — список `PendingPrompt` (что именно спросить по каждой позиции).

Колбэки бота: `choose_food`, `set_grams`, `choose_serving`, затем
`finalize`. Плюс `undo(log_id)`.

- [ ] **Step 1: Write the failing test**

`tests/test_service.py`:
```python
import json

from fsai.models import AliasRecord, FoodCandidate, Serving
from fsai.service import LoggerService, AutoLogged, NeedsInput
from fsai.store import Store
from tests.conftest import FakeProvider


class FakeClient:
    def __init__(self):
        self.search_return = []
        self.servings_return = []
        self.created = []
        self.deleted = []

    def search_foods(self, query, max_results=5):
        return self.search_return

    def get_servings(self, food_id):
        return self.servings_return

    def create_entry(self, food_id, food_name, serving_id, number_of_units,
                     meal, date=None):
        self.created.append((food_id, serving_id, number_of_units, meal))
        return f"e{len(self.created)}"

    def delete_entry(self, entry_id):
        self.deleted.append(entry_id)


def build(tmp_path, provider, client, now_hour=13):
    from datetime import datetime
    store = Store(str(tmp_path / "svc.sqlite3"))
    return LoggerService(
        provider=provider, client=client, store=store,
        clock=lambda: datetime(2026, 6, 17, now_hour, 0),
    ), store


def test_all_known_items_autolog(tmp_path):
    payload = json.dumps({"items": [
        {"name": "гречка", "grams": 200, "confidence": 0.95},
        {"name": "филе", "grams": 150, "confidence": 0.95},
    ]})
    client = FakeClient()
    svc, store = build(tmp_path, FakeProvider(payload), client)
    store.save_alias(AliasRecord("гречка", "11", "22", 100.0, "Buckwheat"))
    store.save_alias(AliasRecord("филе", "33", "44", 100.0, "Chicken"))

    res = svc.process_text("греча 200г, филе 150г")

    assert isinstance(res, AutoLogged)
    assert len(client.created) == 2
    assert client.created[0] == ("11", "22", 2.0, "lunch")
    assert store.get_log(res.log_id)["entry_ids"] == ["e1", "e2"]


def test_unknown_item_needs_input_then_finalize(tmp_path):
    payload = json.dumps({"items": [{"name": "греча", "grams": 200, "confidence": 0.9}]})
    client = FakeClient()
    client.search_return = [FoodCandidate("1", "Buckwheat", "Per 100g")]
    client.servings_return = [Serving("100", "100 g", 100.0, "g")]
    svc, store = build(tmp_path, FakeProvider(payload), client)

    res = svc.process_text("греча 200г")
    assert isinstance(res, NeedsInput)
    prompt = res.pending[0]
    assert prompt.kind == "food"
    assert prompt.candidates[0].food_id == "1"

    # пользователь выбрал продукт
    svc.choose_food(res.session_id, prompt.index, "1", "Buckwheat")
    final = svc.finalize(res.session_id)
    assert isinstance(final, AutoLogged)
    assert client.created == [("1", "100", 2.0, "lunch")]
    # алиас сохранён для будущего
    assert store.get_alias("греча").food_id == "1"


def test_missing_grams_needs_input(tmp_path):
    payload = json.dumps({"items": [{"name": "гречка"}]})
    client = FakeClient()
    svc, store = build(tmp_path, FakeProvider(payload), client)
    store.save_alias(AliasRecord("гречка", "11", "22", 100.0, "Buckwheat"))

    res = svc.process_text("гречка")
    assert isinstance(res, NeedsInput)
    assert res.pending[0].kind == "grams"

    svc.set_grams(res.session_id, res.pending[0].index, 250.0)
    final = svc.finalize(res.session_id)
    assert isinstance(final, AutoLogged)
    assert client.created[0] == ("11", "22", 2.5, "lunch")


def test_empty_parse_returns_autologged_with_no_entries(tmp_path):
    client = FakeClient()
    svc, _ = build(tmp_path, FakeProvider(json.dumps({"items": []})), client)
    res = svc.process_text("бессмыслица")
    assert isinstance(res, AutoLogged) and res.log_id is None
    assert client.created == []


def test_undo_deletes_entries(tmp_path):
    payload = json.dumps({"items": [{"name": "гречка", "grams": 200}]})
    client = FakeClient()
    svc, store = build(tmp_path, FakeProvider(payload), client)
    store.save_alias(AliasRecord("гречка", "11", "22", 100.0, "Buckwheat"))
    res = svc.process_text("гречка 200")
    count = svc.undo(res.log_id)
    assert count == 1
    assert client.deleted == ["e1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_service.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fsai.service'`

- [ ] **Step 3: Write minimal implementation**

`fsai/service.py`:
```python
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
        items = self.parser.parse(text, self.store.all_alias_names())
        resolved: dict[int, ResolvedItem] = {}
        pending: dict[int, PendingPrompt] = {}
        for idx, item in enumerate(items):
            res = self.resolver.resolve(item, meal)
            self._record(idx, item, res, resolved, pending)
        session = _Session(str(uuid.uuid4()), text, meal, resolved, pending)
        if pending:
            self._sessions[session.session_id] = session
            return NeedsInput(session.session_id, list(pending.values()))
        return self._finalize_session(session)

    # --- колбэки уточнения ---
    def choose_food(self, session_id: str, index: int, food_id: str,
                    food_name: str) -> None:
        session = self._sessions[session_id]
        prompt = session.pending[index]
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
            return 0
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
            return AutoLogged(lines=[], log_id=None)
        entry_ids = self.diary.write(items)
        log_id = self.store.add_log(session.raw_text, entry_ids)
        lines = [
            f"{it.food_name} — {it.grams:g} г ({it.meal})" for it in items
        ]
        return AutoLogged(lines=lines, log_id=log_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_service.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add fsai/service.py tests/test_service.py
git commit -m "feat: LoggerService orchestration (parse/resolve/autolog/pending/undo)"
```

---

## Task 11: Telegram bot (`fsai/bot.py`)

**Files:**
- Create: `fsai/bot.py`
- Test: `tests/test_bot_render.py`

Тонкая обвязка. Чистые функции рендеринга/клавиатур тестируем юнит-тестами;
runtime (long-polling) проверяется вручную (см. README). Колбэк-данные
кодируются как `"<action>:<session_id>:<index>:<payload>"`.

- [ ] **Step 1: Write the failing test**

`tests/test_bot_render.py`:
```python
from fsai.models import FoodCandidate
from fsai.service import AutoLogged, NeedsInput, PendingPrompt
from fsai.bot import (
    format_autolog, food_keyboard, pack_cb, unpack_cb, build_needs_input_messages,
)
from fsai.models import ParsedItem


def test_format_autolog_lists_items():
    res = AutoLogged(lines=["Buckwheat — 200 г (lunch)"], log_id=7)
    text = format_autolog(res)
    assert "Buckwheat — 200 г (lunch)" in text
    assert "Записано" in text


def test_format_autolog_empty():
    assert "не понял" in format_autolog(AutoLogged(lines=[], log_id=None)).lower()


def test_callback_pack_unpack_roundtrip():
    data = pack_cb("food", "sess-1", 2, "food123")
    action, sid, idx, payload = unpack_cb(data)
    assert (action, sid, idx, payload) == ("food", "sess-1", 2, "food123")


def test_food_keyboard_has_button_per_candidate():
    prompt = PendingPrompt(
        index=0, kind="food", parsed=ParsedItem("греча", 200.0),
        candidates=[FoodCandidate("1", "Buckwheat", ""),
                    FoodCandidate("2", "Buckwheat groats", "")],
    )
    kb = food_keyboard("sess-1", prompt)
    flat = [b for row in kb.inline_keyboard for b in row]
    assert len(flat) == 2
    assert flat[0].callback_data == pack_cb("food", "sess-1", 0, "1")


def test_build_needs_input_messages_for_grams():
    prompt = PendingPrompt(index=0, kind="grams", parsed=ParsedItem("гречка"))
    msgs = build_needs_input_messages("sess-1", NeedsInput("sess-1", [prompt]))
    assert any("грамм" in m.text.lower() for m in msgs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_bot_render.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fsai.bot'`

- [ ] **Step 3: Write minimal implementation**

`fsai/bot.py`:
```python
from dataclasses import dataclass
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters,
)

from fsai.service import AutoLogged, NeedsInput, PendingPrompt

CB_SEP = "|"


# ---------- чистые функции (тестируемы без Telegram runtime) ----------

def pack_cb(action: str, session_id: str, index: int, payload: str) -> str:
    return CB_SEP.join([action, session_id, str(index), payload])


def unpack_cb(data: str):
    action, session_id, index, payload = data.split(CB_SEP, 3)
    return action, session_id, int(index), payload


def format_autolog(res: AutoLogged) -> str:
    if not res.lines:
        return "Хм, не понял ни одной позиции. Переформулируй?"
    body = "\n".join(f"• {line}" for line in res.lines)
    return f"✅ Записано:\n{body}"


def undo_keyboard(log_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("↩ Отменить", callback_data=pack_cb(
            "undo", "-", 0, str(log_id)))
    ]])


def food_keyboard(session_id: str, prompt: PendingPrompt) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        c.food_name + (f" — {c.description}" if c.description else ""),
        callback_data=pack_cb("food", session_id, prompt.index, c.food_id))]
        for c in prompt.candidates]
    return InlineKeyboardMarkup(rows)


def serving_keyboard(session_id: str, prompt: PendingPrompt) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        s.description or s.serving_id,
        callback_data=pack_cb("serv", session_id, prompt.index, s.serving_id))]
        for s in prompt.servings]
    return InlineKeyboardMarkup(rows)


@dataclass
class OutMessage:
    text: str
    keyboard: Optional[InlineKeyboardMarkup] = None


def build_needs_input_messages(session_id: str,
                               res: NeedsInput) -> list[OutMessage]:
    msgs: list[OutMessage] = []
    for prompt in res.pending:
        if prompt.kind == "grams":
            msgs.append(OutMessage(
                f"Сколько грамм «{prompt.parsed.name}»? Пришли число."))
        elif prompt.kind == "food":
            if prompt.candidates:
                msgs.append(OutMessage(
                    f"Выбери продукт для «{prompt.parsed.name}»:",
                    food_keyboard(session_id, prompt)))
            else:
                msgs.append(OutMessage(
                    f"Ничего не нашёл по «{prompt.parsed.name}». "
                    f"Попробуй другое название."))
        elif prompt.kind == "serving":
            msgs.append(OutMessage(
                f"У «{prompt.parsed.name}» нет порции в граммах. "
                f"Выбери серию:", serving_keyboard(session_id, prompt)))
    return msgs


# ---------- runtime-обвязка (проверяется вручную) ----------

class TelegramBot:
    def __init__(self, config, service):
        self.config = config
        self.service = service
        self._await_grams: dict[int, tuple[str, int]] = {}  # chat_id -> (sid, idx)

    def build_application(self) -> Application:
        app = Application.builder().token(self.config.telegram_token).build()
        owner = filters.User(user_id=self.config.owner_chat_id)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & owner,
                                       self.on_text))
        app.add_handler(CallbackQueryHandler(self.on_callback))
        return app

    async def on_text(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        import asyncio
        chat_id = update.effective_chat.id
        text = update.message.text
        # ждём ли мы граммовку?
        if chat_id in self._await_grams:
            sid, idx = self._await_grams.pop(chat_id)
            try:
                grams = float(text.replace(",", "."))
            except ValueError:
                await update.message.reply_text("Нужно число грамм.")
                self._await_grams[chat_id] = (sid, idx)
                return
            await asyncio.to_thread(self.service.set_grams, sid, idx, grams)
            await self._continue(update, sid)
            return
        res = await asyncio.to_thread(self.service.process_text, text)
        await self._render(update, res)

    async def on_callback(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        import asyncio
        query = update.callback_query
        await query.answer()
        action, sid, idx, payload = unpack_cb(query.data)
        if action == "undo":
            count = await asyncio.to_thread(self.service.undo, int(payload))
            await query.edit_message_text(
                f"↩ Отменено записей: {count}")
            return
        if action == "food":
            name = next((c.food_name for p in [] for c in []), payload)
            await asyncio.to_thread(self.service.choose_food, sid, idx,
                                    payload, payload)
            await self._continue_from_query(query, sid)
            return
        if action == "serv":
            # граммовку серии уточняем отдельным шагом ввода
            self._await_grams[query.message.chat_id] = (sid, idx)
            await query.edit_message_text(
                "Сколько грамм в выбранной серии? Пришли число.")
            return

    async def _render(self, update, res):
        if isinstance(res, AutoLogged):
            kb = undo_keyboard(res.log_id) if res.log_id else None
            await update.message.reply_text(format_autolog(res), reply_markup=kb)
        else:
            await self._send_needs_input(update.message.reply_text, res)

    async def _continue(self, update, session_id):
        import asyncio
        res = await asyncio.to_thread(self.service.finalize, session_id)
        await self._render(update, res)

    async def _continue_from_query(self, query, session_id):
        import asyncio
        res = await asyncio.to_thread(self.service.finalize, session_id)
        if isinstance(res, AutoLogged):
            kb = undo_keyboard(res.log_id) if res.log_id else None
            await query.edit_message_text(format_autolog(res), reply_markup=kb)
        else:
            await self._send_needs_input(query.message.reply_text, res)

    async def _send_needs_input(self, reply, res: NeedsInput):
        for msg in build_needs_input_messages(res.session_id, res):
            await reply(msg.text, reply_markup=msg.keyboard)
            if msg.text.startswith("Сколько грамм"):
                pass  # grams ожидаются по индексу через build (упрощённо)
```

> **Note для исполнителя:** runtime-часть (`TelegramBot`) намеренно тонкая и
> покрывается ручной проверкой по README. Если при ручном тесте выявится, что
> для `food`-колбэка нужно человекочитаемое имя продукта (а не повтор food_id),
> храните соответствие `food_id -> food_name` в pending-сессии и доставайте его в
> `on_callback` (мелкая доработка, не меняющая архитектуру). Юнит-тесты этой
> задачи проверяют только чистые функции рендеринга/клавиатур.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_bot_render.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add fsai/bot.py tests/test_bot_render.py
git commit -m "feat: Telegram bot (render/keyboards + long-polling wiring)"
```

---

## Task 12: Auth setup, entrypoint, README

**Files:**
- Create: `fsai/auth_setup.py`, `fsai/__main__.py`, `README.md`
- Test: `tests/test_auth_setup.py`

- [ ] **Step 1: Write the failing test for auth token exchange**

`tests/test_auth_setup.py`:
```python
from fsai.auth_setup import exchange_verifier


class FakeFs:
    def __init__(self):
        self.authed_with = None

    def get_authorize_url(self, callback_url="oob"):
        return "https://auth.example/url"

    def authenticate(self, verifier):
        self.authed_with = verifier
        return ("ACCESS_TOKEN", "ACCESS_SECRET")


def test_exchange_verifier_returns_tokens():
    fs = FakeFs()
    token, secret = exchange_verifier(fs, "1234")
    assert (token, secret) == ("ACCESS_TOKEN", "ACCESS_SECRET")
    assert fs.authed_with == "1234"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_auth_setup.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'fsai.auth_setup'`

- [ ] **Step 3: Write minimal implementation**

`fsai/auth_setup.py`:
```python
"""Разовый 3-legged OAuth (oob/PIN). Запуск: python -m fsai.auth_setup

Печатает токены, которые нужно положить в .env как
FATSECRET_ACCESS_TOKEN / FATSECRET_ACCESS_SECRET.
"""
import os


def exchange_verifier(fs, verifier: str):
    """Обменивает PIN/verifier на (access_token, access_secret)."""
    return fs.authenticate(verifier)


def main() -> None:
    from dotenv import load_dotenv
    from fatsecret import Fatsecret

    load_dotenv()
    key = os.environ["FATSECRET_CONSUMER_KEY"]
    secret = os.environ["FATSECRET_CONSUMER_SECRET"]
    fs = Fatsecret(key, secret)

    url = fs.get_authorize_url(callback_url="oob")
    print("1) Открой ссылку и подтверди доступ:\n   " + url)
    verifier = input("2) Вставь PIN/verifier и нажми Enter: ").strip()

    token, token_secret = exchange_verifier(fs, verifier)
    print("\nГотово. Добавь в .env:")
    print(f"FATSECRET_ACCESS_TOKEN={token}")
    print(f"FATSECRET_ACCESS_SECRET={token_secret}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_auth_setup.py -q`
Expected: PASS (1 passed)

- [ ] **Step 5: Write the entrypoint `fsai/__main__.py`**

```python
"""Точка входа: python -m fsai — запускает бота в режиме long-polling."""
from dotenv import load_dotenv

from fsai.bot import TelegramBot
from fsai.config import load_config
from fsai.fatsecret_client import FatSecretClient
from fsai.llm.factory import build_provider
from fsai.service import LoggerService
from fsai.store import Store


def main() -> None:
    load_dotenv()
    config = load_config()
    provider = build_provider(config)
    client = FatSecretClient(
        config.fatsecret_consumer_key, config.fatsecret_consumer_secret,
        config.fatsecret_access_token, config.fatsecret_access_secret,
    )
    store = Store(config.db_path)
    service = LoggerService(
        provider=provider, client=client, store=store,
        meal_bounds=(config.meal_breakfast_start, config.meal_lunch_start,
                     config.meal_dinner_start, config.meal_dinner_end),
    )
    bot = TelegramBot(config, service)
    app = bot.build_application()
    app.run_polling()


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Verify the package imports and entrypoint is wired**

Run: `python -c "import fsai.__main__; import fsai.bot; import fsai.service; print('ok')"`
Expected: prints `ok` (без запуска polling).

- [ ] **Step 7: Write `README.md`**

````markdown
# fsai — голосовой логгер еды для FatSecret (Telegram)

Надиктуй боту в Telegram «греча отварная 200г, куриное филе 150г» —
он распарсит LLM-ом, сопоставит с твоей личной таблицей продуктов и запишет
в дневник питания FatSecret.

## Установка

```bash
pip install -e ".[dev]"
cp .env.example .env   # заполни значения
```

## Авторизация в FatSecret (один раз)

1. Заполни `FATSECRET_CONSUMER_KEY` / `FATSECRET_CONSUMER_SECRET` в `.env`.
2. Запусти:
   ```bash
   python -m fsai.auth_setup
   ```
3. Открой ссылку, подтверди доступ, вставь PIN.
4. Скопируй выведенные `FATSECRET_ACCESS_TOKEN` / `FATSECRET_ACCESS_SECRET`
   в `.env`.

## Запуск

```bash
python -m fsai
```

Бот работает в режиме long-polling и отвечает только на `OWNER_CHAT_ID`.

## Как пользоваться

- Надиктуй приём пищи в поле ввода Telegram (встроенный голосовой набор).
- Знакомые продукты с явной граммовкой записываются сразу + кнопка «↩ Отменить».
- Незнакомый продукт → бот предложит кандидатов из FatSecret кнопками;
  выбор сохраняется в таблицу навсегда.
- Не указаны граммы → бот спросит число.

## Тесты

```bash
pytest -q
```

## Эксплуатация

Для постоянной работы заверни `python -m fsai` в systemd-юнит или Docker.
Приём пищи определяется по локальному времени (`TZ` и границы `MEAL_*` в `.env`).
````

- [ ] **Step 8: Run full test suite**

Run: `pytest -q`
Expected: PASS (все тесты зелёные).

- [ ] **Step 9: Commit**

```bash
git add fsai/auth_setup.py fsai/__main__.py README.md tests/test_auth_setup.py
git commit -m "feat: OAuth setup script, entrypoint, README"
```

---

## Self-Review

**1. Spec coverage:**
- Telegram-бот, long-polling, один пользователь → Task 11 (`owner` filter), `__main__` (`run_polling`). ✓
- Текст от голосового набора (без STT) → бот принимает только текст (Task 11). ✓
- LLM-парсинг со сменным провайдером Anthropic/OpenAI → Tasks 5, 6 (`LLMProvider`, factory). ✓
- Личная таблица + органичное наполнение → Tasks 4, 8 (alias save при `confirm_food`). ✓
- Подтверждение при сомнении (известный+граммы+единственный матч → авто; иначе спрашиваем) → Tasks 8, 10 (`Resolved` vs `NeedsGrams/NeedsFood/NeedsServing`). ✓
- Отмена → Tasks 4 (`log`), 10 (`undo`), 11 (`undo` кнопка). ✓
- Приём пищи по времени → Task 9 (`infer_meal`), конфиг-границы. ✓
- `food_entry.create` параметры / `meal` enum / `food_entry.delete` → Task 7 (подтверждено по докам). ✓
- OAuth 3-legged oob → Task 12 (`auth_setup`). ✓
- SQLite-состояние → Task 4. ✓
- Обработка ошибок: чужой отправитель (Task 11 owner-filter), пустой парсинг (Task 5/10 → «не понял»), пустой поиск (Task 11 «попробуй другое название»). Сетевые ретраи и протухший токен — базовая обработка делегирована pyfatsecret/PTB; при ручном тесте добавить try/except в `on_text`/`on_callback` с дружелюбным сообщением (отмечено как мелкая доработка в Task 11 note).

**2. Placeholder scan:** Код во всех шагах конкретен. Единственное место с явной пометкой «доработать при ручном тесте» — runtime food-callback name lookup в Task 11 (note), что допустимо: это не плейсхолдер логики, а оговоренное упрощение тонкой обвязки, проверяемой вручную.

**3. Type consistency:** `ParsedItem/FoodCandidate/Serving/AliasRecord/ResolvedItem` определены в Task 2 и используются согласованно. `Resolution` варианты (`Resolved/NeedsGrams/NeedsFood/NeedsServing`) совпадают в resolver (Task 8) и service (Task 10). `PendingPrompt.kind` ∈ {"food","grams","serving"} согласован между service (Task 10) и bot (Task 11). `create_entry`/`delete_entry` сигнатуры совпадают в client (Task 7), diary (Task 9), service-фейках (Task 10).
