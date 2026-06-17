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
