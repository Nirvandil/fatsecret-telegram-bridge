import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters,
)

from fatsecret_telegram_bridge.service import AutoLogged, NeedsInput, PendingPrompt

logger = logging.getLogger(__name__)

CB_SEP = "|"


# ---------- pure functions (testable without the Telegram runtime) ----------

def pack_cb(action: str, session_id: str, index: int, payload: str) -> str:
    return CB_SEP.join([action, session_id, str(index), payload])


def unpack_cb(data: str):
    action, session_id, index, payload = data.split(CB_SEP, 3)
    return action, session_id, int(index), payload


def format_autolog(res: AutoLogged) -> str:
    if not res.lines:
        return "Hmm, I didn't catch any items. Rephrase?"
    body = "\n".join(f"• {line}" for line in res.lines)
    return f"✅ Logged:\n{body}"


def undo_keyboard(log_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("↩ Undo", callback_data=pack_cb(
            "undo", "-", 0, str(log_id)))
    ]])


def _candidate_label(c) -> str:
    name = (c.food_name or "").strip()
    if name and c.description:
        label = f"{name} — {c.description}"
    else:
        label = name or c.description or f"id {c.food_id}"
    return label[:100]  # Telegram: a button label must be short and non-empty


def food_keyboard(session_id: str, prompt: PendingPrompt) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        _candidate_label(c),
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
                f"How many grams of '{prompt.parsed.name}'? Send a number."))
        elif prompt.kind == "food":
            if prompt.candidates:
                msgs.append(OutMessage(
                    f"Pick a food for '{prompt.parsed.name}':",
                    food_keyboard(session_id, prompt)))
            else:
                msgs.append(OutMessage(
                    f"Nothing found for '{prompt.parsed.name}'. "
                    f"Try a different name."))
        elif prompt.kind == "serving":
            msgs.append(OutMessage(
                f"'{prompt.parsed.name}' has no gram-based serving. "
                f"Pick a serving:", serving_keyboard(session_id, prompt)))
    return msgs


# ---------- runtime wiring (verified manually, see README) ----------

class TelegramBot:
    def __init__(self, config, service):
        self.config = config
        self.service = service
        # chat_id -> what text input we're waiting for next
        self._awaiting: dict[int, tuple] = {}
        # session_id -> {index -> PendingPrompt}, to fetch servings in a callback
        self._prompts: dict[str, dict[int, PendingPrompt]] = {}
        # session_id -> {index -> kind} — which prompts were already shown (dedup)
        self._sent: dict[str, dict[int, str]] = {}

    def build_application(self) -> Application:
        app = Application.builder().token(self.config.telegram_token).build()
        # OWNER_CHAT_ID is a chat id (private: == user_id, group/supergroup:
        # negative). Filter by chat, not by the sending user.
        owner = filters.Chat(chat_id=self.config.owner_chat_id)
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & owner, self.on_text))
        app.add_handler(CallbackQueryHandler(self.on_callback))
        return app

    # --- incoming text ---
    async def on_text(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        text = update.message.text
        logger.info("Message from chat=%s: %r", chat_id, text)

        try:
            awaiting = self._awaiting.get(chat_id)
            if awaiting is not None:
                await self._handle_awaited_number(update, chat_id, awaiting, text)
                return

            res = await asyncio.to_thread(self.service.process_text, text)
            await self._render(update.message.reply_text, res, chat_id)
        except Exception:
            logger.exception("Error handling message")
            await update.message.reply_text("⚠️ Something went wrong, check the logs.")

    async def _handle_awaited_number(self, update, chat_id, awaiting, text):
        try:
            number = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text("I need a number. Try again.")
            return
        self._awaiting.pop(chat_id, None)
        kind = awaiting[0]
        if kind == "item_grams":
            _, sid, idx = awaiting
            await asyncio.to_thread(self.service.set_grams, sid, idx, number)
            await self._finalize_and_render(update.message.reply_text, sid, chat_id)
        elif kind == "serving_grams":
            _, sid, idx, serving_id = awaiting
            serving = self._find_serving(sid, idx, serving_id)
            await asyncio.to_thread(
                self.service.choose_serving, sid, idx, serving, number)
            await self._finalize_and_render(update.message.reply_text, sid, chat_id)

    # --- button callbacks ---
    async def on_callback(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        action, sid, idx, payload = unpack_cb(query.data)
        chat_id = query.message.chat_id
        logger.info("Callback: action=%s idx=%s payload=%s (session=%s)",
                    action, idx, payload, sid)

        try:
            if action == "undo":
                count = await asyncio.to_thread(self.service.undo, int(payload))
                await query.edit_message_text(f"↩ Undone entries: {count}")
                return
            if action == "food":
                await asyncio.to_thread(self.service.choose_food, sid, idx, payload)
                await query.edit_message_text("Got it.")
                await self._finalize_and_render(
                    query.message.reply_text, sid, chat_id)
                return
            if action == "serv":
                self._awaiting[chat_id] = ("serving_grams", sid, idx, payload)
                await query.edit_message_text(
                    "How many grams in one such serving? Send a number.")
                return
        except Exception:
            logger.exception("Error handling callback")
            await query.message.reply_text("⚠️ Something went wrong, check the logs.")

    # --- result rendering ---
    async def _render(self, reply, res, chat_id):
        if isinstance(res, AutoLogged):
            kb = undo_keyboard(res.log_id) if res.log_id else None
            await reply(format_autolog(res), reply_markup=kb)
        else:
            await self._send_needs_input(reply, res, chat_id)

    async def _send_needs_input(self, reply, res: NeedsInput, chat_id):
        prompts = self._prompts.setdefault(res.session_id, {})
        sent = self._sent.setdefault(res.session_id, {})
        grams_await = None
        for prompt, msg in zip(
                res.pending, build_needs_input_messages(res.session_id, res)):
            prompts[prompt.index] = prompt
            if grams_await is None and prompt.kind == "grams":
                grams_await = prompt.index
            # Already shown this prompt in this form — don't duplicate the message.
            if sent.get(prompt.index) == prompt.kind:
                continue
            await reply(msg.text, reply_markup=msg.keyboard)
            sent[prompt.index] = prompt.kind
        # Await a numeric reply for the first still-open grams prompt.
        if grams_await is not None:
            self._awaiting[chat_id] = ("item_grams", res.session_id, grams_await)

    async def _finalize_and_render(self, reply, session_id, chat_id):
        res = await asyncio.to_thread(self.service.finalize, session_id)
        if isinstance(res, AutoLogged):
            # Session closed — clear state and show the summary.
            self._sent.pop(session_id, None)
            self._prompts.pop(session_id, None)
            await self._render(reply, res, chat_id)
        else:
            # Still-open items remain — send only the new prompts.
            await self._send_needs_input(reply, res, chat_id)

    def _find_serving(self, session_id, index, serving_id):
        prompt = self._prompts.get(session_id, {}).get(index)
        if prompt is None:
            return None
        return next((s for s in prompt.servings if s.serving_id == serving_id),
                    None)
