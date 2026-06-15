from app.core.config import settings


def voice_for_speaker(speaker: str, *, provider: str) -> str:
    if provider == "say":
        if speaker == "openai":
            return settings.tts_voice_openai
        if speaker == "anthropic":
            return settings.tts_voice_anthropic
        if speaker == "AI_A":
            return settings.tts_voice_ai_a
        if speaker == "AI_B":
            return settings.tts_voice_ai_b
        return settings.tts_voice_narrator

    if speaker == "openai":
        return settings.tts_edge_voice_openai
    if speaker == "anthropic":
        return settings.tts_edge_voice_anthropic
    if speaker == "AI_A":
        return settings.tts_edge_voice_ai_a
    if speaker == "AI_B":
        return settings.tts_edge_voice_ai_b
    return settings.tts_edge_voice_narrator
