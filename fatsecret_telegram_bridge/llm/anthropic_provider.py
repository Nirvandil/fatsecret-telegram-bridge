from fatsecret_telegram_bridge.llm.base import LLMProvider

MAX_TOKENS = 1024


class AnthropicProvider(LLMProvider):
    def __init__(self, client, model: str):
        self._client = client
        self._model = model

    def complete(self, system: str, user: str) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text
