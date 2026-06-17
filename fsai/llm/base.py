from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Минимальный интерфейс модели: вернуть текст ответа на пару system/user."""

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        ...
