"""User-facing AI provider error formatting."""

from __future__ import annotations


def unwrap_ai_error(exc: BaseException) -> BaseException:
    from tenacity import RetryError

    if isinstance(exc, RetryError) and exc.last_attempt.failed:
        inner = exc.last_attempt.exception()
        if inner is not None:
            return inner
    return exc


def format_ai_error(exc: BaseException) -> str:
    root = unwrap_ai_error(exc)
    message = str(root)
    lowered = message.lower()

    if "credit balance is too low" in lowered:
        return (
            "Anthropic API: Guthaben aufgebraucht. "
            "Bitte unter console.anthropic.com → Plans & Billing Credits nachladen "
            "oder einen anderen ANTHROPIC_API_KEY in backend/.env setzen."
        )
    if "invalid x-api-key" in lowered or "authentication" in lowered and "anthropic" in lowered:
        return "Anthropic API: Ungültiger oder fehlender API-Key (ANTHROPIC_API_KEY)."
    if "insufficient_quota" in lowered or "exceeded your current quota" in lowered:
        return "OpenAI API: Kontingent aufgebraucht. Bitte Billing prüfen oder OPENAI_API_KEY wechseln."
    if "invalid_api_key" in lowered:
        return "OpenAI API: Ungültiger oder fehlender API-Key (OPENAI_API_KEY)."

    return message
