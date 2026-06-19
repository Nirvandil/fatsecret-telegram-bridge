import pytest
from fatsecret_telegram_bridge.config import load_config


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
    assert cfg.db_path == "fatsecret_telegram_bridge.sqlite3"
    assert (cfg.meal_breakfast_start, cfg.meal_lunch_start,
            cfg.meal_dinner_start, cfg.meal_dinner_end) == (5, 11, 16, 22)
    assert cfg.log_level == "INFO"
    assert cfg.poll_interval == 0.0
    assert cfg.poll_timeout == 10
    assert cfg.fatsecret_region is None and cfg.fatsecret_language is None


def test_region_language_loaded():
    env = base_env()
    env["FATSECRET_REGION"] = "DE"
    env["FATSECRET_LANGUAGE"] = "de"
    cfg = load_config(env)
    assert cfg.fatsecret_region == "DE" and cfg.fatsecret_language == "de"


def test_llm_none_does_not_require_key():
    env = base_env()
    del env["LLM_API_KEY"]
    env["LLM_PROVIDER"] = "none"
    cfg = load_config(env)
    assert cfg.llm_provider == "none" and cfg.llm_api_key == ""


def test_missing_llm_key_raises_when_provider_set():
    env = base_env()
    del env["LLM_API_KEY"]
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        load_config(env)


def test_missing_required_raises():
    env = base_env()
    del env["TELEGRAM_TOKEN"]
    with pytest.raises(ValueError, match="TELEGRAM_TOKEN"):
        load_config(env)
