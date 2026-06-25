from app.services.ai_errors import format_ai_error


def test_format_anthropic_credit_error() -> None:
    exc = ValueError(
        "Error code: 400 - Your credit balance is too low to access the Anthropic API."
    )
    message = format_ai_error(exc)
    assert "Guthaben aufgebraucht" in message
    assert "ANTHROPIC_API_KEY" in message
