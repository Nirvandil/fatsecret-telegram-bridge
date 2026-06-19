import pytest

from fatsecret_telegram_bridge.llm.anthropic_provider import AnthropicProvider
from fatsecret_telegram_bridge.llm.openai_provider import OpenAIProvider
from fatsecret_telegram_bridge.llm.factory import build_provider


class FakeAnthropicMessages:
    def __init__(self, sink):
        self.sink = sink

    def create(self, **kwargs):
        self.sink.update(kwargs)
        class _Block:
            text = "ANTHROPIC_OK"
        class _Resp:
            content = [_Block()]
        return _Resp()


class FakeAnthropicClient:
    def __init__(self, sink):
        self.messages = FakeAnthropicMessages(sink)


class FakeOpenAIChat:
    def __init__(self, sink):
        self.completions = self
        self.sink = sink

    def create(self, **kwargs):
        self.sink.update(kwargs)
        class _Msg:
            content = "OPENAI_OK"
        class _Choice:
            message = _Msg()
        class _Resp:
            choices = [_Choice()]
        return _Resp()


class FakeOpenAIClient:
    def __init__(self, sink):
        self.chat = FakeOpenAIChat(sink)


def test_anthropic_provider_calls_model_and_returns_text():
    sink = {}
    p = AnthropicProvider(client=FakeAnthropicClient(sink), model="claude-haiku-4-5")
    out = p.complete("SYS", "USR")
    assert out == "ANTHROPIC_OK"
    assert sink["model"] == "claude-haiku-4-5"
    assert sink["system"] == "SYS"
    assert sink["messages"] == [{"role": "user", "content": "USR"}]


def test_openai_provider_calls_model_and_returns_text():
    sink = {}
    p = OpenAIProvider(client=FakeOpenAIClient(sink), model="gpt-4o-mini")
    out = p.complete("SYS", "USR")
    assert out == "OPENAI_OK"
    assert sink["model"] == "gpt-4o-mini"
    assert sink["messages"][0] == {"role": "system", "content": "SYS"}
    assert sink["messages"][1] == {"role": "user", "content": "USR"}


def test_factory_selects_by_config(monkeypatch):
    class FakeAnthropicModule:
        def Anthropic(self, api_key):
            return object()
    import sys
    monkeypatch.setitem(sys.modules, "anthropic", FakeAnthropicModule())

    class Cfg:
        llm_provider = "anthropic"
        llm_model = "claude-haiku-4-5"
        llm_api_key = "k"
    assert isinstance(build_provider(Cfg()), AnthropicProvider)


def test_factory_rejects_unknown_provider():
    class Cfg:
        llm_provider = "llama"
        llm_model = "x"
        llm_api_key = "k"
    with pytest.raises(ValueError, match="llama"):
        build_provider(Cfg())
