# fatsecret-telegram-bridge

Dictate (or type) what you ate into Telegram — *"oatmeal 50g, chicken breast 150g, apple 200g"* — and it gets logged into your [FatSecret](https://www.fatsecret.com/) food diary automatically.

A small, single-user Telegram bot that turns free-form meal descriptions into FatSecret diary entries. An LLM parses the message, the bot matches each food against your personal lookup table (which grows as you use it), and writes the entries via the FatSecret API. Built to kill the tedium of typing every weighed food by hand.

> Python package name: `fsai`. Repo name: `fatsecret-telegram-bridge`.

---

## How it works

```
You dictate in Telegram ──▶ text ──▶ [LLM: parse + translate to English]
   ──▶ [match against your personal table / FatSecret search]
   ──▶ known & unambiguous? ── yes ──▶ write to diary  (+ "↩ Undo" button)
                             ── no  ──▶ ask you to pick the food (inline buttons)
```

- **Voice is free and built-in:** use Telegram's own voice-to-text in the message field. The bot only ever receives text — no separate speech-to-text service needed.
- **Personal food table grows organically:** the first time you mention a food, the bot searches FatSecret and shows candidates as buttons; you tap one, and the mapping (your name → FatSecret food + serving) is saved forever. Next time it's logged instantly.
- **LLM does parsing + translation:** it turns natural speech into structured `{food, grams}` pairs *and* produces an English search term, because the free FatSecret tier only exposes the **US/English** food database (see [Limitations](#limitations)).
- **Undo:** every auto-logged message comes with an inline "↩ Undo" button.

---

## Features

- Natural-language meal logging in any language (parsed + translated by the LLM).
- Organic personal mapping table — no upfront data entry.
- Confirm-only-when-uncertain: known foods with explicit grams are logged immediately; unknown/ambiguous ones ask for a one-tap choice.
- Automatic meal assignment by time of day (configurable), per-entry undo.
- Pluggable LLM provider: **Anthropic** or **OpenAI**.
- Runs entirely on FatSecret's **free** Basic tier (5000 calls/day).
- SQLite for state, long-polling (no public webhook/HTTPS endpoint required).

---

## Prerequisites

You'll need four things (all have free options):

1. **Python 3.11+**
2. **A Telegram bot token** — create a bot via [@BotFather](https://t.me/BotFather).
3. **FatSecret API credentials (OAuth 1.0)** — register at the [FatSecret Platform](https://platform.fatsecret.com/platform-api). The free *Basic* plan includes food-diary read/write.
4. **An LLM API key** — either [Anthropic](https://console.anthropic.com/) or [OpenAI](https://platform.openai.com/). Cost is a fraction of a cent per message.

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
| `LLM_PROVIDER` | `anthropic` or `openai` |
| `LLM_MODEL` | e.g. `claude-haiku-4-5` or `gpt-4o-mini` |
| `LLM_API_KEY` | Your Anthropic/OpenAI key |
| `DB_PATH` | SQLite file path (default `fsai.sqlite3`) |
| `TZ` | Your timezone, e.g. `Europe/Berlin` |
| `MEAL_*` | Hour boundaries for breakfast/lunch/dinner |
| `LOG_LEVEL` | `INFO` (use `DEBUG` to see raw LLM output) |
| `POLL_TIMEOUT` / `POLL_INTERVAL` | Long-polling tuning (defaults are fine) |

`.env` and the SQLite database are git-ignored — they never get committed.

### 6. Authorize your FatSecret account (one time)

FatSecret diary access uses 3-legged OAuth. Run the helper, which uses an out-of-band PIN flow (works on headless servers):

```bash
python -m fsai.auth_setup
```

It prints an authorization URL → open it, approve access, copy the PIN back into the prompt. It then prints your `FATSECRET_ACCESS_TOKEN` and `FATSECRET_ACCESS_SECRET` — paste both into `.env`. These tokens are long-lived; you only do this once.

### 7. Run

```bash
python -m fsai
```

You should see `fsai started (long-polling…)`. Now message your bot.

---

## Using it

- **Dictate** a meal in Telegram (tap the mic in the message field), or just type:
  *"buckwheat 200g, low-fat cottage cheese 150g, 1 banana"*.
- For each **new** food, the bot replies with FatSecret candidates as buttons — tap the right one. The choice is saved to your personal table, so it's never asked again.
- **Known** foods with explicit grams are logged immediately, with a **↩ Undo** button.
- If you didn't give grams, the bot asks for a number.
- Meal (breakfast/lunch/dinner/other) is inferred from the current time; tune the boundaries in `.env`.

The whole flow is logged to the console — set `LOG_LEVEL=DEBUG` to also see the raw LLM responses.

---

## Limitations

- **Single user.** The bot only responds in one chat (`OWNER_CHAT_ID`); everything else is ignored.
- **US/English food database.** The free FatSecret Basic tier exposes only the US/English dataset — localized (e.g. Russian) search returns nothing. That's why the LLM translates food names to English before searching. You'll be matching against generic US food entries (e.g. "Apple", "Oatmeal"); for region-specific branded products, pick the closest generic. (Localized databases are a FatSecret Premier feature.)
- **Best-effort matching.** The first pick per food is yours to confirm; after that it's remembered.

---

## Running as a long-lived service

For always-on use, wrap `python -m fsai` in a process manager so the bot is reachable whenever you open Telegram:

- **systemd** (Linux): a simple unit running `…/.venv/bin/python -m fsai` with `WorkingDirectory` set to the repo and `Restart=always`.
- **Docker**: a tiny image with the repo + `.env` mounted, `CMD ["python", "-m", "fsai"]`.

A cheap VPS, a Raspberry Pi, or a home server all work — long-polling needs no inbound ports.

---

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

Architecture (small, focused modules under `fsai/`):

| Module | Responsibility |
|---|---|
| `parser.py` + `llm/` | Text → structured items via a pluggable `LLMProvider` |
| `fatsecret_client.py` | Thin wrapper over the `fatsecret` library (search / servings / create / delete) |
| `resolver.py` | Map a parsed item to a FatSecret food + serving (table lookup or search) |
| `diary.py` | Meal inference, units math, diary writes |
| `service.py` | Orchestration: parse → resolve → auto-log or ask; undo |
| `bot.py` | Telegram adapter (handlers, inline keyboards, rendering) |
| `store.py` | SQLite: alias table + entry log |
| `auth_setup.py` | One-time 3-legged OAuth helper |

---

## License

[MIT](LICENSE) — do whatever you want.

## Disclaimer

Not affiliated with or endorsed by FatSecret. Use within FatSecret's API terms. This is a personal-use tool; mind your API keys and credentials.
