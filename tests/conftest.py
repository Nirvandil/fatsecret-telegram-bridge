import pytest

from fsai.llm.base import LLMProvider


class FakeProvider(LLMProvider):
    """Возвращает заранее заданную строку, игнорируя промпт."""

    def __init__(self, response: str = ""):
        self.response = response
        self.last_system = None
        self.last_user = None

    def complete(self, system: str, user: str) -> str:
        self.last_system = system
        self.last_user = user
        return self.response


@pytest.fixture
def fake_provider():
    return FakeProvider()
