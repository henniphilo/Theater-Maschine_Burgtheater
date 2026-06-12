from app.core.config import settings


def normalize_speaker(speaker: str) -> str:
    mapping = {
        "openai": "AI_A",
        "anthropic": "AI_B",
        "AI_A": "AI_A",
        "AI_B": "AI_B",
        "narrator": "narrator",
    }
    return mapping.get(speaker, speaker)


def voice_for_speaker(speaker: str, *, provider: str) -> str:
    role = normalize_speaker(speaker)
    if provider == "say":
        if role == "AI_A":
            return settings.tts_voice_openai
        if role == "AI_B":
            return settings.tts_voice_anthropic
        return settings.tts_voice_narrator
    if role == "AI_A":
        return settings.tts_edge_voice_openai
    if role == "AI_B":
        return settings.tts_edge_voice_anthropic
    return settings.tts_edge_voice_narrator
