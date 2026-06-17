from fsai.llm.base import LLMProvider
from fsai.llm.anthropic_provider import AnthropicProvider
from fsai.llm.openai_provider import OpenAIProvider


def build_provider(config) -> LLMProvider:
    provider = config.llm_provider.lower()
    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=config.llm_api_key)
        return AnthropicProvider(client=client, model=config.llm_model)
    if provider == "openai":
        import openai
        client = openai.OpenAI(api_key=config.llm_api_key)
        return OpenAIProvider(client=client, model=config.llm_model)
    raise ValueError(f"Unknown LLM_PROVIDER: {config.llm_provider}")
