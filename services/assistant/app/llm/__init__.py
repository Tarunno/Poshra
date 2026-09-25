from app.llm.base import (
    Conversation,
    Provider,
    TextDelta,
    ToolCall,
    ToolResult,
    ToolSpec,
    Turn,
)

__all__ = [
    "Conversation",
    "Provider",
    "TextDelta",
    "ToolCall",
    "ToolResult",
    "ToolSpec",
    "Turn",
    "build_provider",
]


def build_provider(config) -> Provider:
    """Pick the provider named in the configuration.

    Imported lazily so a deployment running one provider does not need the
    other's client installed or its key present.
    """
    if config.provider == "anthropic":
        from app.llm.anthropic import AnthropicProvider

        return AnthropicProvider(
            api_key=config.api_key,
            # One key, billed by use: nothing to rotate between.
            model=config.models[0],
            max_tokens=config.max_tokens,
        )

    if config.provider == "gemini":
        from app.llm.gemini import GeminiProvider

        return GeminiProvider(
            api_key=config.api_key,
            models=config.models,
            max_tokens=config.max_tokens,
            timeout=config.llm_timeout,
        )

    raise ValueError(f"unknown LLM provider: {config.provider}")
