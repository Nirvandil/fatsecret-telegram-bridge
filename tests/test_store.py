import threading

from fatsecret_telegram_bridge.models import AliasRecord
from fatsecret_telegram_bridge.store import Store


def make_store(tmp_path):
    return Store(str(tmp_path / "t.sqlite3"))


def test_save_and_get_alias(tmp_path):
    s = make_store(tmp_path)
    rec = AliasRecord("гречка", "11", "Buckwheat, cooked")
    s.save_alias(rec)
    assert s.get_alias("гречка") == rec


def test_get_missing_alias_returns_none(tmp_path):
    s = make_store(tmp_path)
    assert s.get_alias("нет такого") is None


def test_save_alias_upserts(tmp_path):
    s = make_store(tmp_path)
    s.save_alias(AliasRecord("рис", "1", "Rice"))
    s.save_alias(AliasRecord("рис", "9", "Rice, white"))
    got = s.get_alias("рис")
    assert got.food_id == "9" and got.food_name == "Rice, white"


def test_all_alias_names(tmp_path):
    s = make_store(tmp_path)
    s.save_alias(AliasRecord("рис", "1", "Rice"))
    s.save_alias(AliasRecord("гречка", "3", "Buckwheat"))
    assert sorted(s.all_alias_names()) == ["гречка", "рис"]


def test_log_roundtrip(tmp_path):
    s = make_store(tmp_path)
    log_id = s.add_log("oatmeal 50g", ["e1", "e2"])
    rec = s.get_log(log_id)
    assert rec["raw_text"] == "oatmeal 50g"
    assert rec["entry_ids"] == ["e1", "e2"]


def test_get_missing_log_returns_none(tmp_path):
    s = make_store(tmp_path)
    assert s.get_log(999) is None


def test_store_usable_from_another_thread(tmp_path):
    # The bot calls Store from a worker thread (asyncio.to_thread); the
    # connection is created in the main thread — sqlite forbids this by default.
    s = make_store(tmp_path)
    s.save_alias(AliasRecord("рис", "1", "Rice"))
    result = {}

    def worker():
        try:
            result["names"] = s.all_alias_names()
            s.save_alias(AliasRecord("гречка", "3", "Buckwheat"))
            result["log_id"] = s.add_log("t", ["e1"])
        except Exception as e:  # noqa: BLE001
            result["error"] = e

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert "error" not in result, result.get("error")
    assert result["names"] == ["рис"]
    assert result["log_id"] is not None
    assert s.get_alias("гречка") is not None


def test_migrates_legacy_aliases_schema(tmp_path):
    # An old DB had a fixed serving per alias; the new schema drops that table.
    import sqlite3
    path = str(tmp_path / "legacy.sqlite3")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE aliases (alias TEXT PRIMARY KEY, food_id TEXT, "
        "serving_id TEXT, grams_per_serving REAL, food_name TEXT, created_at TEXT)")
    conn.commit()
    conn.close()

    s = Store(path)                       # migration runs in __init__
    s.save_alias(AliasRecord("rice", "1", "Rice"))
    assert s.get_alias("rice").food_id == "1"
