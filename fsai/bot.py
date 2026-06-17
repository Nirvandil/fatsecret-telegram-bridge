import asyncio
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


# ---------- runtime-обвязка (проверяется вручную, см. README) ----------

class TelegramBot:
    def __init__(self, config, service):
        self.config = config
        self.service = service
        # chat_id -> что ждём текстом дальше
        self._awaiting: dict[int, tuple] = {}
        # session_id -> {index -> PendingPrompt}, чтобы доставать servings в колбэке
        self._prompts: dict[str, dict[int, PendingPrompt]] = {}

    def build_application(self) -> Application:
        app = Application.builder().token(self.config.telegram_token).build()
        owner = filters.User(user_id=self.config.owner_chat_id)
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & owner, self.on_text))
        app.add_handler(CallbackQueryHandler(self.on_callback))
        return app

    # --- входящий текст ---
    async def on_text(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        text = update.message.text

        awaiting = self._awaiting.get(chat_id)
        if awaiting is not None:
            await self._handle_awaited_number(update, chat_id, awaiting, text)
            return

        res = await asyncio.to_thread(self.service.process_text, text)
        await self._render(update.message.reply_text, res, chat_id)

    async def _handle_awaited_number(self, update, chat_id, awaiting, text):
        try:
            number = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text("Нужно число. Попробуй ещё раз.")
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

    # --- колбэки кнопок ---
    async def on_callback(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        action, sid, idx, payload = unpack_cb(query.data)
        chat_id = query.message.chat_id

        if action == "undo":
            count = await asyncio.to_thread(self.service.undo, int(payload))
            await query.edit_message_text(f"↩ Отменено записей: {count}")
            return
        if action == "food":
            await asyncio.to_thread(self.service.choose_food, sid, idx, payload)
            await query.edit_message_text("Принято.")
            await self._finalize_and_render(
                query.message.reply_text, sid, chat_id)
            return
        if action == "serv":
            self._awaiting[chat_id] = ("serving_grams", sid, idx, payload)
            await query.edit_message_text(
                "Сколько грамм в одной такой порции? Пришли число.")
            return

    # --- рендеринг результата ---
    async def _render(self, reply, res, chat_id):
        if isinstance(res, AutoLogged):
            kb = undo_keyboard(res.log_id) if res.log_id else None
            await reply(format_autolog(res), reply_markup=kb)
        else:
            await self._send_needs_input(reply, res, chat_id)

    async def _send_needs_input(self, reply, res: NeedsInput, chat_id):
        self._prompts[res.session_id] = {p.index: p for p in res.pending}
        for prompt, msg in zip(
                res.pending, build_needs_input_messages(res.session_id, res)):
            await reply(msg.text, reply_markup=msg.keyboard)
            if prompt.kind == "grams":
                self._awaiting[chat_id] = ("item_grams", res.session_id,
                                           prompt.index)

    async def _finalize_and_render(self, reply, session_id, chat_id):
        res = await asyncio.to_thread(self.service.finalize, session_id)
        await self._render(reply, res, chat_id)

    def _find_serving(self, session_id, index, serving_id):
        prompt = self._prompts.get(session_id, {}).get(index)
        if prompt is None:
            return None
        return next((s for s in prompt.servings if s.serving_id == serving_id),
                    None)
