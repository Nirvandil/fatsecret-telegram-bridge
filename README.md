# fsai — голосовой логгер еды для FatSecret (Telegram)

Надиктуй боту в Telegram «греча отварная 200г, куриное филе 150г» —
он распарсит LLM-ом, сопоставит с твоей личной таблицей продуктов и запишет
в дневник питания FatSecret.

## Установка

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; на *nix: source .venv/bin/activate
pip install -e ".[dev]"
copy .env.example .env          # Windows; на *nix: cp .env.example .env
# затем заполни значения в .env
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
