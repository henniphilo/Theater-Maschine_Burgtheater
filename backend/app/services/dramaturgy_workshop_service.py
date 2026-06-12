from dataclasses import dataclass
from datetime import UTC, datetime
from typing import AsyncIterator, Literal

from app.director.dialogue.builder import build_dialogue_event
from app.director.dramaturgy.llm_director import LLMDirector
from app.director.outputs.osc_commands import build_osc_commands
from app.schemas.script import ScriptBeat
from app.services.ai_service import AIService

DRAMATURGY_SYSTEM = """Ihr seid zwei Theater-Dramaturgen in einem Workshop.
Diskutiert ausschließlich die Regie für den gegebenen Textabschnitt: Video, Sound, Licht.
Bezieht euch auf konkrete Medien-IDs aus dem Katalog. Kurz und präzise (max. 4 Sätze).
Kein allgemeines Pro/Contra zum Thema — nur Bühnenbild und Cues."""

OPENAI_DRAMATURGE = "Dramaturg A (GPT)"
ANTHROPIC_DRAMATURGE = "Dramaturg B (Claude)"

EventType = Literal["thinking", "discussion_turn", "dramaturgy_decision", "beat_done", "error", "done"]


@dataclass
class WorkshopEvent:
    type: EventType
    beat_id: str | None = None
    beat_order: int | None = None
    speaker: str | None = None
    content: str | None = None
    dramaturgy: dict | None = None
    planned_commands: list[dict] | None = None
    discussion_summary: str | None = None
    detail: str | None = None


class DramaturgyWorkshopService:
    def __init__(
        self,
        ai_service: AIService | None = None,
        llm_director: LLMDirector | None = None,
    ) -> None:
        self.ai = ai_service or AIService()
        self.llm_director = llm_director or LLMDirector(ai_service=self.ai)

    def _validate_providers(self) -> None:
        if "openai" not in self.ai.providers:
            raise ValueError("OpenAI is not configured (set OPENAI_API_KEY)")
        if "anthropic" not in self.ai.providers:
            raise ValueError("Anthropic is not configured (set ANTHROPIC_API_KEY)")

    async def _openai_discussion(
        self,
        beat: ScriptBeat,
        title: str,
        catalog_hint: str,
        prior: list[str],
        openai_model: str,
    ) -> str:
        context = "\n\n".join(prior) if prior else "(noch keine Diskussion)"
        user = (
            f"Stück: {title}\n"
            f"Textabschnitt:\n{beat.text}\n\n"
            f"Medien-Katalog (Auszug):\n{catalog_hint}\n\n"
            f"Bisherige Dramaturgie-Diskussion:\n{context}\n\n"
            "Ergänze oder widersprich mit einer konkreten Regie-Empfehlung."
        )
        return await self.ai.generate(
            "openai",
            openai_model,
            [
                {"role": "system", "content": DRAMATURGY_SYSTEM},
                {"role": "user", "content": user},
            ],
            max_tokens=280,
        )

    async def _anthropic_discussion(
        self,
        beat: ScriptBeat,
        title: str,
        catalog_hint: str,
        prior: list[str],
        anthropic_model: str,
    ) -> str:
        context = "\n\n".join(prior) if prior else "(noch keine Diskussion)"
        user = (
            f"Stück: {title}\n"
            f"Textabschnitt:\n{beat.text}\n\n"
            f"Medien-Katalog (Auszug):\n{catalog_hint}\n\n"
            f"Bisherige Dramaturgie-Diskussion:\n{context}\n\n"
            "Antworte auf die letzte Empfehlung mit deiner Regie-Sicht."
        )
        return await self.ai.generate(
            "anthropic",
            anthropic_model,
            [
                {"role": "system", "content": DRAMATURGY_SYSTEM},
                {"role": "user", "content": user},
            ],
            max_tokens=280,
        )

    async def run_stream(
        self,
        *,
        title: str,
        beats: list[ScriptBeat],
        openai_model: str,
        anthropic_model: str,
        discussion_rounds: int = 1,
    ) -> AsyncIterator[WorkshopEvent]:
        self._validate_providers()
        catalog_hint = str(self.llm_director.catalog_allowlist())[:1200]

        for beat in beats:
            discussion_lines: list[str] = []
            try:
                for _round in range(discussion_rounds):
                    yield WorkshopEvent(type="thinking", beat_id=beat.id, beat_order=beat.order, speaker="openai")
                    gpt = await self._openai_discussion(
                        beat, title, catalog_hint, discussion_lines, openai_model
                    )
                    discussion_lines.append(f"{OPENAI_DRAMATURGE}: {gpt}")
                    yield WorkshopEvent(
                        type="discussion_turn",
                        beat_id=beat.id,
                        beat_order=beat.order,
                        speaker="openai",
                        content=gpt,
                    )

                    yield WorkshopEvent(type="thinking", beat_id=beat.id, beat_order=beat.order, speaker="anthropic")
                    claude = await self._anthropic_discussion(
                        beat, title, catalog_hint, discussion_lines, anthropic_model
                    )
                    discussion_lines.append(f"{ANTHROPIC_DRAMATURGE}: {claude}")
                    yield WorkshopEvent(
                        type="discussion_turn",
                        beat_id=beat.id,
                        beat_order=beat.order,
                        speaker="anthropic",
                        content=claude,
                    )

                discussion_summary = "\n".join(discussion_lines)
                event = build_dialogue_event(
                    speaker="openai" if beat.speaker == "AI_A" else "anthropic",
                    text=beat.text,
                    topic=title,
                    created_at=datetime.now(UTC),
                )
                decision = await self.llm_director.decide(
                    event,
                    model=openai_model,
                    discussion_context=discussion_summary,
                )
                planned = build_osc_commands(decision, dry_run=True)

                yield WorkshopEvent(
                    type="dramaturgy_decision",
                    beat_id=beat.id,
                    beat_order=beat.order,
                    dramaturgy=decision.model_dump(mode="json"),
                    planned_commands=[c.model_dump(mode="json") for c in planned],
                    discussion_summary=discussion_summary,
                )
                yield WorkshopEvent(
                    type="beat_done",
                    beat_id=beat.id,
                    beat_order=beat.order,
                    discussion_summary=discussion_summary,
                )
            except Exception as exc:
                yield WorkshopEvent(
                    type="error",
                    beat_id=beat.id,
                    beat_order=beat.order,
                    detail=str(exc),
                )
                return

        yield WorkshopEvent(type="done")
