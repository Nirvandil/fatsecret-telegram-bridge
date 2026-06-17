from fsai.models import FoodCandidate, ParsedItem
from fsai.service import AutoLogged, NeedsInput, PendingPrompt
from fsai.bot import (
    format_autolog, food_keyboard, pack_cb, unpack_cb, build_needs_input_messages,
)


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
