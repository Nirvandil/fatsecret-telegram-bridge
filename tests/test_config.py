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
