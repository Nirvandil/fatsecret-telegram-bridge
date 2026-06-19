# fatsecret-telegram-bridge

Type what you ate into Telegram — *"oatmeal 50g, chicken breast 150g, apple 200g"* — and it gets logged into your [FatSecret](https://www.fatsecret.com/) food diary automatically. (Tip: use your phone keyboard's voice-to-text, e.g. Gboard's mic, to "dictate" the message instead of typing it.)

A small, single-user Telegram bot that turns free-form meal descriptions into FatSecret diary entries. An LLM parses the message, the bot matches each food against your personal lookup table (which grows as you use it), and writes the entries via the FatSecret API. Built to kill the tedium of typing every weighed food by hand.

> Python package name: `fatsecret_telegram_bridge`. Repo name: `fatsecret-telegram-bridge`.

---

## How it works

```
You type in Telegram ──▶ text ──▶ [LLM: parse + translate to English]
   ──▶ [match against your personal table / FatSecret search]
   ──▶ known & unambiguous? ── yes ──▶ write to diary  (+ "↩ Undo" button)
                             ── no  ──▶ ask you to pick the food (inline buttons)
```

- **Text in, no STT service:** the bot only ever receives text. Type it, or use your phone keyboard's built-in voice-to-text (e.g. Gboard's mic) to dictate it into the message field — either way the bot just gets text, so no separate speech-to-text service is needed.
- **Personal food table grows organically:** the first time you mention a food, the bot searches FatSecret and shows candidates as buttons; you tap one, and the mapping (your name → FatSecret food + serving) is saved forever. Next time it's logged instantly.
- **LLM does parsing + translation (optional):** it turns natural speech into structured `{food, quantity, unit}` items *and* produces an English search term, because the free FatSecret tier only exposes the **US/English** food database (see [Limitations](#limitations)). The LLM is optional — set `LLM_PROVIDER=none` to run key-free with a simple regex parser (structured `name quantity unit` input, no translation).
- **Any unit, not just grams:** log in whatever unit FatSecret offers for a food — `200 g`, `6 oz`, `1 cup`, `2 slices`, `1 piece`. The serving is matched to your unit per message; grams are not forced.
- **Undo:** every auto-logged message comes with an inline "↩ Undo" button.

---

## Features

- Natural-language meal logging in any language (parsed + translated by the LLM).
- **Optional LLM** — pluggable **Anthropic** / **OpenAI**, or **none** (no key, regex parser) for English/structured input.
- **Any unit:** grams, oz, cup, tbsp, slice, piece — logged in the food's own serving, no forced grams conversion.
- Organic personal mapping table — no upfront data entry.
- Confirm-only-when-uncertain: known foods are logged immediately; unknown/ambiguous ones ask for a one-tap choice.
- Automatic meal assignment by time of day (configurable), per-entry undo.
- **Optional localized food DB** via `FATSECRET_REGION`/`LANGUAGE` (FatSecret Premier).
- Runs entirely on FatSecret's **free** Basic tier (5000 calls/day).
- SQLite for state, long-polling (no public webhook/HTTPS endpoint required).

---

## Prerequisites

You'll need four things (all have free options):

1. **Python 3.11+**
2. **A Telegram bot token** — create a bot via [@BotFather](https://t.me/BotFather).
3. **FatSecret API credentials (OAuth 1.0)** — register at the [FatSecret Platform](https://platform.fatsecret.com/platform-api). The free *Basic* plan includes food-diary read/write.
4. **An LLM API key (optional)** — [Anthropic](https://console.anthropic.com/) or [OpenAI](https://platform.openai.com/); a fraction of a cent per message. Skip it with `LLM_PROVIDER=none` if you'll type structured English (`name quantity unit`) and don't need translation.

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/Nirvandil/fatsecret-telegram-bridge.git
cd fatsecret-telegram-bridge

python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1

pip install -e ".[dev]"
```

### 2. Create your Telegram bot

1. Message [@BotFather](https://t.me/BotFather), send `/newbot`, follow the prompts, and copy the **bot token**.
2. Find your **chat id**:
   - **Private chat (recommended):** message [@userinfobot](https://t.me/userinfobot) — it replies with your numeric user id (a positive number). Use that as `OWNER_CHAT_ID`, and chat with your bot 1-on-1.
   - **Group/supergroup:** the chat id is a negative number (e.g. `-1001234567890`). If you go this route you **must** disable privacy mode in @BotFather (`/setprivacy` → select your bot → **Disable**) and then re-add the bot to the group, otherwise it won't see normal messages.

### 3. Get FatSecret API credentials

1. Sign up at [platform.fatsecret.com](https://platform.fatsecret.com/platform-api) and create an application.
2. Copy the **OAuth 1.0** *Consumer Key* and *Consumer Secret* (a.k.a. Client ID / Client Secret).
3. FatSecret may require you to **whitelist the IP address** of the machine that will run the bot — set this in your app's API settings, otherwise calls are rejected.

### 4. Get an LLM API key

Grab a key from Anthropic *or* OpenAI and note the model you want (e.g. `claude-haiku-4-5` or `gpt-4o-mini`).

### 5. Configure `.env`

```bash
cp .env.example .env
```

Open `.env` and fill in the values:

| Variable | What it is |
|---|---|
| `TELEGRAM_TOKEN` | Bot token from @BotFather |
| `OWNER_CHAT_ID` | Your chat id (positive for private, negative for group) |
| `FATSECRET_CONSUMER_KEY` / `FATSECRET_CONSUMER_SECRET` | FatSecret OAuth 1.0 app credentials |
| `FATSECRET_ACCESS_TOKEN` / `FATSECRET_ACCESS_SECRET` | Filled in step 6 |
| `FATSECRET_REGION` / `FATSECRET_LANGUAGE` | Optional, e.g. `DE` / `de` — localized food DB (Premier only; free tier ignores) |
| `LLM_PROVIDER` | `anthropic`, `openai`, or `none` (no LLM, regex parser) |
| `LLM_MODEL` | e.g. `claude-haiku-4-5` or `gpt-4o-mini` (ignored when `none`) |
| `LLM_API_KEY` | Your Anthropic/OpenAI key (leave empty when `none`) |
| `DB_PATH` | SQLite file path (default `fatsecret_telegram_bridge.sqlite3`) |
| `TZ` | Your timezone, e.g. `Europe/Berlin` |
| `MEAL_*` | Hour boundaries for breakfast/lunch/dinner |
| `LOG_LEVEL` | `INFO` (use `DEBUG` to see raw LLM output) |
| `POLL_TIMEOUT` / `POLL_INTERVAL` | Long-polling tuning (defaults are fine) |

`.env` and the SQLite database are git-ignored — they never get committed.

### 6. Authorize your FatSecret account (one time)

FatSecret diary access uses 3-legged OAuth. Run the helper, which uses an out-of-band PIN flow (works on headless servers):

```bash
python -m fatsecret_telegram_bridge.auth_setup
```

It prints an authorization URL → open it, approve access, copy the PIN back into the prompt. It then prints your `FATSECRET_ACCESS_TOKEN` and `FATSECRET_ACCESS_SECRET` — paste both into `.env`. These tokens are long-lived; you only do this once.

### 7. Run

```bash
python -m fatsecret_telegram_bridge
```

You should see `fatsecret_telegram_bridge started (long-polling…)`. Now message your bot.

---

## Using it

- **Type** a meal in Telegram — or use your keyboard's voice-to-text (e.g. Gboard's mic) to dictate it. Units are flexible: *"buckwheat 200 g, chicken 6 oz, rice 1 cup, 2 eggs"*.
- For each **new** food, the bot replies with FatSecret candidates as buttons — tap the right one. The food is saved to your personal table, so it's never asked again.
- **Known** foods with a clear quantity and unit are logged immediately, with a **↩ Undo** button.
- If you gave no unit, the bot asks which serving (g, oz, cup, …); if no quantity, it asks for a number.
- Meal (breakfast/lunch/dinner/other) is inferred from the current time; tune the boundaries in `.env`.

The whole flow is logged to the console — set `LOG_LEVEL=DEBUG` to also see the raw LLM responses.

---

## Limitations

- **Free tier = US/English food database only.** The free FatSecret *Basic* plan exposes only the US/English dataset. Searching in another language returns nothing — passing `region`/`language` (e.g. `RU`/`ru`) is accepted but yields no results on a free token (localized databases are a FatSecret **Premier** feature). This is why the LLM translates each food name to English before searching. In practice you match against **generic US food entries** ("Apple", "Oatmeal", "Sugar"); region-specific or branded products usually aren't present — pick the closest generic, and it's saved to your table for next time.
- **Single user.** The bot only responds in one chat (`OWNER_CHAT_ID`); messages from anyone/anywhere else are silently ignored.
- **Group chats need privacy mode off.** To use the bot in a group/supergroup, disable privacy mode in @BotFather and re-add the bot (see [Setup](#2-create-your-telegram-bot)). A private 1-on-1 chat is simpler and needs none of this.
- **Meal is inferred from the time of day.** Breakfast/lunch/dinner/other is chosen by the clock (boundaries configurable via `MEAL_*` in `.env`); there is no in-chat meal override. Adjust in the FatSecret app if it guesses wrong.
- **One "how many grams?" follow-up at a time.** If a single message contains several foods *without* grams, the bot reliably tracks only the first grams question. Easiest workaround: include grams in the message ("oatmeal 50g").
- **You confirm each new food once.** The first time a food appears you pick the FatSecret match (best-effort); it's remembered afterwards. A wrong pick is logged like any entry — use **↩ Undo** or fix it in the FatSecret app.
- **Requires an LLM API key with credit.** Parsing/translation calls Anthropic or OpenAI (cents per day for one user); quality depends on the model you pick.
- **FatSecret may require IP whitelisting.** Some accounts must register the running machine's IP in the app's API settings, otherwise calls are rejected with a signature/permission error.

---

## Running as a long-lived service

For always-on use, wrap `python -m fatsecret_telegram_bridge` in a process manager so the bot is reachable whenever you open Telegram:

- **systemd** (Linux): a simple unit running `…/.venv/bin/python -m fatsecret_telegram_bridge` with `WorkingDirectory` set to the repo and `Restart=always`.
- **Docker**: a tiny image with the repo + `.env` mounted, `CMD ["python", "-m", "fatsecret_telegram_bridge"]`.

A cheap VPS, a Raspberry Pi, or a home server all work — long-polling needs no inbound ports.

---

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

Architecture (small, focused modules under `fatsecret_telegram_bridge/`):

| Module | Responsibility |
|---|---|
| `parser.py` + `llm/` | Text → structured items: `Parser` (LLM, with translation) or `RegexParser` (no LLM) |
| `units.py` | Normalize a unit string ("grams"/"г" → "g", "ounce" → "oz") for serving matching |
| `fatsecret_client.py` | Thin wrapper over the `fatsecret` library (search / servings / create / delete) |
| `resolver.py` | Map a parsed item to a FatSecret food + serving (table lookup or search), matching the unit |
| `diary.py` | Meal inference and diary writes |
| `service.py` | Orchestration: parse → resolve → auto-log or ask (food / serving / quantity); undo |
| `bot.py` | Telegram adapter (handlers, inline keyboards, rendering) |
| `store.py` | SQLite: alias table + entry log |
| `auth_setup.py` | One-time 3-legged OAuth helper |

---

## License

[MIT](LICENSE) — do whatever you want.

## Disclaimer

Not affiliated with or endorsed by FatSecret. Use within FatSecret's API terms. This is a personal-use tool; mind your API keys and credentials.
