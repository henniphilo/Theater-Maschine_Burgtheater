from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.services.ai_errors import unwrap_ai_error
from app.services.providers.anthropic_provider import AnthropicProvider
from app.services.providers.base import ChatProvider
from app.services.providers.openai_provider import OpenAIProvider


def _ai_retryable(exc: BaseException) -> bool:
    """Do not retry client/config errors (4xx) — only transient failures."""
    root = unwrap_ai_error(exc)
    try:
        from anthropic import (
            APIConnectionError,
            APITimeoutError,
            AuthenticationError,
            BadRequestError,
            PermissionDeniedError,
            RateLimitError,
        )
    except ImportError:
        return True
    if isinstance(root, (BadRequestError, AuthenticationError, PermissionDeniedError)):
        return False
    if isinstance(root, (APIConnectionError, APITimeoutError, RateLimitError)):
        return True
    try:
        from openai import APIConnectionError as OpenAIConnectionError
        from openai import APITimeoutError as OpenAITimeoutError
        from openai import AuthenticationError as OpenAIAuthError
        from openai import BadRequestError as OpenAIBadRequestError
        from openai import PermissionDeniedError as OpenAIPermissionDeniedError
        from openai import RateLimitError as OpenAIRateLimitError
    except ImportError:
        return True
    if isinstance(
        root,
        (OpenAIBadRequestError, OpenAIAuthError, OpenAIPermissionDeniedError),
    ):
        return False
    if isinstance(root, (OpenAIConnectionError, OpenAITimeoutError, OpenAIRateLimitError)):
        return True
    return True


class AIService:
    def __init__(self) -> None:
        self.providers: dict[str, ChatProvider] = {}
        self._init_provider("openai")
        self._init_provider("anthropic")

    def _init_provider(self, provider: str) -> None:
        try:
            if provider == "openai":
                self.providers[provider] = OpenAIProvider()
            elif provider == "anthropic":
                self.providers[provider] = AnthropicProvider()
        except RuntimeError:
            # Keep app booting even if one provider is not configured yet.
            return

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        retry=retry_if_exception(_ai_retryable),
    )
    async def generate(
        self, provider: str, model: str, messages: list[dict[str, str]], max_tokens: int = 2048
    ) -> str:
        adapter = self.providers.get(provider)
        if adapter is None:
            raise ValueError(f"Unsupported provider: {provider}")
        return await adapter.generate(model, messages, max_tokens=max_tokens)
