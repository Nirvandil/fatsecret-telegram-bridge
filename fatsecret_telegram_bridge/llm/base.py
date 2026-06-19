from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Minimal model interface: return the response text for a system/user pair."""

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        ...
