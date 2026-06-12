import json
import re
from typing import Any

from app.core.config import settings
from app.director.cues.cue_models import DramaturgyDecision
from app.director.dialogue.models import DialogueEvent
from app.director.dramaturgy.engine import DramaturgyEngine
from app.director.media.database import MediaDatabase
from app.services.ai_service import AIService


class DramaturgyValidationError(ValueError):
    pass


class LLMDirector:
    def __init__(
        self,
        media_db: MediaDatabase | None = None,
        ai_service: AIService | None = None,
    ) -> None:
        self.media_db = media_db or MediaDatabase()
        self.ai = ai_service or AIService()
        self.rule_engine = DramaturgyEngine(self.media_db)

    def catalog_allowlist(self) -> dict[str, Any]:
        return {
            "videos": [
                {"id": v.id, "tags": v.tags, "moods": v.moods}
                for v in self.media_db.videos
            ],
            "sounds": [
                {"id": s.id, "tags": s.tags, "moods": s.moods}
                for s in self.media_db.sounds
            ],
            "lights": [
                {"id": s.id, "moods": s.moods, "description": s.description}
                for s in self.media_db.light_scenes
            ],
            "allowed_visual_actions": ["play_clip", "fade_to_black", "stop_clip"],
            "allowed_sound_actions": ["trigger_cue", "stop_cue", "set_volume"],
            "allowed_light_actions": ["set_scene", "fade_blackout", "pulse"],
        }

    async def decide(
        self,
        event: DialogueEvent,
        *,
        model: str = "gpt-4o",
        discussion_context: str = "",
    ) -> DramaturgyDecision:
        if settings.director_dramaturgy_mode == "rules":
            return self.rule_engine.decide(event)

        try:
            raw = await self._call_llm(event, model=model, discussion_context=discussion_context)
            decision = self._parse_decision(raw, event)
            self.validate_decision(decision)
            return decision
        except (DramaturgyValidationError, json.JSONDecodeError, KeyError, ValueError):
            return self.rule_engine.decide(event)

    async def _call_llm(
        self,
        event: DialogueEvent,
        *,
        model: str,
        discussion_context: str,
    ) -> str:
        catalog = json.dumps(self.catalog_allowlist(), ensure_ascii=False)
        system = (
            "Du bist eine Theater-Regisseurin. Wähle NUR IDs aus der Medien-Allowlist. "
            "Antworte ausschließlich mit gültigem JSON ohne Markdown."
        )
        user = (
            f"Textabschnitt:\n{event.text}\n\n"
            f"Thema/Kontext: {event.topic}\n"
            f"Stimmung: {event.mood}, Intensität: {event.intensity}, Tags: {event.tags}\n\n"
            f"Dramaturgie-Diskussion:\n{discussion_context or '(keine)'}\n\n"
            f"Medien-Allowlist:\n{catalog}\n\n"
            "JSON-Schema:\n"
            '{"visual":{"action":"play_clip","clip_id":"...","opacity":0.8,"fade_time":4},'
            '"sound":{"action":"trigger_cue","cue_id":"...","volume":0.6},'
            '"light":{"action":"set_scene","scene_id":"...","fade_time":4},'
            '"reason":"...","tags":[],"mood":"...","intensity":0.5,"timestamp":0}'
        )
        return await self.ai.generate(
            "openai",
            model,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=800,
        )

    def _parse_decision(self, raw: str, event: DialogueEvent) -> DramaturgyDecision:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        data = json.loads(cleaned)
        data.setdefault("tags", event.tags)
        data.setdefault("mood", event.mood)
        data.setdefault("intensity", event.intensity)
        data.setdefault("timestamp", event.timestamp)
        return DramaturgyDecision.model_validate(data)

    def validate_decision(self, decision: DramaturgyDecision) -> None:
        video_ids = {v.id for v in self.media_db.videos}
        sound_ids = {s.id for s in self.media_db.sounds}
        light_ids = {s.id for s in self.media_db.light_scenes}

        if decision.visual and decision.visual.clip_id and decision.visual.clip_id not in video_ids:
            raise DramaturgyValidationError(f"Unknown clip_id: {decision.visual.clip_id}")
        if decision.sound and decision.sound.cue_id and decision.sound.cue_id not in sound_ids:
            raise DramaturgyValidationError(f"Unknown cue_id: {decision.sound.cue_id}")
        if decision.light and decision.light.scene_id and decision.light.scene_id not in light_ids:
            raise DramaturgyValidationError(f"Unknown scene_id: {decision.light.scene_id}")
