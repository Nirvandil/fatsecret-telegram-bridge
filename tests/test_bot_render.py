from fatsecret_telegram_bridge.models import FoodCandidate, ParsedItem
from fatsecret_telegram_bridge.service import AutoLogged, NeedsInput, PendingPrompt
from fatsecret_telegram_bridge.bot import (
    format_autolog, food_keyboard, pack_cb, unpack_cb, build_needs_input_messages,
    TelegramBot,
)


def test_format_autolog_lists_items():
    res = AutoLogged(lines=["Buckwheat — 200 g (lunch)"], log_id=7)
    text = format_autolog(res)
    assert "Buckwheat — 200 g (lunch)" in text
    assert "Logged" in text


def test_format_autolog_empty():
    assert "rephrase" in format_autolog(AutoLogged(lines=[], log_id=None)).lower()


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


def test_food_keyboard_handles_empty_name():
    prompt = PendingPrompt(
        index=0, kind="food", parsed=ParsedItem("x", 10.0),
        candidates=[FoodCandidate("7", "", "")],
    )
    btn = food_keyboard("s", prompt).inline_keyboard[0][0]
    assert btn.text                      # label is non-empty
    assert btn.callback_data == pack_cb("food", "s", 0, "7")


def test_build_needs_input_messages_for_grams():
    prompt = PendingPrompt(index=0, kind="grams", parsed=ParsedItem("гречка"))
    msgs = build_needs_input_messages("sess-1", NeedsInput("sess-1", [prompt]))
    assert any("grams" in m.text.lower() for m in msgs)


class _ReplyRecorder:
    def __init__(self):
        self.calls = []

    async def __call__(self, text, reply_markup=None):
        self.calls.append(text)


async def test_send_needs_input_does_not_duplicate_on_repeat():
    bot = TelegramBot(config=None, service=None)
    reply = _ReplyRecorder()
    res = NeedsInput("s1", [
        PendingPrompt(0, "food", ParsedItem("a", query_en="a", grams=10.0),
                      candidates=[FoodCandidate("1", "A", "")]),
        PendingPrompt(1, "food", ParsedItem("b", query_en="b", grams=20.0),
                      candidates=[FoodCandidate("2", "B", "")]),
    ])
    await bot._send_needs_input(reply, res, chat_id=1)
    assert len(reply.calls) == 2
    # Re-sending the same prompts (after another item is resolved) — no duplicates.
    await bot._send_needs_input(reply, res, chat_id=1)
    assert len(reply.calls) == 2
